#!/usr/bin/env python3
"""CourtEscrow demo CLI — GenLayer side (DealJudge on Studio Next, 61997).

Drives one DealJudge case through its lifecycle using the project's
demo operator account (.demo/genlayer-demo-account.json, never committed).
In this demo the operator account plays both parties on GenLayer
(buyer == seller == operator); the escrow side on Base Sepolia uses
three distinct accounts. See docs/ARCHITECTURE.md.

Usage:
  genlayer_case.py open    <case_id> <agreement> <criteria_json>
  genlayer_case.py deliver <case_id> <manifest> <evidence_url> <evidence_sha256_hex>
  genlayer_case.py accept  <case_id>
  genlayer_case.py dispute <case_id> <reason>
  genlayer_case.py resolve <case_id>
  genlayer_case.py get     <case_id>
  genlayer_case.py count

Every write waits for FINALIZED and prints one JSON line.
"""
import hashlib
import json
import sys
import urllib.request

sys.path.insert(0, "scripts")
from read_counts import studio_dev  # noqa: E402  (chain definition only)

from eth_account import Account  # noqa: E402
from genlayer_py import create_client  # noqa: E402
from genlayer_py.types import TransactionStatus  # noqa: E402

DEAL_JUDGE = "0xC4feD4c49aE86Ec1A9803694A0EA0E677a15C2F3"


def load_client():
    with open(".demo/genlayer-demo-account.json") as f:
        rec = json.load(f)
    account = Account.from_key(rec["private_key"])
    return create_client(chain=studio_dev, account=account), account.address


def write(client, fn, args):
    tx = client.write_contract(address=DEAL_JUDGE, function_name=fn, args=args)
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx, status=TransactionStatus.FINALIZED, retries=60
    )
    status = receipt["status"] if isinstance(receipt, dict) else str(receipt)
    print(json.dumps({"tx": tx, "status": str(status), "fn": fn}))
    return tx


def main():
    cmd = sys.argv[1]
    client, me = load_client()
    if cmd == "open":
        case_id, agreement, criteria_json = sys.argv[2], sys.argv[3], sys.argv[4]
        write(client, "open_case", [case_id, me, me, agreement, criteria_json])
    elif cmd == "deliver":
        case_id, manifest, url, ev_hash = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
        delivery_hash = hashlib.sha256(manifest.encode()).hexdigest()
        write(client, "submit_delivery", [case_id, manifest, delivery_hash, url, ev_hash])
    elif cmd == "accept":
        write(client, "accept_delivery", [sys.argv[2]])
    elif cmd == "dispute":
        write(client, "raise_dispute", [sys.argv[2], sys.argv[3]])
    elif cmd == "resolve":
        write(client, "resolve_case", [sys.argv[2]])
    elif cmd == "get":
        case = client.read_contract(address=DEAL_JUDGE, function_name="get_case", args=[sys.argv[2]])
        print(json.dumps(case, default=str))
    elif cmd == "count":
        n = client.read_contract(address=DEAL_JUDGE, function_name="get_case_count", args=[])
        print(json.dumps({"case_count": n}))
    elif cmd == "pin":
        # Print the sha256 the contract will compute for an evidence URL:
        # sha256 of the fetched text truncated to 6000 chars.
        with urllib.request.urlopen(sys.argv[2], timeout=30) as r:
            text = r.read().decode("utf-8")
        print(json.dumps({"sha256": hashlib.sha256(text[:6000].encode()).hexdigest(), "chars": len(text)}))
    else:
        raise SystemExit(f"unknown command {cmd}")


if __name__ == "__main__":
    main()
