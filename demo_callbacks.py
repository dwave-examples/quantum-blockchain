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
from demo_utils import directory_setup, prep_directory
from demo_configs import DEFAULT_TABLE_HEADER, DEFAULT_TABLE_BODY, MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_constants import (GRAPHS_PATH, 
                            DYNAMIC_PARAMS_PATH, 
                            STATIC_PARAMS_FILE, 
                            BASE_GLOBAL_GRAPH_FILE,
                            BASE_MINER_GRAPH_FILE,
                            MINER_STATS_FILE,
                            EMBEDDINGS_DIRECTORY)

PAUSE_FILE = os.path.join(DYNAMIC_PARAMS_PATH, "pause.txt")

INTRO_SCREEN_FILE = os.path.join("static","intro_screen.png")

LOADING_SCREEN_FILES = [os.path.join("static", f"load_screen{n}.png") for n in range(4)]

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
    Output("miner-table-head", "children"),
    Output("miner-table-body", "children"),
    inputs=[
        Input("display-update", "n_intervals"),
    ],
    prevent_initial_call = True
)
def render_miner_status(n_intervals: int):
    """ Renders the status of the miners in the current trial. Each miner will be named
        "Miner n" where n is one more than their ID in TrialManager (because numbering 
        starting from Miner 0 is less aesthetic), and will have a status of "Mining, Mined,
        Validating, Valid" if they've started acting this round, or "..." if not.

    Args:
        n_intervals (unused)

    Returns:
        str: miner status table
    """

    if not os.path.exists(MINER_STATS_FILE):
        table_header = DEFAULT_TABLE_HEADER
        table_rows = [DEFAULT_TABLE_BODY]

    else:
        with open(MINER_STATS_FILE, 'r') as f:
            miner_dict = json.load(f)

        block_number = miner_dict["Block"]
        miner_status = miner_dict["Miners"]
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
    Output("intro-text", "className"),
    Output("loading-text", "className"),
    Output("global-graph", "className"),
    Output("miner-graph", "className"),
    Output("miner-graph", "src"),
    inputs=[
        Input("display-update", "n_intervals"),
        Input("run-status", "children"),
    ],
    prevent_initial_call = True
)
def render_miner_graph(n_intervals: int, run_status: str):
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
    #TODO change the logic here to save old graphs and allow for replays.
    num_alts = 25

    ALT_MINER_FILES = [os.path.join(GRAPHS_PATH, f"miner_graph{n}.png") for n in range(num_alts)]

    current_file = 0
    next_file = 1
    found = False
    old_graph_file = "static/pet8.jpg"

    for i in range(num_alts):
        if os.path.exists(ALT_MINER_FILES[i]):
            if not os.path.exists(ALT_MINER_FILES[(i+1)%num_alts]):
                current_file = i
                next_file = (i +1)%num_alts 
                found = True

    #Grab a new graph if it exists
    if os.path.exists(BASE_MINER_GRAPH_FILE):
        if os.path.exists(ALT_MINER_FILES[current_file]):
            old_graph_file = ALT_MINER_FILES[current_file]
        for file in ALT_MINER_FILES:
            if os.path.exists(file): #Remove any files older than the next-to-last
                if file != old_graph_file:
                    os.remove(file)
        os.rename(BASE_MINER_GRAPH_FILE, ALT_MINER_FILES[next_file])
        graph_file = ALT_MINER_FILES[next_file] #Rename new file to next name in sequence
    elif found: #Otherwise, keep the old graph if it exists
        graph_file  = ALT_MINER_FILES[current_file]
    elif run_status == "Running...": #Or show a load screen is we're loading.
        filenum = (int(n_intervals)//3)%4 
        graph_file = LOADING_SCREEN_FILES[filenum]
    else: #And if none of the above apply, intro screen covers everything else
        graph_file = INTRO_SCREEN_FILE

    #if os.path.exists(graph_file):
     #   return graph_file
    #else:
     #   return old_graph_file
    
    return "display-none", "display-none", "display-none", "", graph_file

#========================================================================================

@dash.callback(
    Output("intro-text", "className"),
    Output("loading-text", "className"),
    Output("miner-graph", "className"),
    Output("global-graph", "className"),
    Output("global-graph", "src"),
    inputs=[
        Input("display-update", "n_intervals"),
        Input("run-status", "children"),
    ],
    prevent_initial_call = True
)
def render_global_graph(n_intervals: int, run_status: str):
    """ Updates the display for the global tab, shwoing the graph
        of the current chain state if it is available.

        See render_miner_graph for more detail (logic of both callbacks is the same)
        
        Args:
            global-graph-update: interval set to check if there is anything to update
            run-status: if run status alters, display should alter
            tabs: should automatically render on switching tabs
        Returns:
            graph-file
    """

    num_alts = 25

    ALT_GLOBAL_FILES = [os.path.join(GRAPHS_PATH, f"global_graph{n}.png") for n in range(num_alts)]

    current = 0
    next = 1
    found = False

    for i in range(num_alts):
        if os.path.exists(ALT_GLOBAL_FILES[i]):
            current = i
            next = (i +1)%num_alts
            found = True

     #Grab a new graph if it exists
    if os.path.exists(BASE_GLOBAL_GRAPH_FILE):
        for file in ALT_GLOBAL_FILES:
            if os.path.exists(file):
                os.remove(file) #Remove any files older than the next-to-last
        os.rename(BASE_GLOBAL_GRAPH_FILE, ALT_GLOBAL_FILES[next])
        graph_file = ALT_GLOBAL_FILES[next] #Rename new file to next name in sequence
    elif found: #Otherwise, keep the old graph if it exists
        graph_file  = ALT_GLOBAL_FILES[current]
    elif run_status == "Running...": #Or show a load screen is we're loading.
        filenum = (n_intervals//4)%4 
        graph_file = LOADING_SCREEN_FILES[filenum]
    else: #And if none of the above apply, intro screen covers everything else
        graph_file = INTRO_SCREEN_FILE

    return "display-none", "display-none", "display-none", "", graph_file

#========================================================================================
@dash.callback(
    Output("miner-graph", "src", allow_duplicate=True),
    Output("global-graph", "src", allow_duplicate=True),
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
    prep_directory(GRAPHS_PATH) 
    prep_directory(DYNAMIC_PARAMS_PATH)
    return "display-none", "display-none", "", "display-none", "display-none", {"Running":False, "Paused": False}

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
    with open(PAUSE_FILE, "w") as f:
        f.write("")
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
    return "display-none", "", "", "display-none", {"Running":True, "Paused": False}

#========================================================================================

@dash.callback(

    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
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
    cancel = [Input("reset-button", "n_clicks")],
    prevent_initial_call=True,
)
def simulation(
    # The parameters below must match the `Input` and `State` variables found
    # in the `inputs` list above.
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

    if run_status["Running"] != True or ctx.triggered_id != "run-status":
        raise PreventUpdate
    else:
        num_blocks = block_input_val
        num_miners = miner_slider_val
        trial_directory = directory_setup()
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
                manager.miner_step()
            time.sleep(0.15) #intent is to give other components a chance to update. But might not be necessary.
  
        
    return "display-none", "display-none", ""
