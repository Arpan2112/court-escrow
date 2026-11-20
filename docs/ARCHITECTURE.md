# CourtEscrow — Concept & Architecture (1-pager)

**Mission:** GenLayer Portal Mission 101 — "Internet Court: Partner Demo Lab"
**Tagline:** Two agents agree. One delivers. GenLayer judges when they disagree.
**Deadline:** Mon 23 Nov 2026, 06:59 WIB (portal end_date 2026-11-22T23:59:00Z)

## Problem

AI agents increasingly pay each other for work (reports, audits, code, data).
Escrow alone cannot judge *quality*: a normal escrow releases on a timer or a
signature, not on whether the delivery meets the agreed acceptance criteria.
When buyer and seller disagree, there is no neutral, fast, cheap judge.

## Idea

Combine three existing layers, each doing the one job it is good at:

| Layer | Role |
|---|---|
| **Arkhai / Alkahest** (partner) | Conditional escrow on Base Sepolia: locks the payment, holds the fulfillment obligation (`StringObligation`), enforces the outcome via its `TrustedOracleArbiter`. |
| **Evidence package** (EvidenceGuard component) | Makes the delivery *judgeable*: manifest + content hash + evidence references, checked for internal consistency before any judging. A hash proves integrity of the package, not truth of its claims — stated openly. |
| **GenLayer** (adjudication, Internet Court pattern) | An intelligent contract (`DealJudge`) evaluates the delivery against the acceptance rubric agreed *before* the dispute — consensus (`gl.eq_principle.strict_eq`) covers only the verdict token — and returns one of three verdicts: `RELEASE`, `REFUND`, or `UNDETERMINED`. |

A **manual demo relay** (trusted operator, disclosed — not a bridge) forwards the
GenLayer verdict to the Alkahest `TrustedOracleArbiter`:
`RELEASE → approve`, `REFUND → reject`, `UNDETERMINED → no forced decision`
(the escrow follows its normal expiry/reclaim path).

## Flow

1. Buyer opens a case (`open_case`): agreement text + acceptance criteria are
   registered on GenLayer; buyer locks testnet funds in an Alkahest escrow with
   a trusted-oracle demand naming the relay address.
2. Seller delivers: creates the Alkahest `StringObligation` fulfillment and
   registers the delivery manifest + evidence hash on GenLayer
   (`submit_delivery`).
3. Happy path: buyer accepts → escrow pays out. No judging needed.
4. Dispute path: buyer raises a dispute (`raise_dispute`) → `resolve_case`
   runs the GenLayer adjudication against the pre-agreed rubric → verdict →
   relay calls `arbitrate` on Alkahest → escrow settles accordingly.

## Interface (reproducible)

CLI/skill-first, matching Internet Court's agent-to-agent nature:

```
npm run demo:accepted    # full happy-path scenario
npm run demo:disputed    # dispute scenario ending in a GenLayer verdict
npm run verify           # re-checks every recorded tx id / contract state
```

Each run emits a small HTML case report (parties, criteria, evidence hash,
verdict, tx ids) — the same report that is shown in the demo video.

## Trust assumptions (disclosed, not hidden)

- The relay operator is trusted to forward the verdict faithfully in this
  prototype; the verdict itself is public on GenLayer and the report links it,
  so a lying relay is detectable by anyone.
- EvidenceGuard checks package integrity/consistency only.
- Testnet only: GenLayer Studio Next + Base Sepolia, burner wallets, no real
  assets anywhere in the flow.

## Demo video (≤45 s)

Hook (two agents, one disputed delivery) → agreement & criteria → Alkahest
escrow lock → delivery + evidence hash → dispute → GenLayer adjudication →
verdict → relayed settlement on Alkahest → closing frame with the three logos
(Internet Court, GenLayer, Arkhai) and this repository's URL.
Only real transaction results are shown — no staged verdicts.

## Status

WIP — built for Mission 101 by Lexy5738 (GenLayer builder, portal user 82508).
GenLayer contract + direct-mode tests in progress; Alkahest integration on
Base Sepolia in progress. The `builder-wg` Discord role required by the
mission has been requested from the GenLayer team.
