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
import json, os
import plotly.graph_objects as go
import plotly.express as px

from demo_configs import (
    DESCRIPTION,
    MAIN_HEADER,
    THUMBNAIL,
    MINER_SLIDER,
    DISPLAY_REFRESH_RATE,
    INTRO_TEXT,
    INTRO_SUBTEXT,
    LOADING_TEXT
)


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
            html.Label(label),
            dcc.Slider(
                id=id,
                className="slider",
                **config,
                marks={
                    config["min"]: str(config["min"]),
                    config["max"]: str(config["max"]),
                },
                tooltip={
                    "placement": "bottom",
                    "always_visible": True,
                },
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
            html.Label(label),
            dcc.Dropdown(
                id=id,
                options=options,
                value=options[0]["value"],
                clearable=False,
                searchable=False,
            ),
        ],
    )


def num_blocks_input() -> html.Div:
    return html.Div(
        className="blocks-input-wrapper",
        children=[
            html.Label("Number of Blocks"),
            dcc.Input(
                value=10,
                id = "blocks-input",
                type= "number",
                min=2,
                max=200,
                step=1
            )
        ],
    )

def generate_view_select(num_miners):
    global_opt = ["Global View"]
    miner_opts = [f"Miner {i+1}" for i in range(num_miners)]
    view_opts = global_opt + miner_opts
    return html.Div(
        className="dropdown-wrapper",
        children=[
            html.Label("Select View"),
            dcc.Dropdown(
                id="view-select",
                options=view_opts,
                value=view_opts[1],
                clearable=False,
                searchable=False,
            ),
        ],
    )

def generate_options(options_list: list) -> list[dict]:
    """Generates options for dropdowns, checklists, radios, etc."""
    return [{"label": label, "value": i} for i, label in enumerate(options_list)]


def generate_settings_form() -> html.Div:
    """This function generates settings for selecting the scenario, model, and solver.

    Returns:
        html.Div: A Div containing the settings for selecting the scenario, model, and solver.
    """

    return html.Div(
        className="settings",
        children=[
            slider(
                "Number of Miners",
                "miner-slider",
                MINER_SLIDER,
            ),
            num_blocks_input(),
        ],
    )


def generate_run_buttons() -> html.Div:
    """Run, Pause, Reset and Resume buttons for the simulation"""
    return html.Div(
        id="button-group",
        children=[
            html.Button(id="run-button", children="Begin Simulation", n_clicks=0, disabled=False),
            html.Button(
                id="pause-button",
                children="Pause Simulation",
                n_clicks=0,
                className="display-none",
            ),
            html.Button(id="reset-button", 
                        children="Reset Simulation", 
                        n_clicks=0, 
                        className="display-none",
            ),
            html.Button(id="resume-button", 
                        children="Resume Simulation", 
                        n_clicks=0, 
                        className="display-none",
            ),
        ],
    )

def create_interface():
    """Set the application HTML."""
    return html.Div(
        id="app-container",
        children=[
            # Below are any temporary storage items, e.g., for sharing data between callbacks.
            dcc.Store(id="run-status", data={"Running": False, "Paused": False}),  # Indicates whether run is in progress and whether the run is paused
            dcc.Interval(id="display-update", interval=DISPLAY_REFRESH_RATE),
            dcc.Store(id="block-number-data", data=0),
            dcc.Store(id="graph-data", data=[]),    #Stores graph data for all miners
            dcc.Store(id="graph-data-temp", data=[]), #Allows partial updates to be passed through to graph-data
            # Header brand banner
            html.Div(className="banner", children=[html.Img(src=THUMBNAIL)]),
            # Settings and results columns
            html.Div(
                className="columns-main",
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
                                            html.Div(id="view-select-wrapper"),
                                        ],
                                    )
                                ],
                            ),
                            # Left column collapse button
                            html.Div(
                                html.Button(
                                    id={"type": "collapse-trigger", "index": 0},
                                    className="left-column-collapse",
                                    children=[html.Div(className="collapse-arrow")],
                                ),
                            ),
                        ],
                    ),
                    # Right column
                    html.Div(
                        className="right-column",
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
                            html.Div(
                                className="display-none",
                                id="graph-wrapper",
                                children=[
                                    dcc.Graph(
                                        id="miner-graph-display",
                                        config={"displayModeBar": False},
                                    ),
                                    html.Div([ #TODO move outside of graph wrapper so miner table will update before first graph is ready.
                                        html.H4(id="miner-table-head"),
                                        html.Table(
                                            id="miner-status-table",
                                            children=[
                                                html.Thead(
                                                    html.Tr(
                                                        [
                                                            html.Th("Miner"),
                                                            html.Th("Status"),
                                                        ]
                                                    )
                                                ),
                                                html.Tbody(id="miner-table-body"),
                                            ]
                                        ),
                                    ]),
                                ]
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
