# Copyright 2026 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from datetime import datetime  # To set genesis block

import numpy as np  # To set effective number of samples (sampling noise)

from demo_configs import RANDOM_SEED

# ===================================================================================
#                      PoW Protocol Definitions
# ===================================================================================

EMPTY_QUANTUM_HASH = ""

# Large enough to outweigh any legitimate score.
MIN_SCORE = -(2 ** 14)

# ===================================================================================
#                      Unitary dynamics parameterization
# ===================================================================================
# Microseconds of evolution for the quench as executed on Advantage2_prototype2
DEFAULT_ANNEALING_TIME = 0.005
DEFAULT_CUBIC_LATTICE_SHAPE = (4, 4, 4)  # Default dimensions of dimerized cubic lattice.
DEFAULT_CUBIC_BOUNDARY_CONDITIONS = (False, False, True)  # Open, Open, Periodic
# Energy time rescalings required to emulate Advantage2_system2.6 at
# full problem energy scale. For systems of lower energy scale,
# anneals must be run for longer, for systems of higher energy scale, the
# problem Hamiltonian (energy) scale is reduced. See also the README Per-QPU Calibration.
DEFAULT_ENERGY_TIME_RESCALING = {
    "Advantage_system4.1": (1.0, 0.535),
    "Advantage_system6.4": (1.0, 0.488),
    "Advantage2_system1.12": (1.34, 1.0),
}
# ===================================================================================
#                      Global Trial Definitions
# ===================================================================================

MAX_MINING_ATTEMPTS = 100000
W_0_ALPHA = 0.0
DEFAULT_NUM_READS = 600  # NB - Smaller than arXiv:2503.14462.

MAX_INITIAL_NONCE = 2 ** 31
MAX_RNG_SEED_LEN = 6
init_rng = np.random.default_rng(RANDOM_SEED)
MANAGER_PRNG_SEED = int(init_rng.integers(0, 16 ** MAX_RNG_SEED_LEN - 1))

# Value used for Advantage_system4.1 in arXiv:2503.14462. Num reads was fixed to use 1 second of QPU
# access time (maximum for single-programming). For the simulated data, this is the relevant value.
SIMULATED_DATA_NUM_READS = 3860

# Set per the description of arXiv:arXiv:2503.14462 subject to two difference:
# (1) NUM_READS can be (is by default) smaller, so variance is scaled accordingly (conservatively:
# in line with sampling noise and ignoring control noise)
# (2) the generally available compute environment is different (measured d_Walpha=0.16 over 3
# solvers available January 21 2026, as opposed to 0.18 the 4 GA solvers at the time of the paper).
DELTA_W_0_ALPHA = 0.16 * np.sqrt(SIMULATED_DATA_NUM_READS / DEFAULT_NUM_READS)

GENESIS_BLOCK_TIMESTAMP = datetime.timestamp(datetime.fromisoformat("2025-01-01 00:00:00.000"))
GENESIS_BLOCK_PREV_HASH = "begin_blockchain"
GENESIS_MINER_ID = "genesis"

# ===================================================================================
#                      Directory Definitions
# ===================================================================================

REPO_PATH = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
STATIC_PATH = os.path.join(REPO_PATH, "static")
SIMULATED_PATH = os.path.join(STATIC_PATH, "simulated_data")
EMBEDDINGS_PATH = os.path.join(STATIC_PATH, "embeddings")
