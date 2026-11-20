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

# reproducible demo scenarios (testnet)
npm run demo:accepted
npm run demo:disputed
npm run verify
```

## Networks & safety

GenLayer Studio Next (chain 61997) + Base Sepolia only. Burner wallets,
testnet assets only, no mainnet, no real funds, no secrets in this repo.

## Deployments — GenLayer Studio Next (chain 61997)

Deployed from the project's testnet burner wallet via GenLayer Studio
Dev; both deploy transactions reached FINALIZED and both contracts
answer read calls (initial counters verified 0).

| Contract | Address | Deploy tx |
| --- | --- | --- |
| EvidenceGuard | `0x45f7Fe4DA9640457c9411b736E262675DF011A64` | `0x40d98b03052b5b14f31f5ddff2eb55980c96878fda6a9230ba6702048c63fa7a` |
| DealJudge (current) | `0x605AEdC0f6F2a07d9CD581a2fDc1d140E2742DeB` | `0xc1c9cd8b40b1367648ad2bcd8b07f26785df2b3998c23651864cbf44feca8219` |

DealJudge was redeployed once after a post-deploy audit found that an
evidence URL could be delivered without a pinned hash (and that the
hash check accepted non-hex strings). The patched build makes a valid
sha256 hash mandatory whenever an evidence URL is present. The first
DealJudge deployment (`0x89093EF2324E4aa4534A9DCa586Ff70ee6702262`) is
superseded and unused.

## Status

Work in progress for Mission 101 (deadline 23 Nov 2026, 06:59 WIB).
Built by Lexy5738 with the GenLayer project boilerplate as the starting
scaffold.
