# Copyright 2024 D-Wave
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

""" This file stores input parameters for the app and various configuration values that
    will change the appearance (but generally not the functionality) of the demo as it runs."""

THUMBNAIL = "static/dwave_logo.svg"

APP_TITLE = "Quantum Blockchain"
MAIN_HEADER = "Quantum Blockchain"
DESCRIPTION = """\
A Proof of Quantum Work blockchain run on D-Wave Quantum Processing Units
"""

HIDE_SIMULATED_SOLVERS = True

INTRO_TEXT = 'Select a number of miners and blocks and press "Begin Simulation".'
INTRO_SUBTEXT = "Results will display here while simulation is running."
LOADING_TEXT = "Generating graphs..."

# Minimum time for a single loop in "simulation" callback.
# If loops complete too quickly, display components won't update correctly.
MIN_SIMULATION_LOOP_TIME = 1.1

#######################################
# Graph Visual Elements              #
#######################################
TRUNK_POINT_COLOR = "#1F74DA" # Blocks that are considered valid parts of the main chain
TRUNK_EDGE_COLOR = "#7AAEEC" # Spiral segments connecting the valid blocks
ABANDONED_BRANCH_POINT_COLOR = "#D9610C" # Blocks that are not considered valid
ABANDONED_BRANCH_EDGE_COLOR = "#F5924B" # Spiral segments connecting invalid blocks
ACTIVE_BRANCH_POINT_COLOR = "#929292" # Differentiates 'disputed' blocks from 'consensus' blocks
ACTIVE_BRANCH_EDGE_COLOR = "#C5C5C5" 
MINING_BLOCK_BORDER_COLOR = "#17BEBB" # Block that is currently (or most recently) being mined on
TRUNK_TIP_COLOR = "black" # Block at the end of the trunk and other 'active' blocks in global view
GRAPH_RADIAL_LINE_COLOR = "#E6E6E6" # Radial lines that help with graph readability
GRAPH_RADIAL_LINE_WIDTH = 0.7 # Width of the radial lines

GRAPH_POINT_MIN_SIZE = 5 # Points drawn nearer the center of the graph will be closer to this size
# Points drawn closer to the edge of the graph will be closer to this size
GRAPH_POINT_MAX_SIZE = 15

# Determines how large the branch points are relative to the trunk points.
GRAPH_BRANCH_POINT_SCALING = 0.65
GRAPH_MAX_POINTS_PER_REVOLUTION = 36  # Set to a multiple of 4 to keep dynamic adjustments nice
GRAPH_MIN_POINTS_PER_REVOLUTION = 8 # How many points are drawn in one full 'turn' of the spiral

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

MINER_SLIDER = {"min": 4, "max": 28, "step": 1, "value": 7}

NUM_BLOCKS = {"min": 3, "max": 600, "step": 1, "value": 20}

NUM_MINER_VIEWS = 3

MINER_NAMES = [f"Miner_{i}" for i in range(1, MINER_SLIDER["max"] + 1)]

#######################################
# Mining Difficulty Parameters        #
#######################################

# Length of the quantum hash. Determines how difficult it is to mine and validate a block.
QUANTUM_HASH_LENGTH = 64

# The number of single-bit errors validators will allow. Increasing this will cause validators to
# reject blocks more often, resulting in the chain branching more.
ALLOWABLE_ERR = 1

# Hardness block mining. At hardness 0, mining succeeds on every attempt. At hardness n,
# it takes (on average) 2^n attempts to mine a block. Increasing this will slow down the
# mining rate and make the simulation take longer.
N_ZEROES = 0
