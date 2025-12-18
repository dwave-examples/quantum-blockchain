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
from src.utilities.display_update import render_graphs, render_miner_status
from src.utilities.mining_steps import mine_block

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(
    Output("round-order", "data"),
    Output("miner-status-data", "data"),
    Output("graph-data-temp", "data"),
    Output("block-broadcast", "data"),
    inputs = [
        Input("round-progress", "data"),
        State("graph-data", "data"),
        State("round-order", "data"),
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

    if round_progress == 0:
        miner_list = [MINER_NAMES[i] for i in range(num_miners)]
        miner_status_dict = {name: "" for name in miner_list}
        random.shuffle(miner_list)
        return miner_list, miner_status_dict, dash.no_update
    elif round_progress == 1:
        miner_id = "bob"
        previous_block_hash = "hash"
        new_block = mine_block(miner_id, previous_block_hash)
    elif round_progress > 1 and round_progress < num_miners:
        validator_id = round_order[round_progress]
        #TODO figure out how to get json_block
        return dash.no_update, validator_id
    else:
        return True, dash.no_update




# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Display Updates                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-display", "figure", allow_duplicate=True),
    Output("graph-wrapper", "className", allow_duplicate=True),
    Output("miner-table-head", "children", allow_duplicate=True),
    Output("miner-table-body", "children", allow_duplicate=True),
    inputs=[
            Input("graph-data", "data"),
            Input("miner-status", "data"),
            State("block-number-data", "data")
    ],
    prevent_initial_call=True,
)
def render_main_display(miner_status_data: dict, miner_graph_data: dict, block_num: int):
    """ """
    new_graph = render_graphs(miner_graph_data)
    miner_table_head, miner_table_body = render_miner_status(block_number=block_num, miner_status=miner_status_data)

    return "display-none", "display-none", new_graph, "", miner_table_head, miner_table_body

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

<<<<<<< HEAD
=======
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


>>>>>>> c5d6b317174ec13fc6616e3d67b0c8b4c17191aa
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
