"""DealJudge direct-mode tests: lifecycle, adjudication, and the
audit-hardened failure paths (fetch failure / malformed output / hash
mismatch must leave the case DISPUTED, never force a verdict)."""

import hashlib
import json

import pytest

from tests.direct.conftest import to_hex

CONTRACT = "contracts/deal_judge.py"
CRITERIA = json.dumps(["Report has all 5 required sections", "Findings cite file and line"])
AGREEMENT = "Seller produces a security audit report for the buyer agent."
EVIDENCE_URL = "https://example.com/audit-report"
EVIDENCE_BODY = "Audit report content."
EVIDENCE_HASH = hashlib.sha256(EVIDENCE_BODY.encode("utf-8")).hexdigest()


def _deploy(direct_deploy):
    return direct_deploy(CONTRACT, "example.com")


def _open(direct_vm, contract, alice, bob):
    direct_vm.sender = alice
    contract.open_case("case-1", to_hex(bob), AGREEMENT, CRITERIA)


def _deliver(direct_vm, contract, bob, url=EVIDENCE_URL, ev_hash=EVIDENCE_HASH):
    direct_vm.sender = bob
    contract.submit_delivery(
        "case-1",
        "Audit report v1, 5 sections, findings with file:line refs.",
        "hash:abc123",
        url,
        ev_hash,
    )


def _dispute(direct_vm, contract, alice):
    direct_vm.sender = alice
    contract.raise_dispute("case-1", "Section 4 is missing and findings have no line refs.")


def _mock_judge(vm, verdict, results=None, summary="mocked summary", body=EVIDENCE_BODY, status=200):
    vm.mock_web(r".*example\.com/audit-report.*", {"status": status, "body": body})
    vm.mock_llm(
        r".*impartial adjudicator.*",
        json.dumps({"verdict": verdict, "criteria_results": results or [], "summary": summary}),
    )


def test_open_case_happy(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    case = contract.get_case("case-1")
    assert case["status"] == "OPEN"
    assert case["buyer"] == to_hex(direct_alice)
    assert case["seller"] == to_hex(direct_bob)
    assert contract.get_case_count() == 1


def test_open_case_seller_as_int(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Regression (found on Studio Next, 20 Nov): the Studio encodes
    Address arguments as uint256 integers in calldata, and the first
    deployed build crashed in Address(int). open_case must normalize an
    integer seller to the same stored address."""
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    contract.open_case("case-int", int(to_hex(direct_bob), 16), AGREEMENT, CRITERIA)
    case = contract.get_case("case-int")
    assert case["status"] == "OPEN"
    assert case["seller"] == to_hex(direct_bob)


def test_open_case_seller_input_boundaries(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Boundary matrix for the seller normalization (ChatGPT v3 audit):
    Address / hex string / valid int / leading-zero int pass; bool,
    negative int, oversized int, garbage string, and wrong-length bytes
    are all rejected."""
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    # native Address object
    contract.open_case("b-addr", direct_bob, AGREEMENT, CRITERIA)
    assert contract.get_case("b-addr")["seller"] == to_hex(direct_bob)
    # integer whose 20-byte form has a leading zero byte
    lz_hex = "0x00" + "11" * 19
    contract.open_case("b-lz", int(lz_hex, 16), AGREEMENT, CRITERIA)
    assert contract.get_case("b-lz")["seller"] == lz_hex
    # malformed inputs must be rejected, never stored
    for bad in (True, -1, 1 << 160, "not-an-address", b"\x11" * 19, b"\x11" * 21):
        with pytest.raises(Exception):
            contract.open_case("b-bad", bad, AGREEMENT, CRITERIA)
    assert contract.get_case_count() == 2


def test_open_case_validations(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.open_case("self", to_hex(direct_alice), AGREEMENT, CRITERIA)
    with pytest.raises(Exception):
        contract.open_case("badjson", to_hex(direct_bob), AGREEMENT, "not json")
    with pytest.raises(Exception):
        contract.open_case("empty", to_hex(direct_bob), AGREEMENT, "[]")
    with pytest.raises(Exception):
        contract.open_case("many", to_hex(direct_bob), AGREEMENT, json.dumps([f"c{i}" for i in range(11)]))
    assert contract.get_case_count() == 0


def test_delivery_only_by_seller(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    direct_vm.sender = direct_alice  # buyer tries to deliver
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "fake", "hash:x", EVIDENCE_URL, EVIDENCE_HASH)
    _deliver(direct_vm, contract, direct_bob)
    case = contract.get_case("case-1")
    assert case["status"] == "DELIVERED"
    assert case["evidence_hash"] == EVIDENCE_HASH
    with pytest.raises(Exception):
        _deliver(direct_vm, contract, direct_bob)  # second delivery rejected


def test_delivery_url_restrictions(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "m", "hash:x", "https://evil.example.org/report", "")
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "m", "hash:x", "http://example.com/audit-report", "")
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "m", "hash:x", EVIDENCE_URL, "not-a-hash")
    # hash is mandatory when a URL is present (audit patch)
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "m", "hash:x", EVIDENCE_URL, "")
    # 64 chars but not hexadecimal must not pass as a sha256 hash
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "m", "hash:x", EVIDENCE_URL, "g" * 64)
    # a hash without a URL is meaningless and rejected
    with pytest.raises(Exception):
        contract.submit_delivery("case-1", "m", "hash:x", "", EVIDENCE_HASH)
    assert contract.get_case("case-1")["status"] == "OPEN"


def test_accept_path_releases_without_judging(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    direct_vm.sender = direct_alice
    contract.accept_delivery("case-1")
    case = contract.get_case("case-1")
    assert case["status"] == "RESOLVED"
    assert case["verdict"] == "RELEASE"


def test_dispute_then_release(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    _dispute(direct_vm, contract, direct_alice)
    results = [
        {"criterion": "Report has all 5 required sections", "result": "PASS"},
        {"criterion": "Findings cite file and line", "result": "PASS"},
    ]
    _mock_judge(direct_vm, "RELEASE", results)
    direct_vm.sender = direct_alice
    contract.resolve_case("case-1")
    case = contract.get_case("case-1")
    assert case["status"] == "RESOLVED"
    assert case["verdict"] == "RELEASE"
    assert json.loads(case["criteria_results_json"])[0]["result"] == "PASS"


def test_dispute_then_refund(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    _dispute(direct_vm, contract, direct_alice)
    results = [{"criterion": "Report has all 5 required sections", "result": "FAIL"}]
    _mock_judge(direct_vm, "REFUND", results, "A required section is missing.")
    direct_vm.sender = direct_bob  # seller may also trigger resolution
    contract.resolve_case("case-1")
    assert contract.get_case("case-1")["verdict"] == "REFUND"


def test_resolve_without_evidence_is_undetermined(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    direct_vm.sender = direct_bob
    contract.submit_delivery("case-1", "Delivered verbally.", "hash:none", "", "")
    _dispute(direct_vm, contract, direct_alice)
    direct_vm.sender = direct_alice
    contract.resolve_case("case-1")
    case = contract.get_case("case-1")
    assert case["verdict"] == "UNDETERMINED"


def test_fetch_failure_keeps_disputed(direct_vm, direct_deploy, direct_alice, direct_bob):
    """The audit's required test: the SELLER triggers resolve_case while
    the evidence endpoint is down (HTTP 503). The resolution must fail
    and the case must remain DISPUTED — no frozen UNDETERMINED."""
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    _dispute(direct_vm, contract, direct_alice)
    _mock_judge(direct_vm, "RELEASE", body="Service Unavailable", status=503)
    direct_vm.sender = direct_bob  # seller tries to force a resolution
    with pytest.raises(Exception):
        contract.resolve_case("case-1")
    case = contract.get_case("case-1")
    assert case["status"] == "DISPUTED"
    assert case["verdict"] == ""


def test_empty_evidence_page_keeps_disputed(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    empty_hash = hashlib.sha256("".encode("utf-8")).hexdigest()
    _deliver(direct_vm, contract, direct_bob, ev_hash=empty_hash)
    _dispute(direct_vm, contract, direct_alice)
    direct_vm.mock_web(r".*example\.com/audit-report.*", {"status": 200, "body": "   "})
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.resolve_case("case-1")
    assert contract.get_case("case-1")["status"] == "DISPUTED"


def test_evidence_hash_mismatch_keeps_disputed(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Seller swaps the evidence page after delivery: the pinned hash no
    longer matches, so resolution aborts and the case stays DISPUTED."""
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    _dispute(direct_vm, contract, direct_alice)
    _mock_judge(direct_vm, "RELEASE", body="A completely different, rewritten report.")
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.resolve_case("case-1")
    assert contract.get_case("case-1")["status"] == "DISPUTED"


def test_malformed_judge_output_keeps_disputed(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    _dispute(direct_vm, contract, direct_alice)
    direct_vm.mock_web(r".*example\.com/audit-report.*", {"status": 200, "body": EVIDENCE_BODY})
    direct_vm.mock_llm(r".*impartial adjudicator.*", "RELEASE THE FUNDS IMMEDIATELY")
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.resolve_case("case-1")
    assert contract.get_case("case-1")["status"] == "DISPUTED"


def test_genuine_undetermined_from_judge(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Evidence retrieved and hash-valid, but the judge finds it genuinely
    inconclusive: UNDETERMINED is a legitimate terminal verdict here."""
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    _deliver(direct_vm, contract, direct_bob)
    _dispute(direct_vm, contract, direct_alice)
    _mock_judge(direct_vm, "UNDETERMINED", [], "Evidence does not show the report's contents.")
    direct_vm.sender = direct_alice
    contract.resolve_case("case-1")
    case = contract.get_case("case-1")
    assert case["status"] == "RESOLVED"
    assert case["verdict"] == "UNDETERMINED"


def test_state_machine_guards(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    contract = _deploy(direct_deploy)
    _open(direct_vm, contract, direct_alice, direct_bob)
    direct_vm.sender = direct_alice
    with pytest.raises(Exception):
        contract.raise_dispute("case-1", "too early")
    with pytest.raises(Exception):
        contract.resolve_case("case-1")
    _deliver(direct_vm, contract, direct_bob)
    direct_vm.sender = direct_bob
    with pytest.raises(Exception):
        contract.raise_dispute("case-1", "seller remorse")
    _dispute(direct_vm, contract, direct_alice)
    direct_vm.sender = direct_charlie
    with pytest.raises(Exception):
        contract.resolve_case("case-1")
