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
from src.utilities.get_solvers import get_solver_lists
from src.utilities.save_simulation_data import get_save_data_filename

THEME_COLOR = "#2d4376"

ViewOption = namedtuple("ViewOption", ["menu_select", "graph_name", "wrapper_name", "miner_number"])

GRAPH_VIEW_LABELS = ["Global View"] + [
    f'{" ".join(MINER_NAMES[i].split("_"))} View' for i in range(NUM_MINER_VIEWS)
]

BUTTONS = {
    button.name: html.Button(
        id={"type": "button", "index": button.value},
        children=button.label,
        className=f"button {button.name.lower()}-button",
        style=button.init_style,
    )
    for button in InterfaceButton
}

available_qpu_solvers, simulated_solvers = get_solver_lists()
single_qpu_opts = {solver.solver_name: i for i, solver in enumerate(available_qpu_solvers)}
QPU_SOLVER_OPTS = {f"Random {SolverMode.QPU.label}": -1} | single_qpu_opts
single_simulated_opts = {solver.solver_name: i for i, solver in enumerate(simulated_solvers)}
SIMULATED_SOLVER_OPTS = {f"Random {SolverMode.SIMULATED.label}": -1} | single_simulated_opts


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
    label: str, id: str, options: list, value: str | None = None, disabled: bool = False
) -> html.Div:
    """Dropdown element for option selection.

    Args:
        label: The title that goes above the dropdown.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
        value: The value of the option that should be preselected.
        disabled: Whether the dropdown should be initially disabled.
    """

    return html.Div(
        className="dropdown-wrapper",
        children=[
            html.Label(label, htmlFor=id) if label else (),
            dmc.Select(
                id=id,
                data=options,
                value=value if value in [opt["value"] for opt in options] else options[0]["value"],
                allowDeselect=False,
                disabled=disabled,
                **{"aria-label": " ".join(id.split("-"))} if not label else {},
            ),
        ],
    )


def radio(
    label: str, id: str, options: list, value: str, inline: bool = True, disabled: bool = False
) -> html.Div:
    """Radio element for option selection.

    Args:
        label: The title that goes above the radio.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
        value: The value of the radio that should be preselected.
        inline: Whether the options are displayed beside or below each other.
        disabled: Whether the radio should be initially disabled.
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
                        dmc.Radio(
                            option["label"],
                            value=option["value"],
                            disabled=disabled,
                            color=THEME_COLOR,
                        )
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
    """This function generates settings for selecting number of blocks and miners, as well as the
    solver settings. The HIDE_SIMULATED_SOLVERS and REPLICATION_ID parameters from demo_configs.py
    affect the initial state of the solver settings options, as described in that file.

    Returns:
        html.Div: A Div containing the settings form."""

    hide_simulated_solvers = HIDE_SIMULATED_SOLVERS
    miner_slider_config = copy.copy(MINER_SLIDER)
    num_blocks_config = copy.copy(NUM_BLOCKS)

    qpu_solver_value = ""
    simulated_solver_value = ""

    solver_mode_options = generate_options(SolverMode)
    solver_mode_value = solver_mode_options[0]["value"]

    # If a REPLICATION_ID is provided, the initial values of the settings will be set to match the
    # parameters encoded in that ID, and the settings will be disabled until after the first
    # simulation is run.
    if REPLICATION_ID is not None:
        init_params = get_simulation_params_from_id(REPLICATION_ID)
        miner_slider_config.update({"value": init_params["num_miners"], "disabled": True})
        num_blocks_config.update({"value": init_params["max_blocks"], "disabled": True})
        solver_list = init_params["solvers"]

        if "simulated" in solver_list[0].solver_name:
            hide_simulated_solvers = False
            simulated_solver_value = "" if len(solver_list) > 1 else solver_list[0].solver_name
            solver_mode_value = f"{SolverMode.SIMULATED.value}"
        else:
            qpu_solver_value = "" if len(solver_list) > 1 else solver_list[0].solver_name

    solver_settings = (
        html.Div(
            radio(
                label="Solver Mode",
                id="solver-mode-select",
                options=solver_mode_options,
                value=solver_mode_value,
                disabled=REPLICATION_ID is not None,
            ),
            className="display-none" if hide_simulated_solvers else "",
        ),
        html.Div(
            id="qpu-dropdown",
            children=dropdown(
                label="Solver",
                id="qpu-solver-select",
                options=generate_options(QPU_SOLVER_OPTS),
                value=qpu_solver_value,
                disabled=REPLICATION_ID is not None,
            ),
        ),
        html.Div(
            id="simulated-dropdown",
            className="display-none",
            children=dropdown(
                label="Solver",
                id="simulated-solver-select",
                options=generate_options(SIMULATED_SOLVER_OPTS),
                value=simulated_solver_value,
                disabled=REPLICATION_ID is not None,
            ),
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

    return html.Div(
        id="button-group",
        children=[
            BUTTONS["PAUSE"],
            html.Div(
                id="reset-resume-buttons",
                className="",
                children=[
                    BUTTONS["RESET"],
                    BUTTONS["RESUME"],
                ],
            ),
            BUTTONS["SAVE"],
            BUTTONS["START"],
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
            # First store exists only to be a target to trigger callbacks when the data is updated;
            # actual value of its data is irrelevant.
            dcc.Store(id="simulation-pause-target", data=False),
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
