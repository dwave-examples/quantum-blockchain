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

"""This file stores the Dash HTML layout for the app."""
from __future__ import annotations

from dash import dcc, html
import dash_mantine_components as dmc

from demo_configs import (
    DESCRIPTION,
    MAIN_HEADER,
    NUM_BLOCKS,
    THUMBNAIL,
    MINER_SLIDER,
    DISPLAY_REFRESH_RATE,
    INTRO_TEXT,
    INTRO_SUBTEXT,
    LOADING_TEXT,
)

from demo_solvers import AVAILABLE_SOLVERS
from demo_constants import EMPTY_BLOCK_DICT
from src.values import MINER_NAMES

THEME_COLOR = "#2d4376"


def slider(label: str, id: str, config: dict) -> html.Div:
    """Slider element for value selection.

    Args:
        label: The title that goes above the slider.
        id: A unique selector for this element.
        config: A dictionary of slider configerations, see dcc.Slider Dash docs.
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
                    {"value": config["min"], "label": f"{config["min"]}"},
                    {"value": config["max"], "label": f"{config["max"]}"},
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


def input_number(label: str, id: str, config: dict) -> html.Div:
    return html.Div(
        className="blocks-input-wrapper",
        children=[
            html.Label(label, htmlFor=id),
            dmc.NumberInput(
                id=id,
                **config,
            )
        ],
    )


def generate_options(options_list: list) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    return [{"label": label, "value": f"{i}"} for i, label in enumerate(options_list)]


def generate_options_dropdown(options_list: list) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    return [{"label": label, "value": f"{i}"} for i, label in enumerate(options_list)]


def generate_settings_form() -> html.Div:
    """This function generates settings for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the settings for selecting the scenario, model, and solver.
    """
    solver_opts = [slvr.solver_name for slvr in AVAILABLE_SOLVERS]
    solver_opts += ["Random QPU", "Random Simulated Solver"]

    return html.Div(
        className="settings",
        children=[
            slider(
                "Number of Miners",
                "miner-slider",
                MINER_SLIDER,
            ),
            input_number("Number of Blocks", "blocks-input", NUM_BLOCKS),
            dropdown("Solver", "solver-select", generate_options_dropdown(solver_opts)),
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
                children="Pause Simulation",
                n_clicks=0,
                className="display-none",
            ),
            html.Div(
                id="reset-resume-buttons",
                className="",
                children=[
                    html.Button(
                        id="reset-button",
                        children="Reset Simulation",
                        n_clicks=0,
                        className="display-none",
                    ),
                    html.Button(id="resume-button",
                        children="Resume",
                        n_clicks=0,
                        className="display-none",
                    ),
                ]
            )
        ],
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

            dcc.Store(id="running-status", data=False),
            dcc.Store(id="paused-status", data=False),
            dcc.Store(id="current-block-data", data=""),
            dcc.Store(id="blockchain-structure-data", data =[]),
            dcc.Store(id="miner-status-data", data={}),
            dcc.Store(id="blocks-mined", data=0),

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
                                    dropdown("", "view-select", generate_options_dropdown([MINER_NAMES[i] for i in range(3)])),
                                    html.Div(
                                        className="graph-table-wrapper",
                                        children=[
                                            html.Div(
                                                className="graph-wrapper",
                                                children=[
                                                    dcc.Graph(
                                                        id="miner-graph-display",
                                                        responsive=True,
                                                        config={"displayModeBar": False},
                                                    ),
                                                ]
                                            ),
                                            html.Div([
                                                html.H4(id="miner-table-head"),
                                                html.Table(
                                                    id="miner-status-table",
                                                    children=[
                                                        html.Thead(
                                                            html.Tr(
                                                                [
                                                                    html.Th("Miner"),
                                                                    html.Th("Status"),
                                                                ],
                                                            )
                                                        ),
                                                        html.Tbody(id="miner-table-body"),
                                                    ]
                                                ),
                                            ]),
                                        ]
                                    )
                                ]
                            )
                        ],
                    ),
                ],
            ),
        ],
    )