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

#######################################
# Sliders, buttons and option entries #
#######################################

# an example slider
DYNAMIC_PARAMS_PATH = os.path.join("src", "dynamic", "params")

GRAPHS_PATH = os.path.join("src", "dynamic", "graphs")

TRIAL_OUTPUTS_PATH = os.path.join("src", "trials", "outputs")

MINER_NUM_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "miners.txt")

BLOCK_NUM_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "blocks.txt")

TRIAL_INIT_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "trial_init.json")

PAUSE_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "pause.txt")

RESET_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "reset.txt")

STATIC_PARAMS_FILE = os.path.join("static", "defualt_params.json")

MINER_STATS_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "miner_stats.json")

BASE_MINER_GRAPH_FILE = os.path.join(GRAPHS_PATH, "miner_graph.png")

BASE_GLOBAL_GRAPH_FILE = os.path.join(GRAPHS_PATH, "global_graph.png")

EMBEDDINGS_DIRECTORY = os.path.join("src", "trials", "embeddings")

MIN_MINERS = 3

MAX_MINERS = 30

MINER_SLIDER = {
    "min": MIN_MINERS,
    "max": MAX_MINERS,
    "step": 1,
    "value": 7
}

# an example dropdown
DROPDOWN = ["Option 1", "Option 2"]

# an example checklist
CHECKLIST = ["Option 1", "Option 2"]

# an example radio list
RADIO = ["Option 1", "Option 2"]


# solver time limits in seconds (value means default)
SOLVER_TIME = {
    "min": 10,
    "max": 300,
    "step": 5,
    "value": 10,
}
