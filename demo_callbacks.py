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
import time
import copy
import json


import dash
import asyncio
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

from demo_solvers import AVAILABLE_SOLVERS
from demo_objects import DEMO_MINER, TEST_TREE, DEMO_POW
from demo_constants import EMPTY_BLOCK_DICT, GENESIS_BLOCK, GENESIS_BLOCKNODE
from demo_solvers import AVAILABLE_SOLVERS
from src.utilities.display_update import render_graphs, render_miner_status
from src.structures.block_score_tree import BlockScoreTree, BlockNode


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def reconstruct_score_tree(node_list: list[dict], miner_id: str) -> BlockScoreTree:
    tree = BlockScoreTree()
    for block_entry in node_list:
        score = block_entry["scores"][miner_id]
        block = Block.from_json(block_entry["block_json"])
        tree.add_block(block_hash=block.hash, prev_block_hash=block.previous_hash, block_score=score)

    if tree.high_score > tree.trunk.tip.total_score:
        strongest_branch = tree.hash_to_branch_lookup[tree.strongest_block_hash]
        tree.promote_to_trunk(strongest_branch)

    return tree

@dash.callback(

    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    background=True,
    inputs=[
        Input("running-status", "data"),
        State("miner-slider", "value"),
        State("blocks-input", "value"),
        State("blockchain-structure-data", "data"),
    ],
    running=[
        (Output("miner-slider", "disabled"), True, False),
        (Output("blocks-input", "disabled"), True, False), 
    ],
    progress=[
        Output("current-block-data", "data"),
    ],
    cancel = [Input("reset-button", "n_clicks")],
    prevent_initial_call=True,
)
async def simulation(
    update_current_block_data,
    running_status: bool,
    miner_slider_val: int,
    block_input_val: int,
    blockchain_structure: list,
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

        block_dict_template = {"block_json":"", "block_number": 0, "scores": {}, "miner_id": ""}
        current_block_dict = copy.deepcopy(block_dict_template)

        while(manager.blocks_mined <= num_blocks):

            mined, miner_id, block_score = manager.single_step()
            if mined:
                await asyncio.sleep(0.8)
                current_block_dict = copy.deepcopy(block_dict_template)
                current_block_dict["block_number"] = manager.blocks_mined
                current_block_dict["block_json"] = manager.block_broadcast
                current_block_dict["miner_id"] = miner_id
                print(f"In main loop, current block dict is {current_block_dict}")
                print(f"TrialManager at beginning of new round with {manager.blocks_mined} blocks mined.")
                print(f"Miner_1 tip score is {manager.miners[MINER_NAMES[0]].blockchain.trunk.tip.total_score}")
            else:
                current_block_dict["new"] = False

            current_block_dict["scores"][miner_id] = block_score

            update_current_block_data(current_block_dict)

            await asyncio.sleep(0.25)
        
    return "", "display-none"


#==========================================================================================


@dash.callback(
    Output("blockchain-structure-data", "data"),
    inputs = [
        Input("current-block-data", "data"),
    ],
    prevent_initial_call=True,
)
async def update_blockchain_data(block_data: dict):
    """ """


    block_number = block_data["block_number"]
    print(f"Updating blockchain data for block {block_number}")
    to_update = Patch()
    to_update[block_number-1] = block_data
    return to_update

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
    Output("miner-graph-display", "figure"),
    inputs = [
        Input("blockchain-structure-data", "data"),
        State("miner-slider", "value"),
        ],
    prevent_initial_call=True,
)
async def update_main_display(blockchain_structure_data: list, num_miners: int):

    current_view = MINER_NAMES[0] #TODO replace with input

    #Get blockchain data
  
    block_number = blockchain_structure_data.index(None)
    last_used_index = block_number -1
    if last_used_index < 1:
        raise PreventUpdate()
    else:
        print(f"Drawing graph for block number {last_used_index+1}")

    current_blockchain_data = blockchain_structure_data[:last_used_index+1]
    current_block_data = current_blockchain_data[-1]
    mining_id = current_block_data["miner_id"]

    #Compute miner status table

    miner_status_dict = {MINER_NAMES[i]:"" for i in range(num_miners)}
    for miner_id, score in current_block_data["scores"].items():
        if score > 0:
            status = "Validated"
        else:
            status = "Rejected"
        miner_status_dict[miner_id] = status
    miner_status_dict[mining_id] = "Mined"
    miner_table_head, miner_table_body = render_miner_status(block_number, miner_status_dict)

    #Draw graph
    #TODO add logic to check if graph update is necessary 

    miner_scores_dict = current_block_data["scores"]
    finished_miners = list(miner_scores_dict.keys())
    last_miner = finished_miners[-1]
    
    if current_view == last_miner:
        miner_tree = reconstruct_score_tree(current_blockchain_data, current_view)
        plotter = SpiralPlotter()
        miner_fig = plotter.create_plot_from_tree(miner_tree)

        miner_fig.update_layout( #TODO move to configs and figure out how to use relative units for graph size
            autosize=False,
            width=700,
            height=700,
            showlegend = False,
            xaxis = dict(showticklabels=False),
            yaxis = dict(showticklabels=False),
            margin=dict(
                l=0,
                r=0,
                b=0,
                t=0,
                pad=4
            ),
            paper_bgcolor="White",
            plot_bgcolor="White",
        )
    else:
        miner_fig = dash.no_update

    return "", "display-none", miner_table_head, miner_table_body, miner_fig



#=======================================================================================
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
    Output("blockchain-structure-data", "data", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
        State("blocks-input", "value"),
    ],
    prevent_initial_call = True
)
def run_simulation(run_click: int, num_blocks: int):
    print("In run_simulation")
    blockchain_init = [None for _ in range(num_blocks+3)]
    return "display-none", "", True, "display-none", blockchain_init

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
