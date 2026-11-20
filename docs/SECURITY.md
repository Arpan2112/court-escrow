# Security notes — CourtEscrow contracts

Scope: `contracts/deal_judge.py` and `contracts/evidence_guard.py`, GenLayer
Studio Next testnet. These contracts hold no escrow and move no assets; the
risks below are about *verdict integrity* — a wrong verdict relayed to the
Alkahest arbiter would settle a testnet escrow wrongly.

## Prompt-injection posture

Both contracts fetch web content and hand it to an LLM. That content is
attacker-controlled (a seller chooses the evidence URL). Defences:

1. **Content is framed as data.** The judge/checker prompts state explicitly
   that the fetched content is untrusted data, that instructions inside it
   must not be followed, and that content addressing the judge is itself a
   signal to answer INSUFFICIENT / UNDETERMINED.
2. **Closed output sets.** Verdicts are validated on-chain against a fixed
   set (`SUPPORTED/CONTRADICTED/INSUFFICIENT`,
   `RELEASE/REFUND/UNDETERMINED`). Anything else — including a model that
   was successfully manipulated into inventing a new token — is coerced to
   the safe outcome (INSUFFICIENT / UNDETERMINED), never to a favourable
   one. Malformed JSON degrades the same way.
3. **Failures never become verdicts.** In DealJudge, a retrieval failure
   (HTTP error, empty page, render exception), an LLM failure, malformed
   judge output, or an evidence-hash mismatch ABORTS the resolution: the
   case stays DISPUTED and can be retried. A seller who takes the
   evidence page down gains nothing. UNDETERMINED is reachable only when
   no evidence URL was provided at all, or when the judge read real,
   hash-valid evidence and found it genuinely inconclusive.
4. **Consensus covers the verdict token only.** `resolve_case` runs its
   fetch + judgement under `gl.eq_principle.strict_eq` on the single
   verdict string (RELEASE / REFUND / UNDETERMINED). The explanation
   (criteria results, summary) is generated afterwards by the leader as
   non-authoritative information and can never alter the verdict.
   EvidenceGuard likewise validates its verdict against a closed set
   under strict_eq.
5. **Input caps.** Claims, agreements, criteria, manifests, and reasons
   are length-capped; criteria are validated as a 1–10 item string list at
   case opening and again at resolution.
6. **Allowlists on both contracts.** EvidenceGuard and DealJudge only
   fetch `https://` URLs whose host is on the constructor allowlist
   (exact host match). Fetched content is truncated to 6,000 chars.
7. **Evidence integrity.** At delivery the seller pins the sha256 of the
   evidence content; adjudication re-computes it over the fetched
   content and aborts on mismatch (page swapped after delivery = failed
   retrieval = case stays DISPUTED). Note: redirect behaviour is a
   property of the GenVM web renderer, not something the contract can
   inspect; the allowlist binds the submitted URL and the hash pins the
   content actually judged.
8. **Role checks.** Delivery only by the seller, dispute/accept only by
   the buyer, resolution only by a party to the case. State machine is
   enforced (`OPEN → DELIVERED → DISPUTED → RESOLVED`, or
   `DELIVERED → RESOLVED` on acceptance); terminal cases cannot re-open.

## Known limitations (disclosed)

- A hash proves a delivery package is the one that was registered; it
  does not prove the underlying work is good. That judgement is the
  rubric step's job, and rubrics can be gamed with superficially complete
  evidence — human review remains the backstop for real value.
- The demo relay is a trusted operator (see ARCHITECTURE.md). The verdict
  is public on GenLayer, so a relay that forwards a different decision
  than the recorded verdict is detectable after the fact.
- `strict_eq` on free-text-adjacent JSON is strict: validator disagreement
  on the model output fails the resolution transaction rather than
  recording a contested verdict. Retrying is safe (the case stays
  DISPUTED until a resolution succeeds).

## Test coverage

`tests/direct/test_evidence_guard.py` (9 tests) includes the agreed
regression set: supported / contradicted / insufficient evidence, a
prompt-injection page, over-long claim, disallowed URL, empty page, and
malformed AI output. `tests/direct/test_deal_judge.py` (14 tests) covers
the lifecycle, both verdict paths, the genuine-UNDETERMINED path, the
state machine guards, and the audit failure paths: seller-triggered
resolution against an HTTP 503 endpoint, empty evidence page, evidence
hash mismatch, and malformed judge output — all of which must leave the
case DISPUTED. Full suite: 23/23 passing; genvm-lint passes on both
contracts.
