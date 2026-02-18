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

from collections import namedtuple

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
    THUMBNAIL,
    TRUNK_POINT_COLOR,
    TRUNK_TIP_COLOR,
)
from src.demo_enums import SolverMode
from src.utilities.get_solvers import get_solver_lists

THEME_COLOR = "#2d4376"

ViewOption = namedtuple("ViewOption", ["menu_select", "graph_name", "wrapper_name", "miner_number"])

GRAPH_VIEW_LABELS = ["Global View"] + [f"{MINER_NAMES[i]} View" for i in range(NUM_MINER_VIEWS)]


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


def dropdown(label: str, id: str, options: list) -> html.Div:
    """Dropdown element for option selection.

    Args:
        label: The title that goes above the dropdown.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
    """

    return html.Div(
        className="dropdown-wrapper",
        children=[
            html.Label(label, htmlFor=id) if label else (),
            dmc.Select(
                id=id,
                data=options,
                value=options[0]["value"],
                allowDeselect=False,
            ),
        ],
    )


def radio(
    label: str, id: str, options: list, value: int, inline: bool = True, class_name=""
) -> html.Div:
    """Radio element for option selection.

    Args:
        label: The title that goes above the radio.
        id: A unique selector for this element.
        options: A list of dictionaries of labels and values.
        value: The value of the radio that should be preselected.
        inline: Whether the options are displayed beside or below each other.
    """
    return html.Div(
        className=class_name,
        children=[
            html.Label(label, htmlFor=id),
            dcc.RadioItems(
                id=id,
                className=f"radio{' radio--inline' if inline else ''}",
                inline=inline,
                options=options,
                value=value,
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


def generate_options(options_list: list) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    return [{"label": label, "value": i} for i, label in enumerate(options_list)]


def generate_options_dropdown(options_list: list) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    return [{"label": label, "value": f"{i}"} for i, label in enumerate(options_list)]


def generate_settings_form() -> html.Div:
    """This function generates settings for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the settings for selecting the scenario, model, and solver.
    """
    available_qpu_solvers, available_simulated_solvers = get_solver_lists()

    qpu_solver_opts = [f"Random {SolverMode.QPU.label}"]
    qpu_solver_opts += [solver.solver_name for solver in available_qpu_solvers]

    simulated_solver_opts = [f"Random {SolverMode.SIMULATED.label}"]
    simulated_solver_opts += [solver.solver_name for solver in available_simulated_solvers]

    solver_mode_options = [
        {"label": solver_mode.label, "value": solver_mode.value} for solver_mode in SolverMode
    ]

    solver_settings = (
        radio(
            "Solver Mode",
            "solver-mode-select",
            solver_mode_options,
            solver_mode_options[0]["value"],
            class_name="display-none" if HIDE_SIMULATED_SOLVERS else "",
        ),
        html.Div(
            id="qpu-dropdown",
            children=dropdown(
                "Solver", "qpu-solver-select", generate_options_dropdown(qpu_solver_opts)
            ),
        ),
        html.Div(
            id="simulated-dropdown",
            className="display-none",
            children=dropdown(
                "Solver",
                "simulated-solver-select",
                generate_options_dropdown(simulated_solver_opts),
            ),
        ),
    )

    return html.Div(
        className="settings",
        children=[
            slider("Number of Miners", "miner-slider", MINER_SLIDER),
            input_number("Number of Blocks", "blocks-input", NUM_BLOCKS),
            *solver_settings,
        ],
    )


def generate_run_buttons() -> html.Div:
    """Run, Pause, Reset and Resume buttons for the simulation"""
    return html.Div(
        id="button-group",
        children=[
            html.Button(id="run-button", children="Start Simulation", n_clicks=0, disabled=False),
            html.Button(
                id="pause-button",
                children="Pause",
                n_clicks=0,
                className="display-none",
            ),
            html.Div(
                id="reset-resume-buttons",
                className="",
                children=[
                    html.Button(
                        id="reset-button",
                        children="Reset",
                        n_clicks=0,
                        className="display-none",
                    ),
                    html.Button(
                        id="resume-button",
                        children="Resume",
                        n_clicks=0,
                        className="display-none",
                    ),
                ],
            ),
        ],
    )


def graph_legend() -> html.Div:
    """Generate graph legend"""

    legend_items = (
        ("background", TRUNK_POINT_COLOR, "Consensus"),
        ("background", ABANDONED_BRANCH_POINT_COLOR, "Abandoned"),
        ("background", ACTIVE_BRANCH_POINT_COLOR, "Undecided"),
        ("background", TRUNK_TIP_COLOR, "Available to Mine"),
        ("border-color", MINING_BLOCK_BORDER_COLOR, "Currently Mining"),
    )
    return html.Div(
        [
            html.P(
                [html.Span(style={style_rule: color}), label]
            ) for style_rule, color, label in legend_items
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
            # The data in this first store is irrelevant: it acts as a pass-through to trigger the
            # simulation callback when targeted by other callbacks.
            dcc.Store(id="start-simulation", data=False),
            dcc.Store(id="is-active-simulation", data=False),
            dcc.Store(id="current-block-data", data=""),
            dcc.Store(id="blockchain-structure-data", data=[]),
            # Header brand banner
            html.Header(className="banner", children=[html.Img(src=THUMBNAIL, alt="D-Wave logo")]),
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
                                            html.H1(MAIN_HEADER),
                                            html.P(DESCRIPTION),
                                            generate_settings_form(),
                                            generate_run_buttons(),
                                        ],
                                    )
                                ],
                            ),
                            # Left column collapse button
                            html.Div(
                                html.Button(
                                    id={"type": "collapse-trigger", "index": 0},
                                    className="left-column-collapse",
                                    title="Collapse sidebar",
                                    children=[html.Div(className="collapse-arrow")],
                                    **{"aria-expanded": "true"},
                                ),
                            ),
                        ],
                    ),
                    # Right column
                    html.Div(
                        className="right-column",
                        children=[
                            html.Div(
                                id="prelim-text",
                                className="",
                                children=[
                                    html.Div(
                                        children=[html.H3(INTRO_TEXT), html.P(INTRO_SUBTEXT)],
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
                                        [
                                            dropdown(
                                                "",
                                                "view-select",
                                                generate_options_dropdown(
                                                    [label for label in GRAPH_VIEW_LABELS]
                                                ),
                                            ),
                                            html.H4(id="block-status"),
                                        ],
                                    ),
                                    html.Div(
                                        className="graph-table-wrapper",
                                        children=[
                                            html.Div(
                                                [
                                                    dcc.Loading(
                                                        parent_className="graph-loading",
                                                        overlay_style={
                                                            "visibility": "visible",
                                                            "opacity": "0.5",
                                                        },
                                                        type="circle",
                                                        color=THEME_COLOR,
                                                        children=[
                                                            html.Div(
                                                                id={"type": "view_wrapper", "index": i},
                                                                className=f"graph-wrapper {'display-none' if i > 0 else ''}",
                                                                children=[
                                                                    dcc.Graph(
                                                                        id={"type": "view_graph", "index": i},
                                                                        responsive=True,
                                                                        config={
                                                                            "displayModeBar": False
                                                                        },
                                                                    ),
                                                                ],
                                                            )
                                                            for i in range(len(GRAPH_VIEW_LABELS))
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
    )
