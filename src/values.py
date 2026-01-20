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
DEFAULT_ANNEALING_TIME = (
    0.005  # Microseconds of evolution for the quench as executed on Advantage2_prototype2
)
DEFAULT_CUBIC_LATTICE_SHAPE = (4, 4, 4)  # Default dimensions of dimerized cubic lattice.
DEFAULT_CUBIC_BOUNDARY_CONDITIONS = (False, False, True)  # Open, Open, Periodic
# Energy time rescalings required to emulate Advantage2_system2.6 at
# full problem energy scale (see examples/). For systems of lower energy scale,
# anneals must be run for longer, for systems of higher energy scale, the
# problem Hamiltonian (energy) scale is reduced.
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


MAX_MINERS = 100 
MAX_BLOCKS = 4096
MINER_NAMES = [
    f"Miner_{i}" for i in range(1, MAX_MINERS + 1)
]  # May want to change this to an aliasing scheme later

DEFAULT_BLOCK_SCORE = 0.0
W_0_ALPHA = 0.0
DELTA_W_0_ALPHA = 0.18  # Reference paper value based on witness variance amongst 4 online general access solvers at hte time of the study.
DEFAULT_NUM_READS = 600  # NB - Smaller than the reference paper.
BOOTSTRAP_DATA_NUM_READS = 3860  # Reference paper value for the number of reads performed in estimation of offline witness data for Advantage_system4.1.
GENESIS_BLOCK_TIMESTAMP = datetime.timestamp(datetime.fromisoformat("2025-01-01 00:00:00.000"))
GENESIS_BLOCK_PREV_HASH = "begin_blockchain"


