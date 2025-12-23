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

from __future__ import annotations

import os
import json
import time
import math
import random
import copy

import dash
from dash import MATCH, ctx, html, Patch, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.express as px

from src.utilities.spiral_plotter import SpiralPlotter
from src.utilities.graph_processor import combine_dags, generate_graph_data
from src.agents.trial_manager import TrialManager
from src.agents.miner import Miner
from src.structures.block import Block
from src.values import MINER_NAMES #TODO move to DemoConstants

from demo_configs import MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_solvers import AVAILABLE_SOLVERS
from demo_objects import DEMO_MINER, TEST_TREE, DEMO_POW
from demo_constants import EMPTY_BLOCK_DICT, GENESIS_BLOCK
from demo_solvers import AVAILABLE_SOLVERS
from src.utilities.display_update import render_graphs, render_miner_status
from src.utilities.mining_steps import mine_block, validate_block

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(

    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    background=True,
    inputs=[
        Input("running-status", "data"),
        State("miner-slider", "value"),
        State("blocks-input", "value"),
        State("blockchain-structure-data", "data"),
        State("miner-score-data", "data"),
    ],
    running=[
        (Output("miner-slider", "disabled"), True, False),
        (Output("blocks-input", "disabled"), True, False), 
    ],
    progress=[
        Output("current-block-data", "data"),
        Output("miner-score-temp", "data"),
    ],
    cancel = [Input("reset-button", "n_clicks")],
    prevent_initial_call=True,
)
def simulation(
    update_current_block_data,
    running_status: bool,
    miner_slider_val: int,
    block_input_val: int,
    blockchain_structure: list,
    miner_scores: dict,
):
    """Runs the optimization and updates UI accordingly.

    This is the main function which is called when the ``Run Optimization`` button is clicked.
    This function takes in all form values and runs the optimization, updates the run/cancel
    buttons, deactivates (and reactivates) the results tab, and updates all relevant HTML
    components.

    Args:
        run_click: The (total) number of times the run button has been clicked.


    Returns:
        A NamedTuple (RunOptimizationReturn) containing all outputs to be used when updating the HTML
        template (in ``demo_interface.py``). These are:

            results: The results to display in the results tab.
            problem-details: List of the table rows for the problem details table.
    """

    # Only run optimization code if this function was triggered by a click on `run-button`.
    # Setting `Input` as exclusively `run-button` and setting `prevent_initial_call=True`
    # also accomplishes this.

    print("In simulation")

    if running_status == False or ctx.triggered_id != "running-status":
        raise PreventUpdate
    else: #TODO: add unpause logic
        num_blocks = block_input_val
        num_miners = miner_slider_val
        print(f"Starting TrialManager with {num_blocks} blocks and {num_miners} miners")

        manager = TrialManager(num_blocks=num_blocks, num_miners=num_miners, solver=AVAILABLE_SOLVERS[-1])

        print("TrialManager successfully instantiated.")

        while(manager.blocks_mined <= num_blocks):
            print("In main loop")
            mined, miner_id, block_score = manager.single_step()
            if mined:
                print("Mined")
                current_block = Block.from_json(manager.block_broadcast) #TODO optimize
                current_block_update = (current_block.hash, current_block.previous_hash)
                print(f"TrialManager at beginning of new round with {manager.blocks_mined} blocks mined.")
            else:
                print("Validated")
                current_block_update = dash.no_update
            score_data_list = [miner_id, block_score, mined]
            update_current_block_data((current_block_update, score_data_list))

            time.sleep(1.5)  
        
    return "", "display-none"


@dash.callback(
    Output("miner-score-data", "data", allow_duplicate=True),
    Input("miner-score-temp", "data"),
    prevent_initial_call=True,
)
def move_score_data(miner_score_in: list):
    """ """
    print("Moving score data")
    to_update = Patch()
    to_update[miner_score_in[0]].append(miner_score_in[1])
    return to_update

#==========================================================================================

@dash.callback(
    Output("blockchain-structure-data", "data"),
    Input("current-block-data", "data"),
    prevent_initial_call=True,
)
def update_blockchain_structure(block_data: tuple[str, str]):
    """ """
    print("Updating blockchain data")
    to_update = Patch()
    to_update.append(block_data)
    return to_update

#==========================================================================================



@dash.callback(
    Output("miner-status-data", "data"),
    inputs = [
        Input("miner-score-temp", "data"),
        State("miner-slider", "value"),
        ],
    prevent_initial_call=True,
)
def update_miner_status(miner_score_in: list, num_miners: int):
    print(f"Updating miner status data with {miner_score_in}")
    to_update = Patch()
    if miner_score_in[2] == True:
        for name in MINER_NAMES[:num_miners]:
            to_update.update({name: ""})
        to_update.update({miner_score_in[0]: "Mined"})
    else:
        if miner_score_in[1] > 0:
            miner_status = "Validated"
        else:
            miner_status = "Rejected"

        to_update.update({miner_score_in[0]: miner_status})
    return to_update

#==========================================================================================

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Display Updates                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dash.callback(
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("prelim-text", "className"),
    Output("miner-table-head", "children", allow_duplicate=True),
    Output("miner-table-body", "children", allow_duplicate=True),
    inputs=[
            Input("miner-status-data", "data"),
            State("blockchain-structure-data", "data"),
    ],
    prevent_initial_call=True,
)
def render_miner_status_table(miner_status_data: dict, blockchain_structure_data: list):
    """ """

    print("Received miner status update")
    block_number = len(blockchain_structure_data)
    print(f"Drawing miner status table for block number {block_number}")

    miner_table_head, miner_table_body = render_miner_status(block_number, miner_status_data)
    return "", "display-none", miner_table_head, miner_table_body


#=======================================================================================

def dummy():
    """
@dash.callback(
    Output("graph-data", "data", allow_duplicate=True),
    Input("graph-data-temp", "data"),
    prevent_initial_call=True,
)
def move_graph_data(graph_data_in: list):

    to_update = Patch()
    miner_id = 0
    graph_data_out = graph_data_in
    to_update.update({f"Miner {miner_id + 1}":graph_data_out})
    return to_update
"""
    pass
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Button Triggers                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def run_simulation(run_click: int):
    print("In run_simulation")

    return "display-none", "", True, "display-none"

#========================================================================================

@dash.callback(
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def pause_simulation(pause_click: int):

    return "", "display-none", False

#========================================================================================

@dash.callback(
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def resume_simulation(pause_click: int):
    return "display-none", "", True

#========================================================================================
@dash.callback(
    
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    inputs=[
        Input("reset-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def reset_simulation(reset_click: int):

    return (
        "", #Intro text
        "display-none", #Loading text
        "display-none", #Miner Graph
        "",             #Run Button
        "display-none", #Reset & Resume Buttons
        False,
        0
    )

#=======================================================================================

@dash.callback(
    Output({"type": "to-collapse-class", "index": MATCH}, "className"),
    Output({"type": "collapse-trigger", "index": MATCH}, "aria-expanded"),
    inputs=[
        Input({"type": "collapse-trigger", "index": MATCH}, "n_clicks"),
        State({"type": "to-collapse-class", "index": MATCH}, "className"),
    ],
    prevent_initial_call=True,
)
def toggle_left_column(collapse_trigger: int, to_collapse_class: str) -> tuple[str, str]:
    """Toggles a 'collapsed' class that hides and shows some aspect of the UI.

    Args:
        collapse_trigger (int): The (total) number of times a collapse button has been clicked.
        to_collapse_class (str): Current class name of the thing to collapse, 'collapsed' if not
            visible, empty string if visible.

    Returns:
        str: The new class name of the thing to collapse.
        str: The aria-expanded value.
    """

    classes = to_collapse_class.split(" ") if to_collapse_class else []
    if "collapsed" in classes:
        classes.remove("collapsed")
        return " ".join(classes), "true"
    return to_collapse_class + " collapsed" if to_collapse_class else "collapsed", "false"
