# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import hashlib
import json
from genlayer import *

# RenderProbe — a DIAGNOSTIC contract for CourtEscrow (not part of the
# product path; DealJudge is untouched).
#
# Why it exists: DealJudge.resolve_case kept aborting for one evidence
# file (delivery-complete.md) while succeeding for another. The suspects
# are (1) the sha256 of gl.nondet.web.render() output differs from the
# sha256 of the raw file the seller pinned, and (2) fetch results are
# not consistent across validators. This probe measures both, with no
# LLM involved:
#
# - It fetches the URL twice per node: web.render (text mode, the
#   representation DealJudge hashes) and web.get (raw body bytes).
# - For each representation it records length, sha256, whether the
#   sha256 equals the expected (seller-pinned) hash, and whitespace
#   statistics (newline count, CRLF count, trailing newline).
# - The result is accepted only if EVERY validator recomputes exactly
#   the same measurements as the leader (strict dict equality inside
#   gl.vm.run_nondet_unsafe). If the probe transaction itself fails,
#   that is the cross-validator inconsistency signal.
#
# All nondet calls are lexically inside leader_fn / validator_fn (the
# genvm-lint reachability rule that DealJudge v3 was restructured for).


class RenderProbe(gl.Contract):
    results: TreeMap[str, str]
    probe_count: u256

    def __init__(self):
        self.probe_count = u256(0)

    @gl.public.write
    def probe(self, probe_id: str, url: str, expected_hash: str) -> None:
        if probe_id in self.results:
            raise gl.vm.UserError("probe id already used")
        if len(url) > 300 or not url.startswith("https://"):
            raise gl.vm.UserError("invalid url")
        expected = expected_hash.strip().lower()

        def leader_fn():
            out = {}
            # --- web.render representation ---
            try:
                content = gl.nondet.web.render(url, mode="text")
                if content is None:
                    content = ""
                trimmed = content[:6000]
                digest = hashlib.sha256(trimmed.encode("utf-8")).hexdigest()
                out["render_length"] = str(len(trimmed))
                out["render_sha256"] = digest
                out["render_matches"] = "true" if digest == expected else "false"
                out["render_newlines"] = str(trimmed.count("\n"))
                out["render_crlf"] = str(trimmed.count("\r\n"))
                out["render_trailing_nl"] = "true" if trimmed.endswith("\n") else "false"
            except Exception:
                out["render_length"] = "-1"
                out["render_sha256"] = ""
                out["render_matches"] = "error"
                out["render_newlines"] = "-1"
                out["render_crlf"] = "-1"
                out["render_trailing_nl"] = "error"
            # --- web.get representation ---
            try:
                resp = gl.nondet.web.get(url)
                body = resp.body
                if isinstance(body, bytes):
                    text = body.decode("utf-8")
                else:
                    text = str(body)
                trimmed = text[:6000]
                digest = hashlib.sha256(trimmed.encode("utf-8")).hexdigest()
                out["get_length"] = str(len(trimmed))
                out["get_sha256"] = digest
                out["get_matches"] = "true" if digest == expected else "false"
                out["get_newlines"] = str(trimmed.count("\n"))
                out["get_crlf"] = str(trimmed.count("\r\n"))
                out["get_trailing_nl"] = "true" if trimmed.endswith("\n") else "false"
            except Exception:
                out["get_length"] = "-1"
                out["get_sha256"] = ""
                out["get_matches"] = "error"
                out["get_newlines"] = "-1"
                out["get_crlf"] = "-1"
                out["get_trailing_nl"] = "error"
            return out

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            proposed = leader_result.calldata
            if not isinstance(proposed, dict):
                return False
            mine = leader_fn()
            return mine == proposed

        outcome = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        self.results[probe_id] = json.dumps(outcome, sort_keys=True)
        self.probe_count = u256(int(self.probe_count) + 1)

    @gl.public.view
    def get_result(self, probe_id: str) -> str:
        if probe_id not in self.results:
            raise gl.vm.UserError("unknown probe")
        return self.results[probe_id]

    @gl.public.view
    def get_probe_count(self) -> int:
        return int(self.probe_count)
