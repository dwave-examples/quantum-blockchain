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
import os, json, time
from pathlib import Path

import dash
from dash import MATCH, ctx
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from demo_interface import generate_miner_status_table
from src.demo_enums import SolverType
from demo_configs import(GRAPHS_PATH, 
                         DYNAMIC_PARAMS_PATH, 
                         BASE_MINER_GRAPH_FILE, 
                         BASE_GLOBAL_GRAPH_FILE,
                         STATIC_PARAMS_FILE,
                         TRIAL_INIT_FILE,
                         MIN_MINERS,
                         PAUSE_FILE )

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
    prevent_initial_call = True
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

    num_alts = 4

    ALT_MINER_FILES = [os.path.join(GRAPHS_PATH, f"miner_graph{n}.png") for n in range(num_alts)]

    current = 0
    next = 1
    found = False

    for i in range(num_alts):
        if os.path.exists(ALT_MINER_FILES[i]):
            current = i
            next = (i +1)%num_alts
            found = True

    if os.path.exists(BASE_MINER_GRAPH_FILE):
        for file in ALT_MINER_FILES:
            if os.path.exists(file):
                os.remove(file)
        os.rename(BASE_MINER_GRAPH_FILE, ALT_MINER_FILES[next])
        graph_file = ALT_MINER_FILES[next]
    elif found:
        graph_file  = ALT_MINER_FILES[current]
    else:
        graph_file = "static/pet1.jpg"

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
    num_alts = 4

    ALT_GLOBAL_FILES = [os.path.join(GRAPHS_PATH, f"global_graph{n}.png") for n in range(num_alts)]

    current = 0
    next = 1
    found = False

    for i in range(num_alts):
        if os.path.exists(ALT_GLOBAL_FILES[i]):
            current = i
            next = (i +1)%num_alts
            found = True

    if os.path.exists(BASE_GLOBAL_GRAPH_FILE):
        for file in ALT_GLOBAL_FILES:
            if os.path.exists(file):
                os.remove(file)
        os.rename(BASE_GLOBAL_GRAPH_FILE, ALT_GLOBAL_FILES[next])
        graph_file = ALT_GLOBAL_FILES[next]
    elif found:
        graph_file  = ALT_GLOBAL_FILES[current]
    else:
        graph_file = "static/pet2.jpg"

    return graph_file


@dash.callback(
    Output("bucket", "children", allow_duplicate=True),
    Output("miner_display", "src", allow_duplicate=True),
    Output("global_display", "src", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    inputs=[
        Input("reset-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def reset_simulation(reset_click: int):
    with open(PAUSE_FILE, "w") as f:
        f.write("")
    #TODO change button layout
    return "Paused", "static/pet3.jpg", "static/pet4.jpg", ""

@dash.callback(
    Output("bucket", "children", allow_duplicate=True),
    background=True,
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    running=[
        (Output("pause-button", "className"), "display-none", ""),  # Hides run button while running.
        (Output("run-button", "className"),"", "display-none"),  # Shows run button while running
        (Output("reset-button", "className"), "", "display-none"),  # Shows reset button while running.
        #(Output("run-in-progress", "data"), True, False),  #TODO figure out how/where to use
    ],
    cancel=[Input("run-button", "n_clicks"), Input("reset-button", "n_clicks")],
    prevent_initial_call = True
)
def pause_simulation(pause_click: int):
    with open(PAUSE_FILE, "w") as f:
        f.write("")
    while os.path.exists(PAUSE_FILE):
        time.sleep(0.1)

    return "Paused"

@dash.callback(
    # The Outputs below must align with `RunOptimizationReturn`.
    Output("bucket", "children"),
    Output("pause-button", "className"),
    Output("run-button", "className"),
    Output("reset-button", "className"),
    inputs=[
        # The first string in the Input/State elements below must match an id in demo_interface.py
        # Remove or alter the following id's to match any changes made to demo_interface.py
        Input("run-button", "n_clicks"),
        State("miner-slider", "value"),
        State("blocks-input", "value"),
    ],
    prevent_initial_call=True,
)
def run_simulation(
    # The parameters below must match the `Input` and `State` variables found
    # in the `inputs` list above.
    run_click: int,
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

    if run_click == 0 or ctx.triggered_id != "run-button":
        raise PreventUpdate
    else:
        with open(STATIC_PARAMS_FILE, 'r') as f:
            trial_params = json.load(f)
        trial_params.update({"Miners":miner_slider_val,"Blocks":block_input_val})
        with open(TRIAL_INIT_FILE, 'w') as f:
            json.dump(trial_params, f)
        if os.path.exists(PAUSE_FILE):
            os.remove(PAUSE_FILE)


    return "Not an error!", "", "display-none", "display-none"
