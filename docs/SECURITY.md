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
   `RELEASE/REFUND/UNDETERMINED`). In EvidenceGuard, anything else —
   including a model manipulated into inventing a new token, or malformed
   JSON — is coerced to INSUFFICIENT, never to a favourable outcome. In
   DealJudge, malformed or out-of-set judge output instead ABORTS the
   resolution (see 3): no verdict is recorded at all.
3. **Failures never become verdicts.** In DealJudge, a retrieval failure
   (HTTP error, empty page, render exception), an LLM failure, malformed
   judge output, or an evidence-hash mismatch ABORTS the resolution: the
   case stays DISPUTED and can be retried. A seller who takes the
   evidence page down gains nothing. UNDETERMINED is reachable only when
   no evidence URL was provided at all, or when the judge read real,
   hash-valid evidence and found it genuinely inconclusive.
4. **Consensus covers the verdict token only.** `resolve_case` runs ALL
   of its nondeterministic work inside a single leader/validator block
   (`gl.vm.run_nondet_unsafe`). The leader fetches and verifies the
   evidence, judges it, and drafts the explanation (criteria results,
   summary) as non-authoritative information. Each validator
   independently re-fetches, re-verifies, and re-judges the evidence and
   accepts only if its own verdict equals the leader's — so consensus
   covers only the verdict token (RELEASE / REFUND / UNDETERMINED) and
   the explanation can never alter the outcome. Storage writes happen
   only after the block returns. EvidenceGuard likewise validates its
   verdict against a closed set under strict_eq.
5. **Input caps.** Claims, agreements, criteria, manifests, and reasons
   are length-capped; criteria are validated as a 1–10 item string list at
   case opening and again at resolution.
6. **Allowlists on both contracts.** EvidenceGuard and DealJudge only
   fetch `https://` URLs whose host is on the constructor allowlist
   (exact host match). Fetched content is truncated to 6,000 chars.
7. **Evidence integrity.** When a delivery carries an evidence URL, a
   valid sha256 hash is MANDATORY (a URL with an empty or non-hex hash
   is rejected at delivery, as is a hash without a URL — both gaps were
   found in post-deploy audit and patched). At delivery the seller pins
   the sha256 of the evidence content; adjudication re-computes it over
   the fetched content and aborts on mismatch (page swapped after
   delivery = failed retrieval = case stays DISPUTED). The hash is over
   the content as fetched and truncated to 6,000 chars — clients must
   pin the hash of that same representation. **Representation rule
   (learned live, 20 Nov 2026):** the fetch uses `gl.nondet.web.get`
   (raw response body), never `web.render`. A dedicated probe contract
   (RenderProbe) proved that `web.render` normalizes text — for the
   demo's delivery-complete.md it returned 703 chars against the raw
   file's 706, so a raw-file pin could never verify and every judged
   resolution of that case aborted deterministically. Clients pin the
   sha256 of the raw file bytes (UTF-8), exactly what `web.get`
   returns. Note: redirect behaviour is a property of the GenVM web
   layer, not something the contract can inspect; the allowlist binds
   the submitted URL and the hash pins the content actually judged.
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
- Consensus covers only the single verdict token: validator disagreement
  on that token fails the resolution transaction rather than recording a
  contested verdict. Retrying is safe (the case stays DISPUTED until a
  resolution succeeds).

## Test coverage

`tests/direct/test_evidence_guard.py` (9 tests) includes the agreed
regression set: supported / contradicted / insufficient evidence, a
prompt-injection page, over-long claim, disallowed URL, empty page, and
malformed AI output. `tests/direct/test_deal_judge.py` (21 tests) covers
the lifecycle, both verdict paths, the genuine-UNDETERMINED path, the
state machine guards, the audit failure paths (seller-triggered
resolution against an HTTP 503 endpoint, empty evidence page, evidence
hash mismatch, and malformed judge output — all of which must leave the
case DISPUTED), the seller-address input boundary matrix (Address /
hex string / integer / leading-zero integer accepted; bool, negative,
oversized, garbage, and wrong-length inputs rejected), and the
leader/validator consensus gates (validator accepts matching RELEASE
and REFUND verdicts, rejects a mismatched verdict, rejects when its own
evidence fetch fails, and an explanation failure leaves the verdict
intact with an empty explanation). Full suite: 73/73 passing;
genvm-lint exits 0 on both contracts.
