# builder-wg role request — draft (NOT sent; awaiting Lexy's go-ahead)

**Where:** GenLayer Discord — support ticket, or DM to @ras (per the
hackathon page: "Open a ticket or contact @ras on GenLayer's Discord").
**Account:** lexy5738 · Portal user Lexy5738 (id 82508) · GitHub Arpan2112

---

Hi team — I'm building for **Mission 101 (Internet Court: Partner Demo
Lab)** and would like to request the **builder-wg** role so I can submit.

**Project — CourtEscrow:** an agent-to-agent escrow demo. A buyer locks
payment in an Alkahest (Arkhai) escrow on Base Sepolia; on dispute, a
GenLayer intelligent contract (DealJudge) judges the delivery against
the pre-agreed acceptance criteria and returns RELEASE / REFUND /
UNDETERMINED; the recorded verdict is relayed to the official
TrustedOracleArbiter for settlement.

**Status — complete and verified on-chain:**
- DealJudge v4 deployed on Studio Next, code byte-identical to the
  audited source; 79/79 direct-mode tests pass, lint clean.
- All four verdict paths recorded on-chain (accept-RELEASE, judged
  RELEASE, judged REFUND, UNDETERMINED).
- Full Alkahest settlement proven on the official deployment: escrow →
  fulfillment → arbitrate → seller collect (+0.002 ETH); REFUND path:
  check() false, collect blocked, buyer reclaim.
- Public repo with a full demo report:
  https://github.com/Arpan2112/court-escrow

Happy to walk through any part of it. Thanks!
