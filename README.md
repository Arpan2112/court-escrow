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

## Status

Work in progress for Mission 101 (deadline 23 Nov 2026, 06:59 WIB).
Built by Lexy5738 with the GenLayer project boilerplate as the starting
scaffold.
