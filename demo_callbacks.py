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
import os, json, time, math
from pathlib import Path

import dash
from dash import MATCH, ctx, html, dcc, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from src.demo_enums import SolverType
from src.trials.trial_manager import TrialManager
from src.trials.trial_owners import TrialOwners
from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu
from src.common.values import TRIAL_PARAMETERS_FILE
from demo_utils import prep_directories, make_output_directory
from demo_configs import DEFAULT_TABLE_HEADER, DEFAULT_TABLE_BODY, MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_constants import (
                            GLOBAL_GRAPHS_PATH,
                            BASE_GLOBAL_GRAPH_FILE,
                            MINER_GRAPHS_PATH, 
                            BASE_MINER_GRAPH_FILE,
                            MINER_STATS_PATH, 
                            MINER_STATS_FILE,
                            PAUSE_FILE,
                            STATIC_PARAMS_FILE, 
                            EMBEDDINGS_DIRECTORY,
                          )


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
    table_header = html.Th(round_state + f" Block {block_number}")

    num_miners = len(miner_status)
    miner_names = [f"Miner {i}" for i in range(1, num_miners + 1)]
    columns = min(math.ceil(num_miners / MAX_MINER_ROWS), MAX_MINER_COLUMNS)

    table_rows = []
    new_row = []
    for i in range(0, num_miners):
        new_row.append(html.Th(miner_names[i]))
        new_row.append(html.Td(miner_status[i]))
        if len(new_row) >= 2*columns:
            table_rows.append(html.Tr(new_row))
            new_row = []
    if len(new_row) > 0:
        table_rows.append(html.Tr(new_row))

    return table_header, table_rows

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
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("global-graph", "className", allow_duplicate=True),
    Output("miner-graph", "className", allow_duplicate=True),
    Output("global-graph", "src", allow_duplicate=True),
    Output("miner-graph", "src", allow_duplicate=True),
    inputs=[
        Input("display-update", "n_intervals"),
        Input("view-select", "value"),
        Input("run-status", "data"),
    ],
    prevent_initial_call = True
)
def render_graphs(n_intervals: int, view_select: str, run_status: dict):
    """ Updates the display for the miner tab, shwoing the graph
        of the current chain state if it is available.

        The file naming logic here is somewhat convoluted because it has to be:
        the html.Img object seems to cache copies of the last several images it
        has displayed. If you don't give it a new name, it will keep displaying
        the older image. So we rotate through a sequence of filenames.

        Args:
            miner-graph-update: interval set to check if there is anything to update
            run-status: if run status alters, display should alter
            tabs: should automatically render on switching tabs.

            TODO: as long as we're fine with the space requirement of keeping all the
            graph files for a run, this could be improved and simplified by just 
            having the files generate with new names each time. It would also allow
            for "replays" of a trial at the end. This will take just enough work that I
            don't want to do it quite yet.

        Returns:
            graph-file
    """

    #TODO add a block number store to allow for better logic

    if not (os.listdir(GLOBAL_GRAPHS_PATH) or os.listdir(MINER_GRAPHS_PATH)):
        raise PreventUpdate
    
    if run_status["Paused"] == True:
        raise PreventUpdate
    
    graph_displays = ["display-none", "display-none"]
    graph_files = ["",""]
    max_files = 200

    if view_select == "Global View" or view_select == "Comparison":
        if not os.path.exists(BASE_GLOBAL_GRAPH_FILE):
            raise PreventUpdate
        
        else:
            graph_displays[0] = ""
            ALT_GLOBAL_FILES = [os.path.join(GLOBAL_GRAPHS_PATH, f"global_graph{n}.png") for n in range(max_files)]
            next_file = 0
            for filenum in range(max_files):
                if os.path.exists(ALT_GLOBAL_FILES[filenum]):
                    next_file = filenum + 1
            os.rename(BASE_GLOBAL_GRAPH_FILE, ALT_GLOBAL_FILES[next_file])
            graph_files[0] = ALT_GLOBAL_FILES[next_file]

    if view_select == "Miner View" or view_select == "Comparison":
        if not os.path.exists(BASE_MINER_GRAPH_FILE):
            raise PreventUpdate
        
        else:
            graph_displays[1] = ""
            ALT_MINER_FILES = [os.path.join(MINER_GRAPHS_PATH, f"miner_graph{n}.png") for n in range(max_files)]
            next_file = 0
            for filenum in range(max_files):
                if os.path.exists(ALT_MINER_FILES[filenum]):
                    next_file = filenum + 1
            os.rename(BASE_MINER_GRAPH_FILE, ALT_MINER_FILES[next_file])
            graph_files[1] = ALT_MINER_FILES[next_file]

    
    return "display-none", "display-none", graph_displays[0], graph_displays[1], graph_files[0], graph_files[1]

    
#========================================================================================
@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph", "className", allow_duplicate=True),
    Output("global-graph", "className", allow_duplicate=True),
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
            "display-none", #Global Graph
            "",             #Run Button
            "display-none", #Reset Button
            "display-none", #Resume Button
            {"Running":False, "Paused": False}
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
    inputs=[
        Input("run-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def run_simulation(
    run_click: int,
):
    if os.path.exists(PAUSE_FILE):
        os.remove(PAUSE_FILE)
    return "display-none", "", "", "display-none", {"Running":True, "Paused": False}

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
        Output("miner-table-head", "children"), 
        Output("miner-table-body", "children"),
    ],
    cancel = [Input("reset-button", "n_clicks")],
    prevent_initial_call=True,
)
def simulation(
    table_update,
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
        prep_directories()
        trial_directory = make_output_directory()
        with open(STATIC_PARAMS_FILE, 'r') as f:
            trial_params = json.load(f)

        #Trial initialization stuff. Takes a long time, so we only want to do it once per run.
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

        #End of trial initialization. Start of trial proper.

        while(manager.iteration_number <= num_blocks):
            if not os.path.exists(PAUSE_FILE):
               blocknum, miner_stats = manager.miner_step()
               table_update(render_miner_status(blocknum, miner_stats))
            time.sleep(0.15) #intent is to give other components a chance to update. But might not be necessary.
  
        
    return "", "display-none"
