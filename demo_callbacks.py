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

import dash
from dash import MATCH, ctx, html, Patch, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.express as px

from src.utilities.spiral_plotter import SpiralPlotter
from src.utilities.graph_processor import combine_dags, generate_graph_data
from src.agents.trial_manager import TrialManager
from src.structures.block import Block
from src.values import MINER_NAMES #TODO move to DemoConstants

from demo_configs import MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_solvers import AVAILABLE_SOLVERS
from demo_objects import DEMO_MINER, TEST_TREE

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(
    Output("round-reset-flag", "data"),
    Output("validator-id", "data"),
    inputs = [
        Input("round-progress", "data"), #TODO create
        State("round-order", "data"), #TODO make sure this works
        State("pause-status", "data"),
        State("running-status", "data"),
        State("miner-slider", "value"),
    ],
    prevent_initial_call=True,
)
def round_manager(round_progress: int, round_order: list, pause_status: bool, running_status: bool, num_miners: int):
    """
     Triggered By: Run Button, Resume Button, Round Progress Update

     Triggers: set_round_order, validate_block (mine_block?)
       """

    #if round_progress == 0:
     #   miner_id = round_order[0]
     #   return dash.no_update, miner_id, dash.no_update
    if round_progress >= 1 and round_progress < num_miners:
        validator_id = round_order[round_progress]
        return dash.no_update, validator_id
    else:
        return True, dash.no_update


#=======================================================================================

@dash.callback(
    Output("round-order", "data"),
    Output("miner-status", "data"),
    Input("round-reset-flag", "data"),
    State("miner-slider", "value"),
    prevent_initial_call=True,
)
def set_round_order(round_reset_flag: bool, num_miners: int) -> tuple[list[str], dict[str, str]]:
    """ """

    miner_list = [MINER_NAMES[i] for i in range(num_miners)]
    miner_status_dict = {name: "" for name in miner_list}
    random.shuffle(miner_list)
    return miner_list, miner_status_dict #TODO consider adding miner table update

#=======================================================================================

@dash.callback(
    Output("miner-id", "data"),
    Input("round-order", "data"),
    prevent_initial_call=True,
)
def set_miner(round_order: list):
    """ Tak"""

    active_miner = round_order[0]

    return active_miner

#=======================================================================================

@dash.callback(
    Output("block-broadcast", "data"),
    Output("round-progress", "data", allow_duplicate=True),
    Output("miner-data-temp", "data", allow_duplicate=True),
    Input("miner-id", "data"),
    prevent_initial_call=True,
)
def mine_block(miner_id: str):
    """ Triggered By: Miner ID
    
        Triggers: """

    #TODO figure out how miner knows which block to mine
    prev_hash = "some_placeholder_bs"
    new_block = DEMO_MINER.assemble_new_block(previous_block_hash=prev_hash)
    new_block._header["miner_id"] = miner_id
    mined_block=""
    mine_success = False
    while not mine_success:
        mined_block, mine_success, _ = DEMO_MINER.attempt_mine(new_block)

    return mined_block, 1, {miner_id: "Mined"}

#=======================================================================================

@dash.callback(
    Output("score-broadcast", "data", allow_duplicate=True),
    Output("round-progress", "data", allow_duplicate=True),
    Output("miner-data-temp", "data", allow_duplicate=True),
    Input("validator-id", "data"),
    State("mined-block", "data"),
    State("round-order", "data"),
    prevent_initial_call=True,
)
def validate_block(validator_id: str, mined_block_json: str, round_order: list[str]):
    """ Tak"""

    score = DEMO_MINER.receive_block(mined_block_json)
    round_position = round_order.index(validator_id)
    if score > 0:
        validator_outcome = "Validated"
    else:
        validator_outcome = "Rejected"

    #TODO set up store for scores
    return score, round_position + 1, {validator_id: validator_outcome}

#========================================================================================

def dummy():
    """

@dash.callback(

    Output("block-number-data-temp", "data"),
    Output("miner-table-head", "children"),
    Output("miner-table-body", "children"),
    Output("graph-data-temp", "data"),
    inputs=[
        Input("display-update", "n_intervals"),
        State("miner-slider", "value"),
        State("block-number-data", "data"),
        State("run-status", "data"),
        State("pause-status", "data"),
    ],
    running=[
        (Output("miner-slider", "disabled"), True, False),
        (Output("blocks-input", "disabled"), True, False), 
    ],

    prevent_initial_call=True,
)
def advance_simulation(
    n_intervals: int,
    miner_slider_val: int,
    block_input_val: int,
    run_status: bool,
    pause_status: bool,
):
    Runs the optimization and updates UI accordingly.

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
   

    num_blocks = block_input_val
    num_miners = miner_slider_val
    dummy_graph_data = generate_graph_data(TEST_TREE)

    if run_status == False or pause_status == True:
        miner_status_list = ["waiting" for _ in range(num_miners)]
        placeholder_head, placeholder_body = render_miner_status(0, miner_status_list)
        return block_input_val, placeholder_head, placeholder_body, dummy_graph_data
    else:

        miner_status_list = ["thinking" for _ in range(num_miners)]
        miner_table_head, miner_table_body = render_miner_status(miner_status=miner_status_list, block_number=num_blocks)
        print(f"Advancing simulation with {num_blocks} blocks!")

        return num_blocks + 1, miner_table_head, miner_table_body, dummy_graph_data
    
"""
    pass
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Display Updates                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def render_miner_status(block_number: int, miner_status: dict):
    """ Renders the status of the miners in the current trial. Each miner will be named
        "Miner n" where n is one more than their ID in TrialManager (because numbering 
        starting from Miner 0 is less aesthetic), and will have a status of "Mining, Mined,
        Validating, Valid" if they've started acting this round, or "..." if not.

    Args:
        n_intervals (unused)

    Returns:
        str: miner status table
    """

    print(miner_status)

    if "Mined" in miner_status.values():
        round_state = "Validating"
    else:
        round_state = "Mining"
    table_header = round_state + f" Block {block_number}"

    num_miners = len(miner_status)
    miner_entries = [(key, val) for key, val in miner_status.items()]
    columns = min(math.ceil(num_miners / MAX_MINER_ROWS), MAX_MINER_COLUMNS)

    table_rows = []
    new_row = []
    for i in range(0, num_miners):
        new_row.append(html.Td(miner_entries[i][0]))
        new_row.append(html.Td(miner_entries[i][1]))
        if len(new_row) >= 2*columns:
            table_rows.append(html.Tr(new_row))
            new_row = []
    if len(new_row) > 0:
        table_rows.append(html.Tr(new_row))

    return table_header, table_rows

#==========================================================================================

@dash.callback(
    Output("miner-status-data", "data", allow_duplicate=True),
    Input("miner-data-temp", "data"),
    prevent_initial_call=True,
)
def move_miner_data(miner_data_in: list):
    """ """
    to_update = Patch()
    to_update.update(miner_data_in)
    return to_update

#=======================================================================================

@dash.callback(
    Output("miner-table-head", "children"),
    Output("miner-table-body", "children"),
    Input("miner-status_data", "data"),
    State("block-number-data", "data"),
    prevent_initial_call=True,
)
def update_miner_table(miner_data: dict, block_num: int):
    """ """
    table_head, table_body = render_miner_status(block_number=block_num, miner_status=miner_data)

#=======================================================================================

@dash.callback(
    Output("graph-data", "data", allow_duplicate=True),
    Input("graph-data-temp", "data"),
    prevent_initial_call=True,
)
def move_graph_data(graph_data_in: list):
    """ """
    to_update = Patch()
    miner_id = 0
    graph_data_out = graph_data_in
    to_update.update({f"Miner {miner_id + 1}":graph_data_out})
    return to_update

#=======================================================================================


@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-display", "figure", allow_duplicate=True),
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    inputs=[
        #Input("block-number-data", "data"),
        #Input("view-select", "value"),
        #State("run-status", "data"),
        Input("graph-data", "data")
    ],
    prevent_initial_call=True
)
def render_graphs(graph_data: dict):
    """Updates the display for the miner tab, showing the graph
        of the current chain state if it is available.

        The file naming logic here is somewhat convoluted because it has to be:
        the html.Img object seems to cache copies of the last several images it
        has displayed. If you don't give it a new name, it will keep displaying
        the older image. So we rotate through a sequence of filenames.

        Args:
            miner-graph-update: interval set to check if there is anything to update
            run-status: if run status alters, display should alter
            tabs: should automatically render on switching tabs.

        Returns:
            graph-file"""
   

    #if not run_status["Running"] or num_blocks < 2:
    #    return "display-none", "", None, "display-none"
    #else:
    if len(graph_data) > 0:
        plotter = SpiralPlotter()
        #graph_data = graph_data["Miner 1"]
        graph_data = generate_graph_data(TEST_TREE)
        print(graph_data)
        plotter.import_plotting_data(tree_data=graph_data, num_nodes=8)
        plot_data = plotter.plot_spiral()
        fig = go.Figure(plot_data)

        fig.update_layout( #TODO move to configs and figure out how to use relative units for graph size
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
            paper_bgcolor="white",
            plot_bgcolor="white",
        )

        return "display-none", "display-none", fig, ""
    
    else:
        return "display-none", "display-none", None, ""


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Button Triggers                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("pause-status", "data", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def pause_simulation(pause_click: int):

    return "", "display-none", True

#========================================================================================

@dash.callback(
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("pause-status", "data", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def resume_simulation(pause_click: int):
    return "display-none", "", False

#========================================================================================
@dash.callback(
    
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-resume-buttons", "className", allow_duplicate=True),
    Output("run-status", "data", allow_duplicate=True),
    Output("block-number-data", "data", allow_duplicate=True),
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

#========================================================================================

@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("run-status", "data", allow_duplicate=True),
    Output("view-select", "options"),
    Output("graph-data", "data", allow_duplicate=True),
    Output("miner-status-data", "data", allow_duplicate=True),
    Output("stopping-block", "data"),
    inputs=[
        Input("run-button", "n_clicks"),
        State("miner-slider", "value"),
        State("blocks-input", "value")
    ],
    prevent_initial_call=True,
)
def run_simulation(run_click: int, num_miners: int, num_blocks: int):
    miner_opts = ["Global View"]
    miner_opts += [f"Miner {i+1}" for i in range(num_miners)]
    miner_data = {miner: [] for miner in miner_opts}
    miner_status_dict = {MINER_NAMES[i]: "" for i in range(num_miners)}
    return (
        "display-none",
        "",
        "",
        "display-none",
        True,
        miner_opts,
        miner_data,
        miner_status_dict,
        num_blocks
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
