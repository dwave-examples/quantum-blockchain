# Copyright 2026 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.
#
# The use of code in the quantum-blockchain repository with a quantum computing system is protected
# by the intellectual property rights of D-Wave Quantum Inc. and its affiliates.
#
# The use of the quantum blockchain implementations below (including the Miner, Block, and Hash
# methods) with D-Wave's quantum computing system will require access to D-Wave’s LeapTM quantum
# cloud service and will be governed by the Leap Cloud Subscription Agreement available at:
# https://cloud.dwavesys.com/leap/legal/cloud_subscription_agreement/

from __future__ import annotations

import time
from typing import NamedTuple

import dash
import plotly.graph_objects as go
from dash import ALL, MATCH, ctx, set_props
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate

from demo_configs import MIN_SIMULATION_LOOP_TIME
from src.agents.trial_manager import TrialManager
from src.demo_enums import SolverMode, ViewOpt
from src.protocols.trial_identification import generate_trial_id
from src.utilities.display_update import render_miner_status, compile_hover_data
from src.utilities.get_solvers import get_solver_lists
from src.utilities.spiral_plotter import SpiralPlotter
from src.utilities.save_simulation_data import save_simulation_data

graph_layout_dict = dict(
    autosize=False,
    showlegend=False,
    xaxis=dict(showticklabels=False),
    yaxis=dict(showticklabels=False),
    margin=dict(l=0, r=0, b=0, t=0, pad=4),
    paper_bgcolor="white",
    plot_bgcolor="white",
)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Mining Round Steps                                             |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dash.callback(
    Output("reset-button", "style", allow_duplicate=True),
    Output("pause-button", "style", allow_duplicate=True),
    Output("save-button", "style", allow_duplicate=True),
    Output("save-button", "children", allow_duplicate=True),
    Output("save-button", "disabled", allow_duplicate=True),
    inputs=[
        Input("start-simulation", "data"),
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
    running=[
        (Output("is-active-simulation", "data"), True, False),
    ],
    cancel=[Input("pause-button", "n_clicks")],
    prevent_initial_call=True,
    background=True,
)
def simulation(
    set_progress_miner_table,  # set_progress function for 'progress' argument
    start_simulation: bool,
    num_miners: int,
    num_blocks: int,
    stored_blockchain_data: list,
    qpu_solver_select_val: str,
    simulated_solver_select_val: str,
    solver_mode: str,
) -> tuple[dict, dict, dict, str, bool]:
    """Manages a single run of the blockchain simulation.

    This callback is triggered (indirectly) by the "run" and "resume" buttons. When triggered
    by the "run" button, it will complete a full run of the blockchain simulation with the solver
    scheme and the numbers of blocks and miners each defined by their respective input fields. The
    execution of this function is internally divided up into 'rounds,' where one round covers a
    single action (mining or validation) from each miner in the trial. Each action takes roughly
    1 second, so a round will last for roughly as many seconds as there are miners. It will
    run a number of rounds equal to the 'num_blocks' parameter. As this callback runs, it will
    call the 'set_progress_miner_table' function to provide regular updates to the miner table
    (approximately 1 per second). It will also use the 'set_props' function to keep the
    'blockchain-structure-data' dcc.Store up-to-date with the same frequency, and to update each of
    the graph views once per round.

    Args:
        set_progress_miner_table: the progress function for passing data out to update the miner
            status table
        start_simulation: flag to signal that the 'run' button has been clicked. Passing it
            this way (instead of the 'run' button itself being used as an input), allows certain
            UI updates (such as disabling/hiding components) to be processed immediately on
            clicking 'run', before the simulation starts
        num_miners: value of the miner slider. Determines how many miners the simulation has.
        num_blocks: the value of the blocks input. Determines how many blocks the simulation
            will run for.
        stored_blockchain_data: The data structure storing the current blockchain data.
            This will be empty when starting a new trial, but if the trial has been paused,
            it will contain all the data about the blocks mined up to this point, allowing the
            trial to be restarted from the same state.
        solver_mode: Value of the solver selector. Outputs as a
            string-typed integer value (e.g. "1", "2"), which can just be immediately typed back
            to int and put into the AVAILABLE_SOLVERS constant to get the solver


    Returns:
        Most of the output of this function is passed by 'set_progress_miner_table' or with the
        'set_props' function, so the only actual return values simply toggle button visibility

        reset-button: makes the 'reset' button visible
        pause-button: hides the 'pause' button
    """

    if ctx.triggered_id != "start-simulation":
        raise PreventUpdate

    solver_mode = SolverMode(int(solver_mode))
    available_qpu_solvers, available_simulated_solvers = get_solver_lists()
    mode_config = {
        SolverMode.QPU: (int(qpu_solver_select_val), available_qpu_solvers),
        SolverMode.SIMULATED: (int(simulated_solver_select_val), available_simulated_solvers),
    }
    dropdown_idx, solvers = mode_config[solver_mode]
    if dropdown_idx >= 0:
        solvers = [solvers[dropdown_idx]]

    manager = TrialManager(num_blocks, num_miners, solvers)
    trial_id = generate_trial_id(manager)

    print(f"Starting trial with ID {trial_id}")
    set_props("simulation-id", {"data": trial_id})
    if len(stored_blockchain_data) > 0:
        manager.restart_trial(stored_blockchain_data)

    global_fig = None

    while manager.blocks_mined < num_blocks or manager.round_progress > 0:
        iter_start_time = time.time()
        miner_id = manager.single_step()

        set_props("blockchain-structure-data", {"data": manager.chain_data})
        time.sleep(0.2)

        set_progress_miner_table(manager.chain_data[-1])
        time.sleep(0.2)

        plotter = SpiralPlotter()

        if manager.round_progress == 0:  # round_progress resets to 0 at the end of a round
            mining_hashes = manager.mining_hashes
            block_acceptance_rates = manager.get_acceptance_rates()
            hovertext_data = compile_hover_data(manager.chain_data, block_acceptance_rates)
            global_fig = plotter.create_plot_from_tree(manager.global_tree, mining_hashes, hovertext_data)
            global_fig.update_layout(**graph_layout_dict)
            set_props({"type": "view-graph", "index": 0}, {"figure": global_fig})
        elif miner_id in ViewOpt._member_names_:
            view_miner = manager.miners[miner_id]
            mining_hash = [manager.mining_hashes[0]]
            miner_scores = [{"block_score": block.block_score, "total_score": block.total_score} for block in view_miner.blockchain.block_list[1:]]
            hovertext_data = compile_hover_data(manager.chain_data, miner_scores)
            miner_fig = plotter.create_plot_from_tree(view_miner.blockchain, mining_hash, hovertext_data)
            miner_fig.update_layout(**graph_layout_dict)
            view_idx = ViewOpt[miner_id].value - 1  # ViewOpt vals are off by 1 from miner names
            set_props({"type": "view-graph", "index": view_idx}, {"figure": miner_fig})

        iter_end_time = time.time()
        iter_total_time = iter_end_time - iter_start_time
        if iter_total_time < MIN_SIMULATION_LOOP_TIME:
            time.sleep(MIN_SIMULATION_LOOP_TIME - iter_total_time)

    set_props("blockchain-structure-data", {"data": manager.chain_data})
    time.sleep(0.3)

    # Show reset button, hide pause button, show save button with enabled state and default text
    return {}, {"display": "none"}, {}, "Save Data", False #TODO check with Kate about what 'style' covers


# ======================================================================================================


@dash.callback(
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("view-select-and-block-status", "className", allow_duplicate=True),
    Output("prelim-text", "className"),
    Output("block-status", "children", allow_duplicate=True),
    Output("miner-status-table", "children", allow_duplicate=True),
    Output("graph-loading", "display", allow_duplicate=True),
    inputs=[
        Input("current-block-data", "data"),
        State("miner-slider", "value"),
        State("solver-mode-select", "value"),
        State("qpu-solver-select", "value"),
        State("simulated-solver-select", "value"),
        State("blocks-input", "value"),
    ],
    prevent_initial_call=True,
)
def update_miner_display(
    current_block_data: dict,
    num_miners: int,
    solver_mode: str,
    qpu_select: str,
    simulated_select: str,
    num_blocks: int,
):
    """Processes blockchain structure data and uses it to update the miner status
    table and the graph display."""

    solver_mode = SolverMode(int(solver_mode))
    show_solvers = (solver_mode is SolverMode.QPU and int(qpu_select) == -1) or (
        solver_mode is SolverMode.SIMULATED and int(simulated_select) == -1
    )

    block_number = current_block_data["block_number"]
    block_progress = len(current_block_data["scores"])

    block_status_text = (
        f"Currently mining block {block_number}"
        if block_number < num_blocks or block_progress < num_miners
        else "Finished Simulation"
    )

    miner_table_body = render_miner_status(current_block_data, num_miners, show_solvers)

    graph_loading = "auto" if block_number > 1 else dash.no_update

    return "", "", "display-none", block_status_text, miner_table_body, graph_loading


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: User Controls                                                |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class RunSimulationReturn(NamedTuple):
    """Return type for the ``run_simulation`` callback function."""

    run_button_style: dict = {"display": "none"}
    reset_button_style: dict = {"display": "none"}
    pause_button_style: dict = {}
    start_simulation: bool = True
    miner_slider_disabled: bool = True
    blocks_input_disabled: bool = True
    qpu_solver_select_disabled: bool = True
    simulated_solver_select_disabled: bool = True
    simulation_is_active: bool = True
    graph_loading_display: str = "show"


@dash.callback(
    Output("run-button", "style", allow_duplicate=True),
    Output("reset-button", "style", allow_duplicate=True),
    Output("pause-button", "style", allow_duplicate=True),
    Output("start-simulation", "data", allow_duplicate=True),
    Output("miner-slider", "disabled", allow_duplicate=True),
    Output("blocks-input", "disabled", allow_duplicate=True),
    Output("qpu-solver-select", "disabled", allow_duplicate=True),
    Output("simulated-solver-select", "disabled", allow_duplicate=True),
    Output("is-active-simulation", "data", allow_duplicate=True),
    Output("graph-loading", "display", allow_duplicate=True),
    inputs=[
        Input("run-button", "n_clicks"),
        State("is-active-simulation", "data"),
    ],
    prevent_initial_call=True,
)
def run_simulation(run_click: int, simulation_is_active: bool) -> RunSimulationReturn:
    """Runs a simulation with the selected number of miners and blocks.

    Args:
        run_click: unused
        simulation_is_active: Returns 'True.' Flag to signal that one instance of
            'simulation' callback is already running, so another should not be started"""
    if simulation_is_active:
        raise PreventUpdate

    return RunSimulationReturn()


# ========================================================================================


@dash.callback(
    Output("reset-button", "style", allow_duplicate=True),
    Output("resume-button", "style", allow_duplicate=True),
    Output("pause-button", "style", allow_duplicate=True),
    Output("is-active-simulation", "data", allow_duplicate=True),
    inputs=[
        Input("pause-button", "n_clicks"),
    ],
    prevent_initial_call=True,
)
def pause_simulation(pause_click: int):
    """This callback will pause the current, in-progress simulation. In reality, the
    'simulation' callback is cancelled, but the data defining its current state is
    still stored in the blockchain_structure_data dcc.Store object, so the simulation
    can be restarted by reconstructing the state.

    Args:
        pause_click: Unused. The pause button just needs to trigger the callback,
            its value is irrelevant.

    Returns:
        reset-button: makes visible
        resume-button: makes visible
        pause-button: hides
        is-active-simulation: setting this to False allows the 'simulation' callback
            to be restarted, either by the 'run' button or the 'resume' button.
    """

    return {}, {}, {"display": "none"}, False


# ========================================================================================


@dash.callback(
    Output("reset-button", "style", allow_duplicate=True),
    Output("resume-button", "style", allow_duplicate=True),
    Output("pause-button", "style", allow_duplicate=True),
    Output("start-simulation", "data", allow_duplicate=True),
    Output("is-active-simulation", "data", allow_duplicate=True),
    inputs=[
        Input("resume-button", "n_clicks"),
        State("is-active-simulation", "data"),
    ],
    prevent_initial_call=True,
)
def resume_simulation(pause_click: int, simulation_is_active: bool):
    """Resumes a paused simulation. In practice, this means starting a new instance of the
    'simulation' callback, but without resetting the blockchain data. The simulation
    will then reconstruct its previous state and pick up where it left off.

    Args:
        pause_click: Unused.
        simulation_is_active: Returns 'True.' Flag to signal that one instance of
            'simulation' callback is already running, so another should not be started

    Returns:
        reset-button: hides
        resume-button: hides
        pause-button: makes visible
        start-simulation: Altering this Store (even from True to True) triggers the
            'simulation' callback, in this case resuming an in-progress simulation.
        is-active-simulation: setting this to True allows the 'simulation' callback
            to run, if it is not already.
    """

    if simulation_is_active:
        raise PreventUpdate

    return {"display": "none"}, {"display": "none"}, {}, True, True

# =========================================================================================

@dash.callback(
    Output("save-button", "children", allow_duplicate=True),
    Output("save-button", "disabled", allow_duplicate=True),
    inputs=[
        Input("save-button", "n_clicks"),
        State("blockchain-structure-data", "data"),
        State("simulation-id", "data"),
    ],
    prevent_initial_call=True,
)
def save_simulation_data(n_clicks: int, blockchain_data: list, simulation_id: str):
    """Saves the current trial data to a file when the 'save' button is clicked."""
    if n_clicks == 0:
        raise PreventUpdate
    
    save_simulation_data(blockchain_data, simulation_id)
    return "Data Saved", True  # Change button text to indicate data has been saved and disable it to prevent multiple clicks

# ========================================================================================
class ResetSimulationReturn(NamedTuple):
    """Return type for the ``reset_simulation`` callback function."""

    intro_text_classname: str = ""
    loading_text_classname: str = "display-none"
    miner_graph_and_table_classname: str = "display-none"
    view_select_and_block_status_classname: str = "visibility-hidden"
    run_button_style: dict = {}
    reset_button_style: dict = {"display": "none"}
    resume_button_style: dict = {"display": "none"}
    save_button_style: dict = {"display": "none"}
    prelim_text_classname: str = ""
    miner_slider_disabled: bool = False
    blocks_input_disabled: bool = False
    qpu_solver_select_disabled: bool = False
    simulated_solver_select_disabled: bool = False
    blockchain_data: list = []
    graphs: list[go.Figure] = dash.no_update


@dash.callback(
    Output("intro-text", "className", allow_duplicate=True),
    Output("loading-text", "className", allow_duplicate=True),
    Output("miner-graph-and-table", "className", allow_duplicate=True),
    Output("view-select-and-block-status", "className", allow_duplicate=True),
    Output("run-button", "style", allow_duplicate=True),
    Output("reset-button", "style", allow_duplicate=True),
    Output("resume-button", "style", allow_duplicate=True),
    Output("save-button", "style", allow_duplicate=True),
    Output("prelim-text", "className", allow_duplicate=True),
    Output("miner-slider", "disabled", allow_duplicate=True),
    Output("blocks-input", "disabled", allow_duplicate=True),
    Output("qpu-solver-select", "disabled", allow_duplicate=True),
    Output("simulated-solver-select", "disabled", allow_duplicate=True),
    Output("blockchain-structure-data", "data", allow_duplicate=True),
    Output({"type": "view-graph", "index": ALL}, "figure"),
    inputs=[
        Input("reset-button", "n_clicks"),
        State({"type": "view-graph", "index": ALL}, "figure"),
    ],
    prevent_initial_call=True,
)
def reset_simulation(reset_click: int, graphs: list) -> ResetSimulationReturn:
    """Resets the simulation, allowing a new simulation to be started."""

    return ResetSimulationReturn(graphs=[go.Figure()] * len(graphs))


# =======================================================================================


@dash.callback(
    Output({"type": "view-wrapper", "index": ALL}, "className"),
    inputs=[
        Input("view-select", "value"),
        State({"type": "view-wrapper", "index": ALL}, "className"),
    ],
    prevent_initial_call=True,
)
def toggle_graph_display(selected_view: str, graphs: list[str]):
    """Toggles the visibility of the four different graph displays. Will default to showing the Global
    View graph. When triggered, will hide three of the graph displays and make the selected one visible.
    """

    return_tuple = ["display-none"] * len(graphs)
    return_tuple[int(selected_view) - 1] = ""

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
    """Toggles between QPU Solver mode and Simulated Solver Mode"""
    solver_mode = SolverMode(int(solver_mode))

    if solver_mode is SolverMode.QPU:
        return "", "display-none"
    elif solver_mode is SolverMode.SIMULATED:
        return "display-none", ""

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
        collapse_trigger: The (total) number of times a collapse button has been clicked.
        to_collapse_class: Current class name of the thing to collapse, 'collapsed' if not
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
