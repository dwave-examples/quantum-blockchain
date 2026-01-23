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

import copy
import random
import time
from typing import NamedTuple

import dash
import plotly.graph_objects as go
from dash import MATCH, ctx, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from demo_configs import QUANTUM_HASH_LENGTH, N_ZEROES, ALLOWABLE_ERR, MINER_NAMES
from demo_solvers import get_solver_lists
from demo_interface import VIEW_OPTS
from src.agents.trial_manager import TrialManager
from src.demo_enums import SolverMode
from src.utilities.display_update import render_miner_status
from src.utilities.spiral_plotter import SpiralPlotter
from src.structures.block import Block

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dash.callback(
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("block-status", "className", allow_duplicate=True),
    inputs=[
        Input("is-running-status", "data"),
        State("miner-slider", "value"),
        State("blocks-input", "value"),
        State("blockchain-structure-data", "data"),
        State("qpu-solver-select", "value"),
        State("simulated-solver-select", "value"),
        State("solver-mode-select", "value"),
    ],
    progress=[
        Output("current-block-data", "data"),
    ],
    cancel=[Input("pause-button", "n_clicks")],
    prevent_initial_call=True,
    background=True,
)
def simulation(
    update_current_block_data: dict,
    is_running: bool,
    num_miners: int,
    num_blocks: int,
    blockchain_structure: list,
    qpu_solver_select_val: str,
    simulated_solver_select_val: str,
    solver_mode: str,
):
    """Manages a single run of the blockchain simulation.

    This callback is triggered (indirectly) by the "run" and "resume" buttons. When triggered
    by the "run" button, it will complete a full run of the blockchain simulation with the solver
    scheme and the numbers of blocks and miners each defined by their respective input fields. As
    it runs, it will call the 'update_current_block_data' function to provide progress updates,
    which will then trigger other callbacks to update the display.

    Args:
        update_current_block_data: the progress function for providing updates while the callback is running
        is_running (bool): flag to signal that the 'run' button has been clicked. Passing it this way
            (instead of the 'run' button itself being used as an input), allows certain UI updates (such as
            disabling/hiding components) to be processed immediately on clicking 'run', before the simulation starts
        num_miners (int): the value of the the miner slider: determines how many miners the trial has.
        num_blocks (int): the value of the blocks input. Determines how many blocks the simulation will run for.
        blockchain_structure (list): The data structure storing the current blockchain data. If starting a trial,
            this will simply be a list with 'None' in every field. But if resuming after a pause, this will hold
            the data needed to reconstruct the blockchain
        solver_mode (str): Value of the solver selector. Outputs as a string-typed integer value (e.g.
            "1", "2"), which can just be immediately typed back to int and put into the AVAILABLE_SOLVERS
            constant to get the solver #TODO make the selector return either the solver name or an actual integer


    Returns:
        Most of the output of this function is passed by 'update_current_block_data', so the only
        actual return values simply toggle button visibility

        reset-button: makes the 'reset' button visible
        pause-button: hides the 'pause' button
    """

    if not is_running or ctx.triggered_id != "is-running-status":
        raise PreventUpdate

    solver_mode = SolverMode(solver_mode)
    print(f"Starting TrialManager with {num_blocks} blocks and {num_miners} miners")

    available_qpu_solvers, available_simulated_solvers = get_solver_lists()

    mode_config = {
        SolverMode.QPU: (int(qpu_solver_select_val), available_qpu_solvers),
        SolverMode.SIMULATED: (int(simulated_solver_select_val), available_simulated_solvers),
    }
    dropdown_idx, solvers = mode_config[solver_mode]

    if dropdown_idx > 0:
        solvers = [solvers[dropdown_idx-1]]

    manager = TrialManager(num_blocks, MINER_NAMES[:num_miners], solvers, QUANTUM_HASH_LENGTH, N_ZEROES, ALLOWABLE_ERR)

    block_dict_template = {
        "block_json": "",
        "block_number": 0,
        "scores": {},
        "solvers": {},
        "miner_id": "",
    }
    current_block_dict = copy.deepcopy(block_dict_template)
    current_blockchain = []

    
    if len(blockchain_structure) > 0:
        print(blockchain_structure)
        current_idx = len(blockchain_structure)
        print(f"Restarting trial at block {current_idx}")
        short_blockchain = blockchain_structure[:-1]
        manager.blocks_mined = current_idx + 1
        last_block = blockchain_structure[-1]
        finished_miners = []
        unfinished_miners = []

        for miner_id, miner in manager.miners.items():
            if miner_id in last_block["scores"]:
                miner.re_initialize_blockchain(blockchain_structure)
                finished_miners.append(miner_id)
            else:
                miner.re_initialize_blockchain(short_blockchain)
                unfinished_miners.append(miner_id)

        print("Finished resetting miners")
        manager.round_progress = len(finished_miners)
        manager.block_broadcast = last_block["block_json"]
        random.shuffle(unfinished_miners)
        manager.round_order = finished_miners + unfinished_miners
        current_block_dict = last_block
        current_block = Block.from_json(current_block_dict["block_json"])
        for miner_id, miner in manager.miners.items():
            assert current_block.previous_hash in miner.blockchain.hash_to_branch_lookup, f"{miner_id} failed to have latest block {current_block.hash} with tree structure {miner.blockchain}"
        current_blockchain = blockchain_structure
        print("Finished all restart logic.")

    min_loop_time = 1.1  # TODO make a constant
    view_miners = {
        MINER_NAMES[(opt.miner_number) % num_miners]: opt.graph_name for opt in VIEW_OPTS
    }

    while manager.blocks_mined <= num_blocks:
        iter_start_time = time.time()
        if manager.round_progress == 0 and manager.blocks_mined == num_blocks:
            break 
        mined, miner_id, block_score, solver = manager.single_step()
        if mined:
            current_block_dict = copy.deepcopy(block_dict_template)
            current_block_dict["block_number"] = manager.blocks_mined
            current_block_dict["block_json"] = manager.block_broadcast
            current_block_dict["miner_id"] = miner_id
            print(
                f"TrialManager at beginning of new round with {manager.blocks_mined} blocks mined."
            )

            current_block_dict["scores"][miner_id] = block_score
            current_block_dict["solvers"][miner_id] = solver
            current_blockchain.append(current_block_dict)

        else:

            current_block_dict["scores"][miner_id] = block_score
            current_block_dict["solvers"][miner_id] = solver
            current_blockchain[-1] = current_block_dict

        set_props("blockchain-structure-data", {"data": current_blockchain})
        time.sleep(0.2)

        update_current_block_data(current_block_dict)

        time.sleep(0.2)

        miner_fig = None

        if miner_id in view_miners:
            active_hashes = manager.get_active_block_hashes()
            most_recent_block = manager.miners[miner_id].blockchain.most_recent_block
            plotter = SpiralPlotter()
            if "global" in view_miners[miner_id]:
                last_shared_block = manager.get_last_common_trunk_block()
                miner_fig = plotter.create_plot_from_tree(
                    manager.miners[miner_id].blockchain, 
                    active_blocks = active_hashes,
                    active_block_cutoff=last_shared_block, 
                    mining_block=most_recent_block
                )
            else:
                miner_fig = plotter.create_plot_from_tree(manager.miners[miner_id].blockchain, 
                                                          active_blocks = active_hashes,
                                                          mining_block=most_recent_block)

            miner_graph_name = view_miners[miner_id]

            miner_fig.update_layout(  # TODO move to configs
                autosize=False,
                showlegend=False,
                xaxis=dict(showticklabels=False),
                yaxis=dict(showticklabels=False),
                margin=dict(l=0, r=0, b=0, t=0, pad=4),
                paper_bgcolor="white",
                plot_bgcolor="white",
            )
            set_props(
                miner_graph_name,
                {"figure": miner_fig},
            )


        iter_end_time = time.time()
        iter_total_time = iter_end_time - iter_start_time
        if iter_total_time < min_loop_time:
            time.sleep(min_loop_time - iter_total_time)

    return "", "display-none", ""


# ======================================================================================================


@dash.callback(
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("prelim-text", "className"),
    Output("block-status", "children", allow_duplicate=True),
    Output("miner-status-table", "children", allow_duplicate=True),
    inputs=[
        Input("current-block-data", "data"),
        State("miner-slider", "value"),
        State("solver-mode-select", "value"),
        State("qpu-solver-select", "value"),
        State("simulated-solver-select", "value"),
    ],
    prevent_initial_call=True,
)
def update_miner_display(
    current_block_data: dict,
    num_miners: int,
    solver_mode: str,
    qpu_select: str,
    simulated_select: str,
):
    """This callback processes blockchain structure data and uses it to update the miner status
    table and the graph display."""

    solver_mode = SolverMode(solver_mode)
    show_solvers = (solver_mode is SolverMode.QPU and int(qpu_select) == 0) or (
        solver_mode is SolverMode.SIMULATED and int(simulated_select) == 0
    )

    block_number = current_block_data["block_number"]

    block_status_text = f"Currently mining block number {block_number}"

    miner_table_body = render_miner_status(current_block_data, num_miners, show_solvers)


    return "", "display-none", block_status_text, miner_table_body


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: User Controls                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class RunSimulationReturn(NamedTuple):
    """Return type for the ``run_simulation`` callback function."""

    run_button_classname: str = "display-none"
    reset_button_classname: str = "display-none"
    pause_button_classname: str = ""
    is_running: bool = True
    miner_slider_disabled: bool = True
    blocks_input_disabled: bool = True
    qpu_solver_select_disabled: bool = True
    simulated_solver_select_disabled: bool = True


@dash.callback(
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("is-running-status", "data", allow_duplicate=True),
    Output("miner-slider", "disabled", allow_duplicate=True),
    Output("blocks-input", "disabled", allow_duplicate=True),
    Output("qpu-solver-select", "disabled", allow_duplicate=True),
    Output("simulated-solver-select", "disabled", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
        State("blocks-input", "value"),
    ],
    prevent_initial_call=True,
)
def run_simulation(run_click: int, num_blocks: int) -> RunSimulationReturn:
    """Runs a simulation with the selected number of miners and blocks."""
    return RunSimulationReturn()


# ========================================================================================


@dash.callback(
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
        State("blockchain-structure-data", "data"),
    ],
    prevent_initial_call=True,
)
def pause_simulation(pause_click: int, blocks: list):
    """This callback will pause the current, in-progress simulation. In reality, the
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
    
    print("In pause")
    time.sleep(0.2)
    print(f"Paused with blockchain structure {blocks}")

    return "", "", "display-none"


# ========================================================================================


@dash.callback(
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("pause-button", "className", allow_duplicate=True),
    Output("is-running-status", "data", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def resume_simulation(pause_click: int):
    """Resumes a paused simulation. In practice, this means starting a new instance of the
    'simulation' callback, but without resetting the blockchain data. The simulation
    will then reconstruct its previous state and pick up where it left off.

    Args:
        pause_click (int): Unused.

    Returns:
        reset-button (str): hides
        resume-button (str): hides
        pause-button (str): makes visible
        is-running-status (bool): sets to 'True', indicating that simulation should resume."""

    return "display-none", "display-none", "", True


# ========================================================================================
class ResetSimulationReturn(NamedTuple):
    """Return type for the ``reset_simulation`` callback function."""

    intro_text_classname: str = ""
    loading_text_classname: str = "display-none"
    miner_graph_and_table_classname: str = "display-none"
    run_button_classname: str = ""
    reset_button_classname: str = "display-none"
    resume_button_classname: str = "display-none"
    prelim_text_classname: str = ""
    is_running: bool = False
    miner_slider_disabled: bool = False
    blocks_input_disabled: bool = False
    qpu_solver_select_disabled: bool = False
    simulated_solver_select_disabled: bool = False
    blockchain_data: list = []
    graph_0: go.Figure = go.Figure()
    graph_1: go.Figure = go.Figure()
    graph_2: go.Figure = go.Figure()
    graph_3: go.Figure = go.Figure()


@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-and-table", "className", allow_duplicate=True),  # TODO clear graph displays
    Output("run-button", "className", allow_duplicate=True),
    Output("reset-button", "className", allow_duplicate=True),
    Output("resume-button", "className", allow_duplicate=True),
    Output("prelim-text", "className", allow_duplicate=True),
    Output("is-running-status", "data", allow_duplicate=True),
    Output("miner-slider", "disabled", allow_duplicate=True),
    Output("blocks-input", "disabled", allow_duplicate=True),
    Output("qpu-solver-select", "disabled", allow_duplicate=True),
    Output("simulated-solver-select", "disabled", allow_duplicate=True),
    Output("blockchain-structure-data", "data", allow_duplicate=True),
    Output(VIEW_OPTS[0].graph_name, "figure"),
    Output(VIEW_OPTS[1].graph_name, "figure"),
    Output(VIEW_OPTS[2].graph_name, "figure"),
    Output(VIEW_OPTS[3].graph_name, "figure"),
    inputs=[
        Input("reset-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def reset_simulation(reset_click: int) -> ResetSimulationReturn:
    """Resets the simulation, allowing a new simulation to be started."""

    return ResetSimulationReturn()


# =======================================================================================


@dash.callback(
    [Output(opt.wrapper_name, "className") for opt in VIEW_OPTS],
    inputs=[
        Input("view-select", "value"),
    ],
    prevent_initial_call=True,
)
def toggle_graph_display(
    selected_view,
):  # TODO check binding between this and view dropdown options
    """Toggles the visibility of the four different graph displays. Will default to showing the Global
    View graph. When triggered, will hide three of the graph displays and make the selected one visible.
    """

    print(f"View {selected_view} has been selected.")
    selected_view = int(selected_view)
    return_tuple = ["" if opt == selected_view else "display-none" for opt in range(4)]
    print(f"Returning {return_tuple}")

    return return_tuple


# =========================================================================================


@dash.callback(
    Output("qpu-dropdown", "className"),
    Output("simulated-dropdown", "className"),
    inputs=[
        Input("solver-mode-select", "value"),
    ],
)
def toggle_solver_mode(solver_mode):
    """Toggles between QPU Solver mode and Bootstrapping Solver Mode"""
    solver_mode = SolverMode(solver_mode)

    if solver_mode is SolverMode.QPU:
        return "", "display-none"
    elif solver_mode is SolverMode.SIMULATED:
        return "display-none", ""
    else:
        raise Exception("Invalid solver select option")


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
