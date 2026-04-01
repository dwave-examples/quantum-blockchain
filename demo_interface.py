# Copyright 2026 D-Wave
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

"""This file stores the Dash HTML layout for the app."""

from __future__ import annotations

import copy
from collections import namedtuple
from enum import EnumMeta

import dash_mantine_components as dmc
from dash import dcc, html

from demo_configs import (
    ABANDONED_BRANCH_POINT_COLOR,
    ACTIVE_BRANCH_POINT_COLOR,
    DESCRIPTION,
    HIDE_SIMULATED_SOLVERS,
    INTRO_SUBTEXT,
    INTRO_TEXT,
    LOADING_TEXT,
    MAIN_HEADER,
    MINER_NAMES,
    MINER_SLIDER,
    MINING_BLOCK_BORDER_COLOR,
    NUM_BLOCKS,
    NUM_MINER_VIEWS,
    REPLICATION_ID,
    THUMBNAIL,
    TRUNK_POINT_COLOR,
    TRUNK_TIP_COLOR,
)
from src.demo_enums import InterfaceButton, SolverMode, ViewOpt
from src.protocols.simulation_identification import get_simulation_params_from_id
from src.utilities.get_solvers import SolverName, get_solver_lists
from src.utilities.save_simulation_data import get_save_data_filename

THEME_COLOR = "#2d4376"

ViewOption = namedtuple("ViewOption", ["menu_select", "graph_name", "wrapper_name", "miner_number"])

GRAPH_VIEW_LABELS = ["Global View"] + [
    f'{" ".join(MINER_NAMES[i].split("_"))} View' for i in range(NUM_MINER_VIEWS)
]


def generate_solver_configs():
    available_qpu_solvers, available_simulated_solvers = get_solver_lists()

    qpu_solver_opts = {f"Random {SolverMode.QPU.label}": -1}

    qpu_solver_opts.update(
        {solver.solver_name: i for i, solver in enumerate(available_qpu_solvers)}
    )

    qpu_solver_configs = dict(
        label="Solver",
        id="qpu-solver-select",
        options=generate_options(qpu_solver_opts),
        initial_idx=0,
        start_disabled=False,
    )

    simulated_solver_opts = {f"Random {SolverMode.SIMULATED.label}": -1}
    simulated_solver_opts.update(
        {solver.solver_name: i for i, solver in enumerate(available_simulated_solvers)}
    )

    simulated_solver_configs = dict(
        label="Solver",
        id="simulated-solver-select",
        options=generate_options(simulated_solver_opts),
        initial_idx=0,
        start_disabled=False,
    )

    solver_mode_options = generate_options(SolverMode)

    mode_select_configs = dict(
        label="Solver Mode",
        id="solver-mode-select",
        options=solver_mode_options,
        value=solver_mode_options[0]["value"],
    )

    return qpu_solver_configs, simulated_solver_configs, mode_select_configs


def slider(label: str, id: str, config: dict) -> html.Div:
    """Slider element for value selection.

    Args:
        label: The title that goes above the slider.
        id: A unique selector for this element.
        config: A dictionary of slider configurations, see dcc.Slider Dash docs.
    """
    return html.Div(
        className="slider-wrapper",
        children=[
            html.Label(label, htmlFor=id),
            dmc.Slider(
                id=id,
                className="slider",
                **config,
                marks=[
                    {"value": config["min"], "label": f"{config['min']}"},
                    {"value": config["max"], "label": f"{config['max']}"},
                ],
                labelAlwaysOn=True,
                thumbLabel=f"{label} slider",
                color=THEME_COLOR,
            ),
        ],
    )


def dropdown(
    label: str, id: str, options: list, initial_idx: int = 0, start_disabled: bool = False
) -> html.Div:
    """Dropdown element for option selection.

    Args:
        label: The title that goes above the dropdown.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
        initial_idx: The index of the option that should be preselected.
        start_disabled: Whether the dropdown should be initially disabled.
    """

    return html.Div(
        className="dropdown-wrapper",
        children=[
            html.Label(label, htmlFor=id) if label else (),
            dmc.Select(
                id=id,
                data=options,
                value=options[initial_idx]["value"],
                allowDeselect=False,
                disabled=start_disabled,
                **{"aria-label": " ".join(id.split("-"))} if not label else {},
            ),
        ],
    )


def radio(label: str, id: str, options: list, value: str, inline: bool = True) -> html.Div:
    """Radio element for option selection.

    Args:
        label: The title that goes above the radio.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
        value: The value of the radio that should be preselected.
        inline: Whether the options are displayed beside or below each other.
    """
    return html.Div(
        className="radio-wrapper",
        children=[
            dmc.RadioGroup(
                id=id,
                className=f"radio{' radio--inline' if inline else ''}",
                label=label,
                value=value,
                children=dmc.Group(
                    [
                        dmc.Radio(option["label"], value=option["value"], color=THEME_COLOR)
                        for option in options
                    ]
                ),
            ),
        ],
    )


def input_number(label: str, id: str, config: dict) -> html.Div:
    return html.Div(
        className="blocks-input-wrapper",
        children=[
            html.Label(label, htmlFor=id),
            dmc.NumberInput(
                id=id,
                **config,
            ),
        ],
    )


def generate_options(options: list | EnumMeta | dict) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    if isinstance(options, EnumMeta):
        return [{"label": option.label, "value": f"{option.value}"} for option in options]

    if isinstance(options, dict):
        return [{"label": key, "value": f"{value}"} for key, value in options.items()]

    return [{"label": option, "value": f"{option}"} for option in options]


def generate_settings_form() -> html.Div:
    """This function generates settings for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the settings for selecting the scenario, model, and solver.
    """

    hide_simulated_solvers = HIDE_SIMULATED_SOLVERS
    miner_slider_config = copy.copy(MINER_SLIDER)
    num_blocks_config = copy.copy(NUM_BLOCKS)
    qpu_solver_configs, simulated_solver_configs, mode_select_configs = generate_solver_configs()

    # If a REPLICATION_ID is provided, the initial values of the settings will be set to match the
    # parameters encoded in that ID, and the settings will be disabled until after the first
    # simulation is run.
    if REPLICATION_ID is not None:
        init_params = get_simulation_params_from_id(REPLICATION_ID)
        miner_slider_config.update({"value": init_params["num_miners"], "disabled": True})
        num_blocks_config.update({"value": init_params["max_blocks"], "disabled": True})
        solver_list = init_params["solvers"]
        if len(solver_list) > 1:
            solver_select_idx = 0
        else:
            solver_name = solver_list[0].solver_name
            solver_name_list = [solver_name.value for solver_name in SolverName]
            solver_select_idx = solver_name_list.index(solver_name)

        if "simulated" in solver_list[0].solver_name:
            solver_select_idx -= len([x for x in SolverName if "simulated" not in x.value])
            hide_simulated_solvers = False
            simulated_solver_configs["initial_idx"] = solver_select_idx
            mode_select_configs["value"] = f"{SolverMode.SIMULATED.value}"
        else:
            qpu_solver_configs["initial_idx"] = solver_select_idx

        simulated_solver_configs["start_disabled"] = True
        qpu_solver_configs["start_disabled"] = True

    solver_settings = (
        html.Div(
            radio(**mode_select_configs),
            className="display-none" if hide_simulated_solvers else "",
        ),
        html.Div(
            id="qpu-dropdown",
            children=dropdown(**qpu_solver_configs),
        ),
        html.Div(
            id="simulated-dropdown",
            className="display-none",
            children=dropdown(**simulated_solver_configs),
        ),
    )

    return html.Div(
        className="settings",
        children=[
            slider("Number of Miners", "miner-slider", miner_slider_config),
            input_number("Number of Blocks", "blocks-input", num_blocks_config),
            *solver_settings,
        ],
    )


def generate_run_buttons() -> html.Div:
    """Start, Pause, Reset and Resume buttons for the simulation"""

    button_params = {
        button.name: dict(
            id={"type": "button", "index": button.value},
            children=button.label,
            className="button",
            style=button.init_style,
        )
        for button in InterfaceButton
    }

    return html.Div(
        id="button-group",
        children=[
            html.Button(**button_params["PAUSE"]),
            html.Div(
                id="reset-resume-buttons",
                className="",
                children=[
                    html.Button(**button_params["RESET"]),
                    html.Button(**button_params["RESUME"]),
                ],
            ),
            html.Button(**button_params["SAVE"]),
            html.Button(**button_params["START"]),
        ],
    )


def graph_legend() -> html.Div:
    """Generate graph legend"""

    legend_items = (
        ("background", TRUNK_POINT_COLOR, "Consensus"),
        ("background", ABANDONED_BRANCH_POINT_COLOR, "Abandoned"),
        ("background", ACTIVE_BRANCH_POINT_COLOR, "Undecided"),
        ("background", TRUNK_TIP_COLOR, "Available to Mine"),
        ("borderColor", MINING_BLOCK_BORDER_COLOR, "Currently Mining"),
    )
    return html.Div(
        [
            html.P([html.Span(style={style_rule: color}), label])
            for style_rule, color, label in legend_items
        ],
        className="graph-legend",
    )


def create_interface():
    """Set the application HTML."""
    return html.Div(
        id="app-container",
        children=[
            html.A(  # Skip link for accessibility
                "Skip to main content",
                href="#main-content",
                id="skip-to-main",
                className="skip-link",
            ),
            # The data in the two stores are irrelevant: they act as pass-throughs to trigger and 
            # cancel the simulation  callback when targeted by other callbacks.
            dcc.Store(id="simulation-start-target", data=False),
            dcc.Store(id="simulation-pause-target", data=False),
            dcc.Store(id="is-active-simulation", data=False),
            dcc.Store(id="current-block-data", data=""),
            dcc.Store(id="blockchain-structure-data", data=[]),
            dcc.Store(id="miner-status-data", data=[]),
            dcc.Store(
                id="simulation-save-filename",
                data="" if REPLICATION_ID is None else get_save_data_filename(REPLICATION_ID),
            ),
            # Settings and results columns
            html.Main(
                className="columns-main",
                id="main-content",
                children=[
                    # Left column
                    html.Div(
                        id={"type": "to-collapse-class", "index": 0},
                        className="left-column",
                        children=[
                            html.Div(
                                className="left-column-layer-1",  # Fixed width Div to collapse
                                children=[
                                    html.Div(
                                        className="left-column-layer-2",  # Padding and content wrapper
                                        children=[
                                            html.Div(
                                                [
                                                    html.H1(MAIN_HEADER),
                                                    html.P(DESCRIPTION),
                                                ],
                                                className="title-section",
                                            ),
                                            html.Div(
                                                [
                                                    html.Div(
                                                        html.Div(
                                                            [
                                                                generate_settings_form(),
                                                                generate_run_buttons(),
                                                            ],
                                                            className="settings-and-buttons",
                                                        ),
                                                        className="settings-and-buttons-wrapper",
                                                    ),
                                                    # Left column collapse button
                                                    html.Div(
                                                        html.Button(
                                                            id={
                                                                "type": "collapse-trigger",
                                                                "index": 0,
                                                            },
                                                            className="left-column-collapse",
                                                            title="Collapse sidebar",
                                                            children=[
                                                                html.Div(className="collapse-arrow")
                                                            ],
                                                            **{"aria-expanded": "true"},
                                                        ),
                                                    ),
                                                ],
                                                className="form-section",
                                            ),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    ),
                    # Right column
                    html.Div(
                        className="right-column",
                        children=[
                            html.Header(
                                className="banner",
                                children=[
                                    html.Div(
                                        [
                                            dropdown(
                                                "",
                                                "view-select",
                                                generate_options(ViewOpt),
                                            ),
                                            html.H4(id="block-status"),
                                        ],
                                        className="visibility-hidden",
                                        id="view-select-and-block-status",
                                    ),
                                    html.Img(src=THUMBNAIL, alt="D-Wave logo"),
                                ],
                            ),
                            html.Div(
                                className="tab-content-wrapper",
                                children=[
                                    html.Div(
                                        id="prelim-text",
                                        className="",
                                        children=[
                                            html.Div(
                                                children=[
                                                    html.H3(INTRO_TEXT),
                                                    html.P(INTRO_SUBTEXT),
                                                ],
                                                id="intro-text",
                                            ),
                                            html.H3(
                                                LOADING_TEXT,
                                                id="loading-text",
                                                className="display-none",
                                            ),
                                        ],
                                    ),
                                    html.Div(
                                        className="display-none",
                                        id="miner-graph-and-table",
                                        children=[
                                            html.Div(
                                                className="graph-table-wrapper",
                                                children=[
                                                    html.Div(
                                                        [
                                                            dcc.Loading(
                                                                parent_className="graph-loading",
                                                                id="graph-loading",
                                                                type="circle",
                                                                color=THEME_COLOR,
                                                                children=[
                                                                    html.Div(
                                                                        id={
                                                                            "type": "view-wrapper",
                                                                            "index": i,
                                                                        },
                                                                        className=f"graph-wrapper {'display-none' if i > 0 else ''}",
                                                                        tabIndex=f"{10 + i}",
                                                                        children=[
                                                                            dcc.Graph(
                                                                                id={
                                                                                    "type": "view-graph",
                                                                                    "index": i,
                                                                                },
                                                                                responsive=True,
                                                                                config={
                                                                                    "displayModeBar": False
                                                                                },
                                                                            ),
                                                                        ],
                                                                        **{"role": "presentation"},
                                                                    )
                                                                    for i, view in enumerate(
                                                                        ViewOpt
                                                                    )
                                                                ],
                                                            ),
                                                            graph_legend(),
                                                        ]
                                                    ),
                                                    html.Div(html.Table(id="miner-status-table")),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
