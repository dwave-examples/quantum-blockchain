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
import random

import dash
import asyncio
from dash import MATCH, ctx, html, Patch, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objects as go
import plotly.express as px

from src.utilities.spiral_plotter import SpiralPlotter
from src.agents.trial_manager import TrialManager
from src.structures.block import Block
from src.values import MINER_NAMES #TODO move to DemoConstants

from demo_configs import VIEW_OPTS, GRAPH_NAMES

from demo_solvers import AVAILABLE_SOLVERS
from demo_interface import generate_options
from src.utilities.display_update import render_miner_status
from src.structures.block_score_tree import BlockScoreTree, BlockNode
from src.protocols.hash_calculator import BootstrappingHashSolver

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#TODO remove if no longer necessary
def reconstruct_score_tree(node_list: list[dict], miner_id: str) -> BlockScoreTree:
    tree = BlockScoreTree()
    for block_entry in node_list:
        try: #TODO this code should be reliable, but is failing occasionally. Revisit the logic for determining 
            scores = block_entry["scores"] #how much of the tree a particular miner has completed
            score = scores[miner_id]
            block = Block.from_json(block_entry["block_json"])
            tree.add_block(block_hash=block.hash, prev_block_hash=block.previous_hash, block_score=score)
        except: #If we hit an error, then this miner has accessed as much of the tree as able.
            break

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
        State("solver-select", "value"),
    ],
    progress=[
        Output("current-block-data", "data"),
    ],
    cancel = [Input("pause-button", "n_clicks")],
    prevent_initial_call=True,
)
async def simulation(
    update_current_block_data,
    running_status: bool,
    miner_slider_val: int,
    block_input_val: int,
    blockchain_structure: list,
    solver_select_val: str,
):
    """Manages a single run of the blockchain simulation.

    This callback is triggered (indirectly) by the "run" and "resume" buttons. When triggered
    by the "run" button, it will complete a full run of the blockchain simulation with the solver
    scheme and the numbers of blocks and miners each defined by their respective input fields. As
    it runs, it will call the 'update_current_block_data' function to provide progress updates,
    which will then trigger other callbacks to update the display.

    Args:
        update_current_block_data: the progress function for providing updates while the callback is running
        running_status (bool): flag to signal that the 'run' button has been clicked. Passing it this way
            (instead of the 'run' button itself being used as an input), allows certain UI updates (such as
            disabling/hiding components) to be processed immediately on clicking 'run', before the simulation starts
        miner_slider_val (int): the value of the the miner slider: determines how many miners the trial has.
        block_input_val (int): the value of the blocks input. Determines how many blocks the simulation will run for.
        blockchain_structure (list): The data structure storing the current blockchain data. If starting a trial,
            this will simply be a list with 'None' in every field. But if resuming after a pause, this will hold
            the data needed to reconstruct the blockchain
        solver_select_val (str): Value of the solver selector. Outputs as a string-typed integer value (e.g.
            "1", "2"), which can just be immediately typed back to int and put into the AVAILABLE_SOLVERS
            constant to get the solver #TODO make the selector return either the solver name or an actual integer


    Returns:
        Most of the output of this function is passed by 'update_current_block_data', so the only
        actual return values simply toggle button visibility

        reset-button: makes the 'reset' button visible
        pause-button: hides the 'pause' button
    """

    if running_status == False or ctx.triggered_id != "running-status":
        raise PreventUpdate
    else: 
        num_blocks = block_input_val
        num_miners = miner_slider_val
        print(f"Starting TrialManager with {num_blocks} blocks and {num_miners} miners")

        simulated_qpu_solvers = [solver for solver in AVAILABLE_SOLVERS if isinstance(solver, BootstrappingHashSolver)]
        qpu_solvers = set(AVAILABLE_SOLVERS).difference(simulated_qpu_solvers)
        dropdown_idx = int(solver_select_val)

        if dropdown_idx == 0:
            solvers = list(qpu_solvers)
        elif dropdown_idx == 1:
            solvers = simulated_qpu_solvers
        else:
            solvers = [AVAILABLE_SOLVERS[dropdown_idx - 2]]

        manager = TrialManager(num_blocks=num_blocks, num_miners=num_miners, solvers=solvers)

        block_dict_template = {"block_json":"", "block_number": 0, "scores": {}, "miner_id": ""}
        current_block_dict = copy.deepcopy(block_dict_template)

        first_empty_index = blockchain_structure.index(None)
        if first_empty_index > 0:
            print(f"Restarting trial at block {first_empty_index}")
            current_blockchain = blockchain_structure[:first_empty_index]
            manager.blocks_mined = first_empty_index
            last_block = current_blockchain[-1]
            finished_miners = []
            unfinished_miners = []

            for miner_id, miner in manager.miners.items():
                if miner_id in last_block["scores"]:
                    miner_blockchain = reconstruct_score_tree(current_blockchain, miner_id)
                    finished_miners.append(miner_id)
                else:
                    short_blockchain = current_blockchain[:-1]
                    miner_blockchain = reconstruct_score_tree(short_blockchain, miner_id)
                    unfinished_miners.append(miner_id)

                miner.blockchain = miner_blockchain

            print("Finished resetting miners")
            manager.round_progress = len(finished_miners)
            manager.block_broadcast = last_block["block_json"]
            random.shuffle(unfinished_miners)
            manager.round_order = finished_miners + unfinished_miners
            current_block_dict = last_block
            print("Finished all restart logic.")

        min_loop_time = 1.5 #TODO make a constant
        plotter = SpiralPlotter()
        view_miners = MINER_NAMES[:3]
        global_miner = MINER_NAMES[num_miners-1]

        while(manager.blocks_mined <= num_blocks):
            iter_start_time = time.time()
            mined, miner_id, block_score = manager.single_step()
            if mined:
                current_block_dict = copy.deepcopy(block_dict_template)
                current_block_dict["block_number"] = manager.blocks_mined
                current_block_dict["block_json"] = manager.block_broadcast
                current_block_dict["miner_id"] = miner_id
                print(f"TrialManager at beginning of new round with {manager.blocks_mined} blocks mined.")
            else:
                current_block_dict["new"] = False

            current_block_dict["scores"][miner_id] = block_score

            update_current_block_data(current_block_dict)

            await asyncio.sleep(0.1)

            miner_fig = None

            if miner_id == global_miner:
                last_shared_block = manager.get_last_common_trunk_block()
                miner_fig = plotter.create_plot_from_tree(manager.miners[global_miner].blockchain, active_block_cutoff=last_shared_block)
                miner_graph_id = GRAPH_NAMES["Global_View"] #TODO improve binding            
            elif miner_id in view_miners:
                miner_fig = plotter.create_plot_from_tree(manager.miners[miner_id].blockchain)
                miner_graph_id = GRAPH_NAMES[miner_id]
            if miner_fig is not None:
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
                set_props(miner_graph_id, {"figure":miner_fig},)

            await asyncio.sleep(0.1)

        
    return "", "display-none"


#==========================================================================================


@dash.callback(
    Output("blockchain-structure-data", "data"),
    inputs = [
        Input("current-block-data", "data"),
    ],
    prevent_initial_call=True,
)
def update_blockchain_data(block_data: dict):
    """ Pass-through function to patch the single-block update from the 'simulation' callback
        into the larger blockchain data structure."""
    block_number = block_data["block_number"]
    to_update = Patch()
    to_update[block_number-1] = block_data
    return to_update

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Display Updates                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dash.callback(
    Output(GRAPH_NAMES[VIEW_OPTS[0]], "className"), #TODO find a more pythonic way to do this
    Output(GRAPH_NAMES[VIEW_OPTS[1]], "className"),
    Output(GRAPH_NAMES[VIEW_OPTS[2]], "className"),
    Output(GRAPH_NAMES[VIEW_OPTS[3]], "className"),
    inputs=[
        Input("view-select", "value"),
    ],
)
def toggle_graph_display(selected_view):
    """ """

    selected_view = int(selected_view)
    return_tuple = ["" if opt==selected_view else "display-none" for opt in range(4)]

    return return_tuple

@dash.callback(
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("prelim-text", "className"),
    Output("miner-table-head", "children", allow_duplicate=True),
    Output("miner-table-body", "children", allow_duplicate=True),
    inputs = [
        Input("current-block-data", "data"),
        State("miner-slider", "value"),
        ],
    prevent_initial_call=True,
)
def update_main_display(current_block_data: dict, num_miners: int):
    """ This callback processes blockchain structure data and uses it to update the miner status
        table and the graph display."""
    
    mining_id = current_block_data["miner_id"]
    block_number = current_block_data["block_number"]

    miner_status_dict = {MINER_NAMES[i]:"" for i in range(num_miners)}
    for miner_id, score in current_block_data["scores"].items():
        if score > 0:
            status = "Validated"
        else:
            status = "Rejected"
        miner_status_dict[miner_id] = status
    miner_status_dict[mining_id] = "Mined"
    miner_table_head, miner_table_body = render_miner_status(block_number, miner_status_dict)

    return "", "display-none", miner_table_head, miner_table_body



#=======================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Button Triggers                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

@dash.callback(
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("blockchain-structure-data", "data", allow_duplicate=True),
    Output("miner-slider", "disabled", allow_duplicate=True),
    Output("blocks-input", "disabled", allow_duplicate=True),
    Output("solver-select", "disabled", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
        State("blocks-input", "value"),
        State("miner-slider", "value")
    ],
    prevent_initial_call = True
)
def run_simulation(run_click: int, num_blocks: int, num_miners: int):
    """ Runs a simulation with the selected number of miners and blocks."""
    blockchain_init = [None for _ in range(num_blocks+3)]
    return "display-none", "", True, "display-none", blockchain_init, True, True, True #TODO break into lines and label

#========================================================================================

@dash.callback(
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def pause_simulation(pause_click: int):
    """ This callback will pause the current, in-progress simulation. In reality, the
        'simulation' callback is cancelled, but the data defining its current state is
        still stored in the blockchain_structure_data dcc.Store object, so the simulation
        can be restarted by reconstructing the state.
        
        Args:
            pause_click (int): Unused. The pause button just needs to trigger the callback,
                its value is irrelevant.
                
        Returns:
            reset-button (str): makes visible
            resume-button (str): makes visible
            pause-button (str): hides"""

    return "","", "display-none"

#========================================================================================

@dash.callback(
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def resume_simulation(pause_click: int):
    """ Resumes a paused simulation. In practice, this means starting a new instance of the
        'simulation' callback, but without resetting the blockchain data. The simulation 
        will then reconstruct its previous state and pick up where it left off.
        
        Args:
            pause_click (int): Unused.
            
        Returns:
            reset-button (str): hides
            resume-button (str): hides
            pause-button (str): makes visible
            running-status (bool): sets to 'True', indicating that simulation should resume."""
    return "display-none", "display-none", "", True

#========================================================================================
@dash.callback(
    
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("running-status", "data", allow_duplicate=True),
    Output("miner-slider", "disabled", allow_duplicate=True),
    Output("blocks-input", "disabled", allow_duplicate=True),
    Output("solver-select", "disabled", allow_duplicate=True),
    inputs=[ #TODO add blockchain structure
        Input("reset-button", "n_clicks"),
    ],
    prevent_initial_call = True
)
def reset_simulation(reset_click: int):
    """ Resets the simulation, allowing a new simulation to be started."""
    return (
        "", #Intro text
        "display-none", #Loading text
        "display-none", #Miner Graph
        "",             #Run Button
        "display-none", #Reset Button
        "display-none", #Resume Button
        False, #Running Status
        False, #miner-slider 'disabled' prop
        False, #blocks-input 'disabled' prop
        False, #solver-select 'disabled' prop
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
