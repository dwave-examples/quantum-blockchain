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

"""This file stores input parameters for the app."""

import os
from collections import namedtuple

import plotly.express as px

# THEME_COLOR is used for the button, text, and banner and should be dark
# and pass accessibility checks with white: https://webaim.org/resources/contrastchecker/
# THEME_COLOR_SECONDARY can be light or dark and is used for sliders, loading icon, and tabs
THEME_COLOR = "#074C91"  # D-Wave dark blue default #074C91
THEME_COLOR_SECONDARY = "#2A7DE1"  # D-Wave blue default #2A7DE1

THUMBNAIL = "static/dwave_logo.svg"

APP_TITLE = "Quantum Blockchain"
MAIN_HEADER = "Quantum Blockchain"
DESCRIPTION = """\
A Proof of Quantum Work blockchain run on D-Wave Quantum Processing Units
"""
INTRO_TEXT = 'Select a number of miners and blocks and press "Begin Simulation".'
INTRO_SUBTEXT = "Results will display here while simulation is running."
LOADING_TEXT = "Generating graphs..."

#######################################
# Graph Visual Elements              #
#######################################
TRUNK_POINT_COLOR = "#1F74DA"
TRUNK_EDGE_COLOR = "#7AAEEC"
ABANDONED_BRANCH_POINT_COLOR = "#D9610C"
ABANDONED_BRANCH_EDGE_COLOR = "#F5924B"
ACTIVE_BRANCH_POINT_COLOR = "#929292"
ACTIVE_BRANCH_EDGE_COLOR = "#D6D6D6"
MINING_BLOCK_BORDER_COLOR = "#3B7922"
TRUNK_TIP_COLOR = "black"
GRAPH_RADIAL_LINE_COLOR = "grey"
GRAPH_RADIAL_LINE_WIDTH = 0.5

GRAPH_POINT_MIN_SIZE = 5
GRAPH_POINT_MAX_SIZE = 15
GRAPH_BRANCH_POINT_SCALING = (
    0.65  # Determines how large the branch points are relative to the trunk points.
)
GRAPH_MAX_POINTS_PER_REV = 36  # Only set to a multiple of 4 to keep dynamic adjustments nice
GRAPH_MIN_POINTS_PER_REV = 8
GRAPH_SEGS_PER_REV = GRAPH_MAX_POINTS_PER_REV * 2

GRAPH_LOOP_SCALING = (
    2 / 3
)  # Value to multiply each successive loop (in from the outermost one) of the spiral graph.
GRAPH_MAX_RADIUS = (
    0.999  # Furthest out on the chart area that points will be drawn. Value of 1 is the very edge.
)
GRAPH_MAX_BRANCH_DISTANCE = 0.78  # How far in towards the next trunk section a branch can extend. Value of 1 is all the way to the trunk.
#######################################
# Sliders, buttons and option entries #
#######################################

MIN_MINERS = 3

MAX_MINERS = 28

DEFAULT_TABLE_HEADER = "Initializing..."

DEFAULT_TABLE_BODY = ""

HIDE_BOOTSTRAP_SOLVERS = False

MINER_SLIDER = {"min": MIN_MINERS, "max": MAX_MINERS, "step": 1, "value": 7}

NUM_BLOCKS = {"min": 3, "max": 300, "step": 1, "value": 10}

ViewOption = namedtuple("ViewOption", ["menu_select", "graph_name", "wrapper_name", "miner_number"])

VIEW_OPTS = [
    ViewOption(
        menu_select="Global View",
        graph_name="global_view_graph",
        wrapper_name="global_view_wrapper",
        miner_number=-1,
    ),
    ViewOption(
        menu_select="Miner 1 View",
        graph_name="miner_1_view_graph",
        wrapper_name="miner_1_view_wrapper",
        miner_number=0,
    ),
    ViewOption(
        menu_select="Miner 2 View",
        graph_name="miner_2_view_graph",
        wrapper_name="miner_2_view_wrapper",
        miner_number=1,
    ),
    ViewOption(
        menu_select="Miner 3 View",
        graph_name="miner_3_view_graph",
        wrapper_name="miner_3_view_wrapper",
        miner_number=2,
    ),
]


#######################################
# Mining Difficulty Parameters        #
#######################################
QUANTUM_HASH_LENGTH = 128
ALLOWABLE_ERR = 4
N_ZEROES = 0
