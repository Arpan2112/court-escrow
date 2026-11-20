"""Read the initial counters of the deployed CourtEscrow contracts on
GenLayer Studio Next (chain 61997). Read-only: uses a throwaway
in-memory account purely as the call sender; nothing is signed or sent.
"""
from genlayer_py import create_account, create_client
from genlayer_py.chains.studionet import CONSENSUS_DATA_CONTRACT, CONSENSUS_MAIN_CONTRACT
from genlayer_py.types import GenLayerChain, NativeCurrency

studio_dev = GenLayerChain(
    id=61997,
    name="GenLayer Studio Next",
    rpc_urls={"default": {"http": ["https://studio-dev.genlayer.com/api"]}},
    native_currency=NativeCurrency(name="GEN Token", symbol="GEN", decimals=18),
    block_explorers={"default": {"name": "GenLayer Explorer", "url": "https://explorer-studio-dev.genlayer.com"}},
    testnet=True,
    consensus_main_contract=CONSENSUS_MAIN_CONTRACT,
    consensus_data_contract=CONSENSUS_DATA_CONTRACT,
    fee_manager_contract=None,
    rounds_storage_contract=None,
    appeals_contract=None,
    staking_contract=None,
    default_number_of_initial_validators=5,
    default_consensus_max_rotations=3,
)

EVIDENCE_GUARD = "0x45f7Fe4DA9640457c9411b736E262675DF011A64"
DEAL_JUDGE = "0x605AEdC0f6F2a07d9CD581a2fDc1d140E2742DeB"  # patched build (mandatory evidence hash)

client = create_client(chain=studio_dev, account=create_account())
print("EvidenceGuard.get_check_count =", client.read_contract(address=EVIDENCE_GUARD, function_name="get_check_count", args=[]))
print("DealJudge.get_case_count =", client.read_contract(address=DEAL_JUDGE, function_name="get_case_count", args=[]))
