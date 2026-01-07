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
A simulated blockchain using a Proof of Quantum Work algorithm run on a D-Wave Quantum Annealer
"""
INTRO_TEXT = "Select a number of miners and blocks and press \"Begin Simulation\"."
INTRO_SUBTEXT = "Results will display here while simulation is running."
LOADING_TEXT = "Generating graphs..."

GRAPH_POINT_MIN_SIZE = 5
GRAPH_POINT_MAX_SIZE = 15
GRAPH_MAX_POINTS_PER_REV = 36
GRAPH_MIN_POINTS_PER_REV = 8
GRAPH_SEGS_PER_REV = GRAPH_MAX_POINTS_PER_REV*2 
#######################################
# Sliders, buttons and option entries #
#######################################

MIN_MINERS = 3 

MAX_MINERS = 44

MAX_MINER_ROWS = 28

MAX_MINER_COLUMNS = 2

DEFAULT_TABLE_HEADER = "Initializing..."

DEFAULT_TABLE_BODY = ""

GRAPH_WIDTH = 1000 #width of graph and load screen elements

DISPLAY_REFRESH_RATE = 300 #In milliseconds. How quickly graphs and status tables check for new outputs to display

MINER_SLIDER = {
    "min": MIN_MINERS,
    "max": MAX_MINERS,
    "step": 1,
    "value": 7
}

NUM_BLOCKS = {
    "min": 2,
    "max": 200,
    "step": 1,
    "value": 10
}

TRUNK_COLOR_SCALE = px.colors.sequential.Bluered
BRANCH_COLOR_SCALE = px.colors.sequential.Aggrnyl