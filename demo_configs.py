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
DYNAMIC_PARAMS_PATH = os.path.join("static", "params")

GRAPHS_PATH = os.path.join("static", "graphs")

TRIAL_OUTPUTS_PATH = os.path.join("src", "trials", "outputs")

PAUSE_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "pause.txt")

STATIC_PARAMS_FILE = os.path.join("static", "defualt_params.json")

MINER_STATS_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "miner_stats.json")

BASE_MINER_GRAPH_FILE = os.path.join(GRAPHS_PATH, "miner_graph.png")

BASE_GLOBAL_GRAPH_FILE = os.path.join(GRAPHS_PATH, "global_graph.png")

INTRO_SCREEN_FILE = os.path.join("static","pet1.jpg")

LOADING_SCREEN_FILE = os.path.join("static", "pet2.jpg")

EMBEDDINGS_DIRECTORY = os.path.join("src", "trials", "embeddings")

MIN_MINERS = 3

MAX_MINERS = 30

RUN_STATUS = {"Ready": True, "Running": True, "Paused": False}

MINER_SLIDER = {
    "min": MIN_MINERS,
    "max": MAX_MINERS,
    "step": 1,
    "value": 7
}
