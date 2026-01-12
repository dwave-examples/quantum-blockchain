from datetime import datetime

# ===================================================================================
#                      PoW Protocol Definitions
# ===================================================================================

BLOCK_REWARD = 1.0
MAX_BLOCK_SIZE = 128  # Currently unused as all our trial blocks are small. But we will need to define this eventually.
EMPTY_QUANTUM_HASH = ""
TRANSACTION_MAX_PRECISION = 8  # Good practice to define some maximum precision (i.e. some smallest unit of currency) to avoid validation problems due to rounding errors.
MIN_SCORE = -(
    2**14
)  # Large enough to outweigh any legitimate score, small enough to work on essentially all platforms.

# ===================================================================================
#                      Unitary dynamics parameterization
# ===================================================================================
DEFAULT_CUBIC_LATTICE_SHAPE = (4, 4, 4)  # Default dimensions of dimerized cubic lattice.
DEFAULT_CUBIC_BOUNDARY_CONDITIONS = (False, False, True)  # Open, Open, Periodic
# Energy time rescalings required to emulate Advantage2_system2.6 at
# full problem energy scale (see examples/). For systems of lower energy scale,
# we run longer anneals, for systems of higher energy scale, we reduce the
# problem Hamiltonian (energy) scale..
DEFAULT_ENERGY_TIME_RESCALING = {
    "Advantage2_prototype2.6": (
        1.0,
        1.0,
    ),  # Not generally available, available for resampling (simulated) experiments.
    "Advantage_system4.1": (1.0, 0.535),
    "Advantage_system6.4": (1.0, 0.488),
    "Advantage_system7.1": (
        1.0,
        0.456,
    ),  # Not generally available, available for resampling (simulated) experiments.
    "Advantage2_system1.10": (1.34, 1.0),
}
# ===================================================================================
#                      Global Trial Definitions
# ===================================================================================

MAX_OWNERS = 10
MAX_MINERS = 100  # TODO Generate more miner keys and increase the limit
MAX_BLOCKS = 4096
DEFAULT_TRANSACTION_FEE = 0.02
OWNER_NAMES = [
    f"Owner_{i}" for i in range(1, MAX_OWNERS + 1)
]  # Useful to have standard, human-readable IDs for Owners and Miners
MINER_NAMES = [
    f"Miner_{i}" for i in range(1, MAX_MINERS + 1)
]  # May want to change this to an aliasing scheme later

DEFAULT_BLOCK_SCORE = 0.0
CSV_LOG_SEP_CHAR = ","
MIN_SAFE_SOUNDNESS = 15  # Minimum soundness of blocks before owners will consider them "safe" to spend from: i.e. highly unlikely to be altered.
FIRST_KNOWN_NODE_HOSTNAME = "127.0.0.1:5000"
W_0_ALPHA = 0.0
DELTA_W_0_ALPHA = 0.18
DEFAULT_NUM_READS = 600
ADVANTAGE4_1_MAX_NUM_READS = 3860
GENESIS_BLOCK_TIMESTAMP = datetime.timestamp(datetime.fromisoformat("2025-01-01 00:00:00.000"))
GENESIS_BLOCK_PREV_HASH = "begin_blockchain"

# ===================================================================================
#                      Initialization Parameter Filenames
# ===================================================================================

MINER_PARAMS_FILENAME = "miner_params.json"
OWNER_PARAMS_FILENAME = "owner_params.json"
TRIAL_PARAMS_FILENAME = "global_trial_params.json"
POW_PARAMS_FILENAME = "pow_params.json"


# ===================================================================================
#                    Owner/Miner Data File Names
# ===================================================================================

BLOCKCHAIN_FILENAME = "blockchain.txt"
MEMPOOL_FILENAME = "mempool.txt"
SCORE_TREE_SUMMARY_FILENAME = "score_tree.txt"
SPENDING_QUEUE_FILENAME = "spending_queue.txt"
BROADCAST_LOG_FILE_SUFFIX = "_broadcast_log.csv"
