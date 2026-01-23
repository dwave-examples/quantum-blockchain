from datetime import datetime  # To set genesis block

import numpy as np  # To set effective number of samples (sampling noise)

# TO DO, THIS FILE CONTAINS UNUSED CONSTANTS (APPEARING NOWHERE ELSE IN REPO). TO BE REMOVED
# SOME CONSTANTS NEED TO BE MOVED TO/FROM, OR IMPORTED TO/FROM demo_configs.py . MOST IMPORTANTLY CONFUSING AND DUPLICATED ONES, LIKE MAX_MINERS.

# ===================================================================================
#                      PoW Protocol Definitions
# ===================================================================================

EMPTY_QUANTUM_HASH = ""
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
MAX_MINING_ATTEMPTS = 100000
DEFAULT_BLOCK_SCORE = 0.0
W_0_ALPHA = 0.0
DEFAULT_NUM_READS = 600  # NB - Smaller than arXiv:2503.14462.
BOOTSTRAP_DATA_NUM_READS = 3860  # Value used for Advantage_system4.1 in arXiv:2503.14462. The num reads was fixed to use 1 second of QPU access time (maximum for single-programming). For the simulated data, this is the relevant value.
DELTA_W_0_ALPHA = 0.16 * np.sqrt(
    BOOTSTRAP_DATA_NUM_READS / DEFAULT_NUM_READS
)  # Set per the description of arXiv:arXiv:2503.14462 subject to two difference: (1) NUM_READS can be (is by default) smaller, so variance is scaled accordingly (conservatively: in line with sampling noise and ignoring control noise) (2) the generally available compute environment is different (measured d_Walpha=0.16 over 3 solvers available January 21 2026, as opposed to 0.18 the 4 GA solvers at the time of the paper).

GENESIS_BLOCK_TIMESTAMP = datetime.timestamp(datetime.fromisoformat("2025-01-01 00:00:00.000"))
GENESIS_BLOCK_PREV_HASH = "begin_blockchain"
GENESIS_MINER_ID = "genesis"
