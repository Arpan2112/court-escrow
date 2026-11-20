#!/usr/bin/env node
/* CourtEscrow demo — Base Sepolia ops via the VM MetaMask profiles.
 *
 * Drives Alkahest contracts through page-context provider calls on an
 * already wallet-authorized HTTPS origin (testnet.x1ecochain.com), with
 * hand-rolled ABI encoding (no external deps beyond puppeteer-core).
 * Every send is verified in the MetaMask confirmation popup (recipient,
 * value) before Confirm is clicked.
 *
 * Usage:
 *   node base_ops.js <port> state
 *   node base_ops.js <port> switch
 *   node base_ops.js <port> send-eth   {"to":"0x..","wei":"10000000000000000"}
 *   node base_ops.js <port> escrow    {"amountWei":"2000000000000000","context":"ce-release-1","expirySec":604800}
 *   node base_ops.js <port> fulfill   {"item":"...","refUid":"0x.."}
 *   node base_ops.js <port> arbitrate {"fulfillmentUid":"0x..","context":"ce-release-1","decision":true}
 *   node base_ops.js <port> collect   {"escrowUid":"0x..","fulfillmentUid":"0x.."}
 *   node base_ops.js <port> collect-sim {"escrowUid":"0x..","fulfillmentUid":"0x.."}
 *   node base_ops.js <port> reclaim   {"escrowUid":"0x.."}
 *   node base_ops.js <port> balance   {"address":"0x.."}
 *
 * Prints one JSON object with the result (tx hashes, UIDs, statuses).
 */
const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const C = JSON.parse(fs.readFileSync(path.join(__dirname, 'abi_constants.json'), 'utf8'));
const ESCROW = '0x2b642e572b06627678531c4f088dbfc0682b2d5c'; // NativeTokenEscrowObligation (Base Sepolia)
const STRING_OB = '0xb1e14fdebb8192fb0bee918075ccd350d0cb47a7'; // StringObligation
const ORACLE_ARB = '0xca13c55a1863ff8f6cef9166c30bb4563eb7dca3'; // TrustedOracleArbiter
const ORACLE = '0x91e8A2459CE827b8D2CF1a5D7E50B092D8FA3Ad3'; // relay/oracle account (wallet2)
const BASE_SEPOLIA = '0x14a34';
const sleep = ms => new Promise(r => setTimeout(r, ms));

// In-page helpers: minimal ABI encoder + provider wrappers.
const PAGE_LIB = `
window.__ce = (() => {
  const strip = h => h.startsWith('0x') ? h.slice(2) : h;
  const word = hex => strip(hex).padStart(64, '0');
  const addr = a => word(strip(a).toLowerCase());
  const uint = n => word(BigInt(n).toString(16));
  const bool = b => word(b ? '1' : '0');
  const bytes32 = b => word(strip(b));
  const dyn = hex => { // dynamic bytes: length word + padded data
    const d = strip(hex);
    const padded = d.padEnd(Math.ceil(d.length / 64) * 64 || 64, '0');
    return uint(d.length / 2) + padded;
  };
  const utf8 = s => [...new TextEncoder().encode(s)].map(b => b.toString(16).padStart(2, '0')).join('');
  // tuple(address, bytes)
  const tupleAddrBytes = (a, bytesHex) => addr(a) + uint(64) + dyn(bytesHex);
  // DemandData as a standalone value: abi.encode(DemandData) — a dynamic
  // tuple encoded WITH its outer offset word (0x20). The arbiter's
  // abi.decode(demand, (DemandData)) requires this nested form; the flat
  // tupleAddrBytes form (128 bytes) makes the decoder read the oracle
  // address as a tuple offset and revert. Diagnosed 20-21 Nov 2026 via
  // decodeDemandData/check fuzzing (see demo/results.json).
  const demandData = (a, bytesHex) => uint(32) + tupleAddrBytes(a, bytesHex);
  // tuple(address, bytes, uint256) for escrow ObligationData
  const escrowData = (arbiter, demandHex, amountWei) => addr(arbiter) + uint(96) + uint(amountWei) + dyn(demandHex);
  // tuple(string, bytes32)
  const stringData = (item, schemaTag) => uint(64) + bytes32(schemaTag) + dyn(utf8(item));
  const eth = window.ethereum;
  return { word, addr, uint, bool, bytes32, dyn, utf8, tupleAddrBytes, demandData, escrowData, stringData,
    request: (m, p) => eth.request({ method: m, params: p }) };
})();
'installed';
`;

async function getPage(browser) {
  const pages = await browser.pages();
  let page = pages.find(p => p.url().includes('testnet.x1ecochain.com'));
  if (!page) {
    page = await browser.newPage();
    await page.goto('https://testnet.x1ecochain.com', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await sleep(3500);
  }
  await page.bringToFront();
  const has = await page.evaluate(() => typeof window.__ce !== 'undefined').catch(() => false);
  if (!has) await page.evaluate(PAGE_LIB);
  return page;
}

async function confirmPopup(browser, expect) {
  // Poll for a MetaMask confirmation page; verify expectations; click Confirm.
  for (let i = 0; i < 24; i++) {
    await sleep(1500);
    const pages = await browser.pages();
    const pop = pages.find(p => p.url().includes('confirm') || p.url().includes('notification'));
    if (!pop) continue;
    await pop.bringToFront();
    await sleep(700);
    const t = await pop.evaluate(() => document.body.innerText).catch(() => '');
    if (!/Confirm/.test(t)) continue;
    const checks = {};
    if (expect.to) checks.to = t.toLowerCase().includes(expect.to.slice(0, 10).toLowerCase());
    if (expect.text) checks.text = t.includes(expect.text);
    const clicked = await pop.evaluate(() => {
      const b = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Confirm');
      if (b) { b.click(); return true; } return false;
    });
    return { found: true, checks, clicked, text: t.replace(/\n{2,}/g, '\n').slice(0, 300) };
  }
  return { found: false };
}

async function sendAndWait(page, browser, txParams, expect) {
  // Fire-and-forget in-page: the send promise resolves only after the user
  // confirms in MetaMask, so never hold an evaluate call open on it.
  await page.evaluate(p => {
    window.__ceSend = { status: 'pending' };
    window.__ce.request('eth_sendTransaction', [p])
      .then(h => { window.__ceSend = { status: 'sent', hash: h }; })
      .catch(e => { window.__ceSend = { status: 'error', error: (e.code || '') + ' ' + (e.message || '').slice(0, 140) }; });
    return 'initiated';
  }, txParams);
  const pop = await confirmPopup(browser, expect || {});
  let sent = null;
  for (let i = 0; i < 30; i++) {
    sent = await page.evaluate(() => window.__ceSend).catch(() => null);
    if (sent && sent.status !== 'pending') break;
    await sleep(1500);
  }
  if (!sent || sent.status !== 'sent') return { ...(sent || { status: 'timeout' }), pop };
  let receipt = null;
  for (let i = 0; i < 40 && !receipt; i++) {
    receipt = await page.evaluate(h => window.__ce.request('eth_getTransactionReceipt', [h]).catch(() => null), sent.hash);
    if (!receipt) await sleep(3000);
  }
  return { hash: sent.hash, pop, receipt };
}

function attestedUid(receipt, attester) {
  if (!receipt) return null;
  for (const log of receipt.logs || []) {
    if ((log.topics || [])[0] === C.topic_attested &&
        log.topics[2] && log.topics[2].toLowerCase().includes(attester.slice(2).toLowerCase())) {
      // EAS Attested(recipient, attester, uid, schemaUID): topics[3] is the
      // SCHEMA uid (identical across obligations of a type); the actual
      // attestation uid is the event's data payload.
      return log.data;
    }
  }
  return null;
}

(async () => {
  const [port, action, argJson] = process.argv.slice(2);
  const args = argJson ? JSON.parse(argJson) : {};
  const browser = await puppeteer.connect({ browserURL: `http://127.0.0.1:${port}`, protocolTimeout: 300000 });
  const page = await getPage(browser);
  const out = { action };
  try {
    if (action === 'state') {
      out.accounts = await page.evaluate(() => window.__ce.request('eth_accounts'));
      out.chainId = await page.evaluate(() => window.__ce.request('eth_chainId'));
    } else if (action === 'switch') {
      await page.evaluate(cid => {
        window.__ceSwitch = { status: 'pending' };
        window.__ce.request('wallet_switchEthereumChain', [{ chainId: cid }])
          .then(() => { window.__ceSwitch = { status: 'switched' }; })
          .catch(e => { window.__ceSwitch = { status: 'error', error: e.code + ' ' + (e.message || '').slice(0, 80) }; });
        return 'initiated';
      }, BASE_SEPOLIA);
      await confirmPopup(browser, {});
      let sw = null;
      for (let i = 0; i < 20; i++) {
        sw = await page.evaluate(() => window.__ceSwitch).catch(() => null);
        if (sw && sw.status !== 'pending') break;
        await sleep(1200);
      }
      out.switch = sw;
      out.chainId = await page.evaluate(() => window.__ce.request('eth_chainId'));
    } else if (action === 'addchain') {
      await page.evaluate(() => {
        window.__ceAdd = { status: 'pending' };
        window.__ce.request('wallet_addEthereumChain', [{
          chainId: '0x14a34', chainName: 'Base Sepolia',
          nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
          rpcUrls: ['https://sepolia.base.org'],
          blockExplorerUrls: ['https://sepolia.basescan.org']
        }]).then(() => { window.__ceAdd = { status: 'added' }; })
          .catch(e => { window.__ceAdd = { status: 'error', error: e.code + ' ' + (e.message || '').slice(0, 80) }; });
        return 'initiated';
      });
      await confirmPopup(browser, {});
      let ad = null;
      for (let i = 0; i < 20; i++) {
        ad = await page.evaluate(() => window.__ceAdd).catch(() => null);
        if (ad && ad.status !== 'pending') break;
        await sleep(1200);
      }
      out.add = ad;
      out.chainId = await page.evaluate(() => window.__ce.request('eth_chainId'));
    } else if (action === 'balance') {
      const wei = await page.evaluate(a => window.__ce.request('eth_getBalance', [a, 'latest']), args.address);
      out.address = args.address; out.wei = BigInt(wei).toString();
    } else if (action === 'send-eth') {
      const from = (await page.evaluate(() => window.__ce.request('eth_accounts')))[0];
      const value = '0x' + BigInt(args.wei).toString(16);
      const r = await sendAndWait(page, browser, { from, to: args.to, value }, { to: args.to });
      out.result = { hash: r.hash, status: r.receipt && r.receipt.status, error: r.error };
    } else if (action === 'escrow') {
      const from = (await page.evaluate(() => window.__ce.request('eth_accounts')))[0];
      const expiry = Math.floor(Date.now() / 1000) + (args.expirySec || 604800);
      const data = await page.evaluate(({ escrow, arb, oracle, ctx, amount, expiry, sel }) => {
        const demand = window.__ce.demandData(oracle, window.__ce.utf8(ctx));
        const body = window.__ce.escrowData(arb, demand, amount);
        // doObligation((address,bytes,uint256),uint64): head = offset 0x40 + expiry, then tuple
        return sel + window.__ce.uint(64) + window.__ce.uint(expiry) + body;
      }, { escrow: ESCROW, arb: ORACLE_ARB, oracle: ORACLE, ctx: args.context, amount: args.amountWei, expiry, sel: C.sel_escrow_doObligation });
      const value = '0x' + BigInt(args.amountWei).toString(16);
      const r = await sendAndWait(page, browser, { from, to: ESCROW, data, value }, { to: ESCROW });
      out.result = { hash: r.hash, status: r.receipt && r.receipt.status, error: r.error, escrowUid: attestedUid(r.receipt, ESCROW), expiry };
    } else if (action === 'fulfill') {
      const from = (await page.evaluate(() => window.__ce.request('eth_accounts')))[0];
      const data = await page.evaluate(({ item, tag, ref, sel }) => {
        const body = window.__ce.stringData(item, tag);
        return sel + window.__ce.uint(64) + window.__ce.bytes32(ref) + body;
      }, { item: args.item, tag: C.schema_tag_delivery, ref: args.refUid, sel: C.sel_string_doObligation });
      const r = await sendAndWait(page, browser, { from, to: STRING_OB, data }, { to: STRING_OB });
      out.result = { hash: r.hash, status: r.receipt && r.receipt.status, error: r.error, fulfillmentUid: attestedUid(r.receipt, STRING_OB) };
    } else if (action === 'arbitrate') {
      const from = (await page.evaluate(() => window.__ce.request('eth_accounts')))[0];
      out.from = from;
      const data = await page.evaluate(({ uid, ctx, decision, sel }) => {
        return sel + window.__ce.bytes32(uid) + window.__ce.uint(96) + window.__ce.bool(decision) + window.__ce.dyn(window.__ce.utf8(ctx));
      }, { uid: args.fulfillmentUid, ctx: args.context, decision: !!args.decision, sel: C.sel_arbitrate });
      const r = await sendAndWait(page, browser, { from, to: ORACLE_ARB, data }, { to: ORACLE_ARB });
      const arbLog = (r.receipt && r.receipt.logs || []).find(l => (l.topics || [])[0] === C.topic_arbitration_made);
      out.result = { hash: r.hash, status: r.receipt && r.receipt.status, error: r.error, arbitrationMade: !!arbLog };
    } else if (action === 'collect' || action === 'collect-sim') {
      const from = (await page.evaluate(() => window.__ce.request('eth_accounts')))[0];
      const calldata = await page.evaluate(({ e, f, sel }) => sel + window.__ce.bytes32(e) + window.__ce.bytes32(f),
        { e: args.escrowUid, f: args.fulfillmentUid, sel: C.sel_collect });
      if (action === 'collect-sim') {
        out.simulation = await page.evaluate(({ from, to, data }) => window.__ce.request('eth_call', [{ from, to, data }, 'latest'])
          .then(r => ({ ok: true, result: r })).catch(e => ({ ok: false, error: (e.message || '').slice(0, 160) })),
          { from, to: ESCROW, data: calldata });
      } else {
        const r = await sendAndWait(page, browser, { from, to: ESCROW, data: calldata }, { to: ESCROW });
        const colLog = (r.receipt && r.receipt.logs || []).find(l => (l.topics || [])[0] === C.topic_escrow_collected);
        out.result = { hash: r.hash, status: r.receipt && r.receipt.status, error: r.error, escrowCollected: !!colLog };
      }
    } else if (action === 'reclaim') {
      const from = (await page.evaluate(() => window.__ce.request('eth_accounts')))[0];
      const calldata = await page.evaluate(({ e, sel }) => sel + window.__ce.bytes32(e), { e: args.escrowUid, sel: C.sel_reclaim });
      const r = await sendAndWait(page, browser, { from, to: ESCROW, data: calldata }, { to: ESCROW });
      const recLog = (r.receipt && r.receipt.logs || []).find(l => (l.topics || [])[0] === C.topic_escrow_reclaimed);
      out.result = { hash: r.hash, status: r.receipt && r.receipt.status, error: r.error, escrowReclaimed: !!recLog };
    } else {
      out.error = 'unknown action';
    }
  } catch (e) {
    out.fatal = e.message.slice(0, 200);
  }
  console.log(JSON.stringify(out, null, 1));
  await browser.disconnect();
})();
