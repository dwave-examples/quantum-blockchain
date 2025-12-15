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

import os, json, time, math

import dash
from dash import MATCH, ctx, html, Patch, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.express as px

#from spiral_plotter import SpiralPlotter
from src.agents.trial_manager import TrialManager

from demo_interface import generate_view_select

from demo_configs import MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_constants import (
    PAUSE_FILE,
    STATIC_PARAMS_FILE, 
    EMBEDDINGS_DIRECTORY,
)
from demo_solvers import AVAILABLE_SOLVERS

def render_miner_status(block_number: int, miner_status: list):
    """ Renders the status of the miners in the current trial. Each miner will be named
        "Miner n" where n is one more than their ID in TrialManager (because numbering 
        starting from Miner 0 is less aesthetic), and will have a status of "Mining, Mined,
        Validating, Valid" if they've started acting this round, or "..." if not.

    Args:
        n_intervals (unused)

    Returns:
        str: miner status table
    """


    if "Mined" in miner_status:
        round_state = "Validating"
    else:
        round_state = "Mining"
    table_header = round_state + f" Block {block_number}"

    num_miners = len(miner_status)
    miner_names = [f"Miner {i}" for i in range(1, num_miners + 1)]
    columns = min(math.ceil(num_miners / MAX_MINER_ROWS), MAX_MINER_COLUMNS)

    table_rows = []
    new_row = []
    for i in range(0, num_miners):
        new_row.append(html.Td(miner_names[i]))
        new_row.append(html.Td(miner_status[i]))
        if len(new_row) >= 2*columns:
            table_rows.append(html.Tr(new_row))
            new_row = []
    if len(new_row) > 0:
        table_rows.append(html.Tr(new_row))

    return table_header, table_rows

#=======================================================================================

def update_simulation_data(miner_graph_data, blocknum, miner_status):
    """ Pass-through function used by simulation() callback to pass progress data
        to various componenets mid-run. """
    table_header, table_rows = render_miner_status(blocknum, miner_status)
    return miner_graph_data, table_header, table_rows

#=======================================================================================

@dash.callback(
    Output({"type": "to-collapse-class", "index": MATCH}, "className"),
    inputs=[
        Input({"type": "collapse-trigger", "index": MATCH}, "n_clicks"),
        State({"type": "to-collapse-class", "index": MATCH}, "className"),
    ],
    prevent_initial_call=True,
)
def toggle_left_column(collapse_trigger: int, to_collapse_class: str) -> str:
    """Toggles a 'collapsed' class that hides and shows some aspect of the UI.

    Args:
        collapse_trigger (int): The (total) number of times a collapse button has been clicked.
        to_collapse_class (str): Current class name of the thing to collapse, 'collapsed' if not
            visible, empty string if visible.

    Returns:
        str: The new class name of the thing to collapse.
    """

    classes = to_collapse_class.split(" ") if to_collapse_class else []
    if "collapsed" in classes:
        classes.remove("collapsed")
        return " ".join(classes)
    return to_collapse_class + " collapsed" if to_collapse_class else "collapsed"


#=======================================================================================

@dash.callback(
    Output("graph-data", "data", allow_duplicate=True),
    Input("graph-data-temp", "data"),
    prevent_initial_call=True,
)
def move_graph_data(graph_data_in: list):
    """ Takes the graph data for a single miner passed into the temp store by the
        update_simulation_data function and Patches it into the store with the graph
        data for all of the miners. Must be done this way because Patch won't work
        properly if returned direction from update_simulation."""
    to_update = Patch()
    miner_id = graph_data_in[0]
    graph_data_out = graph_data_in[1:]
    to_update.update({f"Miner {miner_id + 1}":graph_data_out})
    return to_update

#=======================================================================================

@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-display", "figure", allow_duplicate=True),
    Output("graph-wrapper", "className", allow_duplicate=True),
    inputs=[
        Input("block-number-data", "data"),
        Input("view-select", "value"),
        State("run-status", "data"),
        State ("graph-data", "data")
    ],
    prevent_initial_call=True
)
def render_graphs(num_blocks: int, selected_view: str, run_status: dict, all_graph_data: dict):
    """ Updates the display for the miner tab, showing the graph
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
            graph-file
    """

    graph_data = all_graph_data[selected_view]

    if not run_status["Running"] or num_blocks < 2:
        return "display-none", "", None, "display-none"
    else:
        plotter = SpiralPlotter()
        plotter.import_plotting_data(tree_data=graph_data, num_nodes=num_blocks)
        plot_data = plotter.plot_spiral()
        fig = go.Figure(plot_data)

        fig.update_layout( #TODO move to configs and figure out how to use relative units for graph size
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

    return "display-none", "display-none", fig, ""


#========================================================================================
@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("graph-wrapper", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("run-status", "data", allow_duplicate=True),
    inputs=[
        Input("reset-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def reset_simulation(reset_click: int):
    prep_directories()

    return (
        "", #Intro text
        "display-none", #Loading text
        "display-none", #Miner Graph
        "",             #Run Button
        "display-none", #Reset Button
        "display-none", #Resume Button
        {"Running": False, "Paused": False}
    )

#========================================================================================

@dash.callback(
    Output("resume-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-status", "data", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def pause_simulation(pause_click: int):

    if not os.path.exists(PAUSE_FILE):
        with open(PAUSE_FILE, "w") as f:
            f.write(" ")

    return "", "", "display-none", {"Running":True, "Paused": True}

#========================================================================================

@dash.callback(
    Output("resume-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-status", "data", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def resume_simulation(pause_click: int):
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    return "display-none", "display-none", "", {"Running":True, "Paused": False}

#========================================================================================

@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("run-status", "data", allow_duplicate=True),
    Output("view-select-wrapper", "children"),
    Output("graph-data", "data", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
        State("miner-slider", "value"),
    ],
    prevent_initial_call=True,
)
def run_simulation(run_click: int, num_miners: int):
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    miner_data = {f"Miner {i+1}":[] for i in range(num_miners)}
    miner_data.update({"Global View": []})
    return "display-none", "", "", "display-none", {"Running":True, "Paused": False}, generate_view_select(num_miners), miner_data

#========================================================================================

@dash.callback(

    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    background=True,
    inputs=[
        Input("run-status", "data"),
        State("miner-slider", "value"),
        State("blocks-input", "value"),
    ],
    running=[
        (Output("miner-slider", "disabled"), True, False),
        (Output("blocks-input", "disabled"), True, False), 
    ],
    progress=[
        Output("graph-data-temp", "data"),
        Output("miner-table-head", "children"), 
        Output("miner-table-body", "children"),
        
    ],
    cancel = [Input("reset-button", "n_clicks")],
    prevent_initial_call=True,
)
def simulation(
    display_data_update,
    run_status: dict,
    miner_slider_val: int,
    block_input_val: int,
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

    if run_status["Running"] == False or ctx.triggered_id != "run-status":
        raise PreventUpdate
    else:
        num_blocks = block_input_val
        num_miners = miner_slider_val
        solver = AVAILABLE_SOLVERS[-1]

        manager = TrialManager(num_blocks=num_blocks, num_miners=num_miners, solver=solver)

        #End of trial initialization. Start of trial proper.

        while(manager.blocks_mined <= num_blocks):
            manager.single_step()
  
        
    return "", "display-none"