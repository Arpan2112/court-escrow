import hashlib

from gltest import get_contract_factory

COMPLETE_URL = "https://raw.githubusercontent.com/Arpan2112/court-escrow/main/demo/evidence/delivery-complete.md"


def _file_text():
    import pathlib

    p = pathlib.Path(__file__).resolve().parents[2] / "demo" / "evidence" / "delivery-complete.md"
    return p.read_text(encoding="utf-8")


def test_probe_records_render_measurement(direct_vm, direct_deploy):
    factory = get_contract_factory("RenderProbe")
    contract = direct_deploy("contracts/render_probe.py")
    text = _file_text()
    expected = hashlib.sha256(text[:6000].encode("utf-8")).hexdigest()
    direct_vm.mock_web(COMPLETE_URL, {"status": 200, "body": text})
    contract.probe("p1", COMPLETE_URL, expected)
    direct_vm.run_validator()
    import json

    result = json.loads(contract.get_result("p1"))
    assert result["render_length"] == str(len(text[:6000]))
    assert result["render_sha256"] == expected
    assert result["render_matches"] == "true"
    assert contract.get_probe_count() == 1


def test_probe_rejects_duplicate_id(direct_vm, direct_deploy):
    contract = direct_deploy("contracts/render_probe.py")
    text = _file_text()
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    direct_vm.mock_web(COMPLETE_URL, {"status": 200, "body": text})
    contract.probe("dup", COMPLETE_URL, expected)
    try:
        contract.probe("dup", COMPLETE_URL, expected)
        assert False, "expected revert"
    except Exception:
        pass
