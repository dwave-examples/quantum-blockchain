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
from dash import MATCH, ctx, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from demo_interface import generate_miner_status_table
from src.demo_enums import SolverType
from src.trials.trial_manager import TrialManager
from src.trials.trial_owners import TrialOwners
from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu
from src.common.values import TRIAL_PARAMETERS_FILE
from demo_utils import directory_setup
from demo_configs import(GRAPHS_PATH, 
                         DYNAMIC_PARAMS_PATH, 
                         BASE_MINER_GRAPH_FILE, 
                         BASE_GLOBAL_GRAPH_FILE,
                         STATIC_PARAMS_FILE,
                         TRIAL_INIT_FILE,
                         MIN_MINERS,
                         RUN_STATUS,
                         PAUSE_FILE,
                         EMBEDDINGS_DIRECTORY,
                         INTRO_SCREEN_FILE,
                         LOADING_SCREEN_FILE)

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
    Output("miner-status", "children"),
    inputs=[
        Input("miner-status-update", "n_intervals"),
    ],
)
def render_miner_status(n_intervals: int) -> list:
    """Renders the status of the miners in the current trial

    Args:
        n_intervals (unused)

    Returns:
        str: miner status table
    """
    return generate_miner_status_table()

#=======================================================================================

@dash.callback(
    Output("miner-display", "src"),
    inputs=[
        Input("miner-graph-update", "n_intervals"),
        Input("run-status", "children"),
        Input("tabs", "value"),
    ],
)
def render_miner_graph(n_intervals: int, run_status: str, tab_val: str):
    """ Updates the display for the miner tab, shwoing the graph
        of the current chain state if it is available.

        Args:
            miner-graph-update: interval set to check if there is anything to update
            run-status: if run status alters, display should alter
            tabs: should automatically render on switching tabs

        Returns:
            graph-file
    """

    num_alts = 5

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
    elif run_status == "Running...":
        graph_file = LOADING_SCREEN_FILE
    else:
        graph_file = INTRO_SCREEN_FILE

    return graph_file

#========================================================================================

@dash.callback(
    Output("global-display", "src"),
    inputs=[
        Input("global-graph-update", "n_intervals"),
        Input("run-status", "children"),
        Input("tabs", "value"),
    ],
)
def render_global_graph(n_intervals: int, run_status: str, tab_val: str) -> str:
    """ Updates the display for the global tab, shwoing the graph
        of the current chain state if it is available.

        Args:
            global-graph-update: interval set to check if there is anything to update
            run-status: if run status alters, display should alter
            tabs: should automatically render on switching tabs
        Returns:
            graph-file
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

    if run_status == "Ready":
        graph_file = INTRO_SCREEN_FILE
    elif os.path.exists(BASE_GLOBAL_GRAPH_FILE):
        for file in ALT_GLOBAL_FILES:
            if os.path.exists(file):
                os.remove(file)
        os.rename(BASE_GLOBAL_GRAPH_FILE, ALT_GLOBAL_FILES[next])
        graph_file = ALT_GLOBAL_FILES[next]
    elif found:
        graph_file  = ALT_GLOBAL_FILES[current]
    elif run_status == "Running...":
        graph_file = LOADING_SCREEN_FILE
    else:
        graph_file = INTRO_SCREEN_FILE


    return graph_file

#========================================================================================
@dash.callback(
    Output("run-status", "children", allow_duplicate=True),
    Output("miner-display", "src", allow_duplicate=True),
    Output("global-display", "src", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    inputs=[
        Input("reset-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def reset_simulation(reset_click: int):
    os.remove(PAUSE_FILE)
    return "Ready", "static/pet3.jpg", "static/pet4.jpg", "", "display-none", "display-none"

#========================================================================================

@dash.callback(
    Output("pause-status", "children", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def pause_simulation(pause_click: int):
    with open(PAUSE_FILE, "w") as f:
        f.write("")
    return "Paused", "", "", "display-none"

#========================================================================================

@dash.callback(
    Output("pause-status", "children", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def resume_simulation(pause_click: int):
    os.remove(PAUSE_FILE)
    return " ", "display-none", "display-none", ""

#========================================================================================

@dash.callback(
    # The Outputs below must align with `RunOptimizationReturn`.
    Output("run-status", "children", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def run_simulation(
    run_click: int,
):
    return "Running...", "", "display-none"

#========================================================================================

@dash.callback(
    # The Outputs below must align with `RunOptimizationReturn`.
    Output("run-status", "children", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    background=True,
    inputs=[
        # The first string in the Input/State elements below must match an id in demo_interface.py
        # Remove or alter the following id's to match any changes made to demo_interface.py
        Input("run-status", "children"),
        State("miner-slider", "value"),
        State("blocks-input", "value"),
    ],
    cancel = [Input("reset-button", "n_clicks")],
    prevent_initial_call=True,
)
def simulation(
    # The parameters below must match the `Input` and `State` variables found
    # in the `inputs` list above.
    run_status: str,
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

    if run_status != "Running..." or ctx.triggered_id != "run-status":
        raise PreventUpdate
    else:
        num_blocks = block_input_val
        num_miners = miner_slider_val
        trial_directory = directory_setup()
        with open(STATIC_PARAMS_FILE, 'r') as f:
            trial_params = json.load(f)

        trial_owners = TrialOwners()
        owner_keys = [owner.private_key.export_key().decode('utf8') for owner in trial_owners]
        del trial_owners
        trial_params.update({"Miners":num_miners,"Blocks":num_blocks, 
                             "Owners":owner_keys})

        pow_protocol = ProofOfWorkProtocolQpu(embedding_directory=EMBEDDINGS_DIRECTORY,
                                          randomize_solver=trial_params["Random_Solver"], 
                                          randomize_embedding=trial_params["Random_Solver"], 
                                          profile=trial_params["Profile"],
                                          solver=trial_params["Solver"], 
                                          annealing_time=trial_params["Annealing_Time"], 
                                          ensemble=trial_params["Ensemble"])

        pow_protocol.to_json(trial_directory)
        with open(os.path.join(trial_directory,TRIAL_PARAMETERS_FILE), 'w') as f:
            json.dump(trial_params, f)

        manager = TrialManager(trial_directory)

        while(manager.iteration_number <= num_blocks):
            if not os.path.exists(PAUSE_FILE):
                manager.miner_step()
            time.sleep(0.15)
  
        
    return "Simulation Complete", "", "display-none", ""
