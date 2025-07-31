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

from typing import NamedTuple, Union
import os, json
from pathlib import Path

import dash
from dash import MATCH, ctx
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import networkx as nx
from plotly import graph_objects as go
import plotly.express as px

from demo_interface import generate_miner_status_table
from src.demo_enums import SolverType
from src.common.block_score_tree import BlockScoreTree
from demo_configs import GRAPHS_FILEPATH

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


@dash.callback(
    Output("input", "children"),
    inputs=[
        Input("slider", "value"),
    ],
)
def render_initial_state(slider_value: int) -> str:
    """Runs on load and any time the value of the slider is updated.
        Add `prevent_initial_call=True` to skip on load runs.

    Args:
        slider_value: The value of the slider.

    Returns:
        str: The content of the input tab.
    """
    return f"Put demo input here. The current slider value is {slider_value}."

@dash.callback(
    Output("miner_stats", "children"),
    inputs=[
        Input("miner_stats_update", "n_intervals"),
    ],
)
def render_miner_status(n_intervals: int) -> list:
    """Runs on load and any time the value of the slider is updated.
        Add `prevent_initial_call=True` to skip on load runs.

    Args:
        slider_value: The value of the slider.

    Returns:
        str: The content of the input tab.
    """
    return generate_miner_status_table()


@dash.callback(
    Output("miner_display", "src"),
    inputs=[
        Input("miner_graph_update", "n_intervals"),
    ],
)
def render_miner_graph(n_intervals: int):
    """Runs on load and any time the value of the slider is updated.
        Add `prevent_initial_call=True` to skip on load runs.

    Args:
        slider_value: The value of the slider.

    Returns:
        str: The content of the input tab.
    """

    ALT_MINER_FILES = [os.path.join(GRAPHS_FILEPATH, f"miner_graph{n}.png") for n in range(10)]

    base_graph_name = os.path.join(GRAPHS_FILEPATH, "miner_graph.png")
    current = 0
    next = 1
    found = False

    for i in range(10):
        if os.path.exists(ALT_MINER_FILES[i]):
            current = i
            next = (i +1)%10
            found = True

    if os.path.exists(base_graph_name):
        os.rename(base_graph_name, ALT_MINER_FILES[next])
        os.remove(ALT_MINER_FILES[current])
        graph_file = ALT_MINER_FILES[next]
    elif found:
        graph_file  = ALT_MINER_FILES[current]
    else:
        graph_file = "static/pet3.jpg"

    return graph_file

@dash.callback(
    Output("global_display", "src"),
    inputs=[
        Input("global_graph_update", "n_intervals"),
    ],
)
def render_global_graph(n_intervals: int) -> str:
    """Runs on load and any time the value of the slider is updated.
        Add `prevent_initial_call=True` to skip on load runs.

    Args:
        slider_value: The value of the slider.

    Returns:
        str: The content of the input tab.
    """
    if os.path.exists("static/graphs/iter_num.txt"):
        with open("static/graphs/iter_num.txt","r") as f:
            iter_num = int(f.read())
        return f"static/graphs/miner_graph{iter_num}.png"
    else:
        return "static/pet9.jpg"


class RunOptimizationReturn(NamedTuple):
    """Return type for the ``run_optimization`` callback function."""

    results: str = dash.no_update
    problem_details_table: list = dash.no_update
    # Add more return variables here. Return values for callback functions
    # with many variables should be returned as a NamedTuple for clarity.


@dash.callback(
    # The Outputs below must align with `RunOptimizationReturn`.
    Output("results", "children"),
    Output("problem-details", "children"),
    background=True,
    inputs=[
        # The first string in the Input/State elements below must match an id in demo_interface.py
        # Remove or alter the following id's to match any changes made to demo_interface.py
        Input("run-button", "n_clicks"),
        State("solver-type-select", "value"),
        State("solver-time-limit", "value"),
        State("slider", "value"),
        State("dropdown", "value"),
        State("checklist", "value"),
        State("radio", "value"),
    ],
    running=[
        (Output("cancel-button", "className"), "", "display-none"),  # Show/hide cancel button.
        (Output("run-button", "className"), "display-none", ""),  # Hides run button while running.
        (Output("results-tab", "disabled"), True, False),  # Disables results tab while running.
        (Output("results-tab", "label"), "Loading...", "Results"),
        (Output("tabs", "value"), "miner-tab", "miner-tab"),  # Switch to input tab while running.
        (Output("run-in-progress", "data"), True, False),  # Can block certain callbacks.
    ],
    cancel=[Input("cancel-button", "n_clicks")],
    prevent_initial_call=True,
)
def run_optimization(
    # The parameters below must match the `Input` and `State` variables found
    # in the `inputs` list above.
    run_click: int,
    solver_type: Union[SolverType, int],
    time_limit: float,
    slider_value: int,
    dropdown_value: int,
    checklist_value: list,
    radio_value: int,
) -> RunOptimizationReturn:
    """Runs the optimization and updates UI accordingly.

    This is the main function which is called when the ``Run Optimization`` button is clicked.
    This function takes in all form values and runs the optimization, updates the run/cancel
    buttons, deactivates (and reactivates) the results tab, and updates all relevant HTML
    components.

    Args:
        run_click: The (total) number of times the run button has been clicked.
        solver_type: The solver to use for the optimization run defined by SolverType in demo_enums.py.
        time_limit: The solver time limit.
        slider_value: The value of the slider.
        dropdown_value: The value of the dropdown.
        checklist_value: A list of the values of the checklist.
        radio_value: The value of the radio.

    Returns:
        A NamedTuple (RunOptimizationReturn) containing all outputs to be used when updating the HTML
        template (in ``demo_interface.py``). These are:

            results: The results to display in the results tab.
            problem-details: List of the table rows for the problem details table.
    """

    # Only run optimization code if this function was triggered by a click on `run-button`.
    # Setting `Input` as exclusively `run-button` and setting `prevent_initial_call=True`
    # also accomplishes this.
    if run_click == 0 or ctx.triggered_id != "run-button":
        raise PreventUpdate

    solver_type = SolverType(solver_type)


    ###########################
    ### YOUR CODE GOES HERE ###
    ###########################


    # Generates a list of table rows for the problem details table.
    problem_details_table = generate_problem_details_table_rows(
        solver=solver_type.label,
        time_limit=time_limit,
    )

    return RunOptimizationReturn(
        results="Put demo results here.",
        problem_details_table=problem_details_table,
    )
