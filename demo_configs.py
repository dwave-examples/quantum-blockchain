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

"""This file stores input parameters for the app and various configuration values that
will change the appearance (but generally not the functionality) of the demo as it runs."""

THUMBNAIL = "static/dwave_logo.svg"

APP_TITLE = "Quantum Blockchain"
MAIN_HEADER = "Quantum Blockchain"
DESCRIPTION = """\
A Proof of Quantum Work blockchain run on D-Wave Quantum Processing Units
"""

# Set to 'False' for testing code with the simulated solvers, which generate quantum hashes
# via statistical bootstrapping, which can be made fully repeatable when a PRNG_SEED is
# set (unlike the QPU solvers).
HIDE_SIMULATED_SOLVERS = False

# Changing this parameter to any number will make the simulation repeatable for simulated solvers.
# This will not remove the randomness from QPU measurements, so two QPU-based simulations may still
# diverge fairly quickly even with the same PRNG_SEED. If you want completely repeatable
# simulations, use the simulated solvers instead of the QPU solvers. Default set to 'None'.
PRNG_SEED = None

INTRO_TEXT = 'Select a number of miners and blocks and press "Begin Simulation".'
INTRO_SUBTEXT = "Results will display here while simulation is running."
LOADING_TEXT = "Generating graphs..."

# Minimum time for a single loop in "simulation" callback.
# If loops complete too quickly, display components won't update correctly.
MIN_SIMULATION_LOOP_TIME = 1.1

#######################################
# Graph Visual Elements              #
#######################################
TRUNK_POINT_COLOR = "#1F74DA"  # Blocks that are considered valid parts of the main chain
TRUNK_EDGE_COLOR = "#7AAEEC"  # Spiral segments connecting the valid blocks
ABANDONED_BRANCH_POINT_COLOR = "#D9610C"  # Blocks that are not considered valid
ABANDONED_BRANCH_EDGE_COLOR = "#F5924B"  # Spiral segments connecting invalid blocks
ACTIVE_BRANCH_POINT_COLOR = "#929292"  # Differentiates 'disputed' blocks from 'consensus' blocks
ACTIVE_BRANCH_EDGE_COLOR = "#C5C5C5"
MINING_BLOCK_BORDER_COLOR = "#17BEBB"  # Block that is currently (or most recently) being mined on
TRUNK_TIP_COLOR = "black"  # Block at the end of the trunk and other 'active' blocks in global view
GRAPH_RADIAL_LINE_COLOR = "#E6E6E6"  # Radial lines that help with graph readability
GRAPH_RADIAL_LINE_WIDTH = 0.7  # Width of the radial lines

GRAPH_POINT_MIN_SIZE = 5  # Points drawn nearer the center of the graph will be closer to this size
# Points drawn closer to the edge of the graph will be closer to this size
GRAPH_POINT_MAX_SIZE = 15

# Determines how large the branch points are relative to the trunk points.
GRAPH_BRANCH_POINT_SCALING = 0.65
GRAPH_MAX_POINTS_PER_REVOLUTION = 36  # Set to a multiple of 4 to keep dynamic adjustments nice
GRAPH_MIN_POINTS_PER_REVOLUTION = 8  # How many points are drawn in one full 'turn' of the spiral

# Controls how many straight segments are used to connect each graph point. More segments make a
# smoother curve. Dynamically adjusted to the size of the graph.
GRAPH_SEGMENTS_PER_REVOLUTION = GRAPH_MAX_POINTS_PER_REVOLUTION * 2

# Value to multiply each successive loop (in from the outermost one) of the spiral graph.
GRAPH_LOOP_SCALING = 2 / 3

# Furthest out on the chart area that points will be drawn. Value of 1 is the very edge.
GRAPH_MAX_RADIUS = 0.999

# How far in towards the next trunk section a branch can extend.
# Value of 1 is all the way to the trunk.
GRAPH_MAX_BRANCH_DISTANCE = 0.78


#######################################
# Sliders, buttons and option entries #
#######################################

# Controls the available range of miners that can be selected in the miner slider. Recommended
# values are min: "4", max: "28", step: "1" and "value": 7, which will be sufficient for most uses.
# Using fewer than 4 miners is possible but not recommended. Increasing the number of miners causes
# a proportional slowdown in the growth of the chain and the QPU use, as each miner must use a
# separate QPU call to validate. Maximum supported value is 255.
MINER_SLIDER = {"min": 4, "max": 28, "step": 1, "value": 7}

# Controls the values of the selector that chooses the length of the trial (the number of blocks
# mined before completion). Recommended values are min: "5", max: "600", step: "1" and "value": 20,
# which will be sufficient for most use cases. Trials of fewer than 5 blocks are rarely useful even
# for testing, while those exceeding 600 blocks will take more than an hour to complete under most
# settings. Interesting behavior can readily be observed in trials ranging from 20 to several
# hundred blocks. For decreased validation difficulties, it may require more blocks (and thus
# longer trials) for significant branching to occur, while for increased validation difficulties,
# it may take similarly take longer for forks to resolve and miners to reach consensus on the
# early portions of the chain.

NUM_BLOCKS = {"min": 5, "max": 600, "step": 1, "value": 20}

# The number of miner views that will be selectable in the UI. Each miner view will show the
# blockchain graph for a different miner in the trial; different graphs will include the same
# blocks and connections, but generally position and color them differently, reflecting the
# individual miner's opinion on the validity of those blocks. If this value is higher than
# the number of miners selected for a given simulation, there number of views will max out
# at the number of miners selected.

NUM_MINER_VIEWS = 3

MINER_NAMES = [f"Miner_{i}" for i in range(1, 256)]

#######################################
# Mining Difficulty Parameters        #
#######################################

# Length of the quantum hash. Determines how difficult it is to mine and validate a block, though
# increasing the value of ALLOWABLE_ERR will compensate for this. If this parameter is set to 0,
# the demo will function as a classical blockchain, with deterministic validation. Blockchains
# are generally stable but display interesting behavior (significant validation randomness) at
# values roughly in the range of 16-128, but this depends substantially on solver choices: using
# the default choice of "All QPU Solvers" will reduce this range substantially, for example. For
# larger values, stability can be maintained by increasing the ALLOWABLE_ERR parameter in
# proportion to the quantum hash length: roughly 1 point per 32-128 quantum hash bits. Using much
# larger values may cause modest increase in CPU use and memory footprint. Maximum supported value
# of 65536
QUANTUM_HASH_LENGTH = 64

# The number of single-bit errors validators will allow. Increasing this will cause validators to
# reject blocks more often, resulting in the chain branching more. For typical use this should
# be a non-negative integer much smaller than the quantum hash length. Maximum supported value
# of 255.
ALLOWABLE_ERR = 1

# Hardness block mining. At hardness 0, mining succeeds on every attempt. At hardness n, it takes
# (on average) 2^n attempts to mine a block. Increasing this will slow down the mining rate and
# make the simulation take longer. For most practical uses, values should range from 0 to 30. Max
# supported value of 255.
N_ZEROES = 0
