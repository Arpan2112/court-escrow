# CourtEscrow

**Two agents agree. One delivers. GenLayer judges when they disagree.**

An agent-to-agent escrow demo for GenLayer Portal **Mission 101 — Internet
Court: Partner Demo Lab**: a buyer agent pays a seller agent for a deliverable;
the money sits in an **Alkahest** (Arkhai) conditional escrow on Base Sepolia;
if the buyer disputes the delivery, a **GenLayer** intelligent contract judges
it against the acceptance criteria both sides agreed up front — the
adjudication pattern at the heart of **Internet Court**.

- 📐 Concept & architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- ⚖️ GenLayer contract: `contracts/deal_judge.py` (with `contracts/evidence_guard.py`)
- 🧪 Direct-mode tests: `tests/direct/` (web/LLM mocked, no Studio required)
- 🎬 Demo video (≤45 s): linked in the Mission 101 submission

## Why

Escrow can lock money; it cannot judge quality. CourtEscrow separates the
three jobs cleanly:

| Layer | Job |
|---|---|
| Alkahest escrow | Lock and settle the payment (`TrustedOracleArbiter`) |
| Evidence package | Make the delivery judgeable (manifest + hash + references) |
| GenLayer `DealJudge` | Judge the delivery against the pre-agreed rubric → `RELEASE` / `REFUND` / `UNDETERMINED` |

A disclosed, trusted manual relay forwards the verdict to the arbiter.
`UNDETERMINED` is never forced into an approval — the escrow then follows its
normal expiry/reclaim path. All trust assumptions are documented in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

```shell
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# lint the contracts
genvm-lint check contracts/deal_judge.py

# run the direct-mode test suite
python -m pytest tests/direct/ -q

# demo tooling (testnets only)
#   GenLayer reads / evidence pins:  demo/genlayer_case.py
#   GenLayer writes: GenLayer Studio Dev UI (Run and Debug panel)
#   Base Sepolia escrow/fulfill/arbitrate/collect/reclaim:
#     NODE_PATH=<puppeteer_modules> node demo/base_ops.cjs <cdp-port> <action> '<json>'
# Every recorded demo transaction is listed in demo/results.json.
```

## Networks & safety

GenLayer Studio Next (chain 61997) + Base Sepolia only. Burner wallets,
testnet assets only, no mainnet, no real funds, no secrets in this repo.

## Deployments — GenLayer Studio Next (chain 61997)

Deployed from the project's testnet burner wallet via GenLayer Studio
Dev; both deploy transactions reached FINALIZED and both contracts
answer read calls (initial counters verified 0).

| Contract | Address | Deploy tx | Status |
| --- | --- | --- | --- |
| EvidenceGuard | `0x45f7Fe4DA9640457c9411b736E262675DF011A64` | `0x40d98b03052b5b14f31f5ddff2eb55980c96878fda6a9230ba6702048c63fa7a` | ACTIVE |
| DealJudge v4 | `0xC4feD4c49aE86Ec1A9803694A0EA0E677a15C2F3` | `0xf839b256c127ea70765d72c6fed3f18f6a182a6715b20afbcbafbe8e82a27811` | ACTIVE |
| DealJudge v3 | `0x7934c9A0a1Dd4D20759676B82690a93d8FF02Ca1` | `0x10210253927d42ed491222d91314a2e881340742705e3e14729221912cea6cb6` | Superseded by v4 |
| DealJudge v2 | `0x605AEdC0f6F2a07d9CD581a2fDc1d140E2742DeB` | `0xc1c9cd8b40b1367648ad2bcd8b07f26785df2b3998c23651864cbf44feca8219` | Superseded |
| DealJudge v1 | `0x89093EF2324E4aa4534A9DCa586Ff70ee6702262` | `0x280c32a5fd3404674190112965b8d6064fefe423bacac6ebf93a9f20741db578` | Superseded |

DealJudge's history, each step audit-driven: **v1 → v2** — a post-deploy
audit found an evidence URL could be delivered without a pinned hash
(and the hash check accepted non-hex strings); v2 makes a valid sha256
hash mandatory whenever an evidence URL is present. **v2 → v3** — the
resolve path was restructured so all nondeterministic work (fetch,
judge, explanation) runs inside one leader/validator block with storage
writes only after consensus, and seller addresses are normalized for
Studio's uint256 argument encoding. **v3 → v4** — on-chain diagnosis
(a dedicated `RenderProbe` contract) proved `gl.nondet.web.render`
normalizes text, so a sha256 pin over the raw file could never match;
v4 fetches the raw body via `gl.nondet.web.get`, checks the HTTP
status, and hashes the full body before truncation. Deployed v4 code
is byte-identical to the audited source (sha256
`d5e4ffbb01dfc87e65f7c3400a86474e366ffe26fdf14f18d26589d760c4a278`).

## Verified demo results (all on-chain)

Four GenLayer verdict paths and the full Alkahest settlement loop are
proven with recorded transactions — see `demo/results.json` for every
hash and UID.

| Path | Result |
| --- | --- |
| Buyer accepts delivery | Case `ce-accepted-1` → `RELEASE` (no LLM) |
| Disputed, incomplete evidence | Case `ce-refund-1` → `REFUND` by full consensus, all 3 criteria FAIL |
| Disputed, no evidence | Case `ce-undet-1` → `UNDETERMINED` (deterministic), never relayed |
| Disputed, complete evidence | Case `ce-release-v4` → `RELEASE` by full consensus, all 3 criteria PASS |
| Alkahest settlement of the judged RELEASE | Escrow `0xada1211f…53fd` → fulfillment → `arbitrate(true)` → seller **collect succeeded** (tx `0x245dedc6…b781`, seller +0.002 ETH) |
| Buyer reclaim of expired escrows | `ce-refund-1` and `ce-undet-1` escrows reclaimed in full |

One integration lesson worth recording: the Alkahest arbiter decodes
the escrow demand as `abi.encode(DemandData)` — the *nested* tuple
encoding with its outer offset word. Two early escrows were created
with the flat `abi.encode(address, bytes)` form; their demands cannot
be decoded by the arbiter, so those escrows can never be collected
(their 0.002 ETH each is reclaimable by the buyer after expiry,
~27 Nov 2026). All later escrows use the nested encoding, as
`demo/base_ops.cjs` now does.

## Status

Demo complete and verified on-chain for Mission 101 (deadline
23 Nov 2026, 06:59 WIB): 79/79 direct-mode tests pass, both contracts
lint clean, all four verdict paths and the full settlement loop are
recorded in `demo/results.json`. Built by Lexy5738 with the GenLayer
project boilerplate as the starting scaffold.
