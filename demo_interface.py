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

from demo_configs import (
    DESCRIPTION,
    MAIN_HEADER,
    THUMBNAIL,
    MINER_SLIDER,
    GRAPH_WIDTH,
    DISPLAY_REFRESH_RATE
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
            dcc.Store(id="run-in-progress", data=False),  # Indicates whether run is in progress
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
                            html.Div(id="run-status", children="Ready"),
                            html.Div(id="pause-status", children=""),  
                            html.Div(id="miner-status", children=[
                                                                  dcc.Interval(id="miner-status-table-update", interval=DISPLAY_REFRESH_RATE),
                                                                  html.Table(id="miner-status-table", children = 
                                                                                                                [
                                                                                                                html.Thead(id="miner-table-head"),
                                                                                                                html.Tbody(id="miner-table-body"),
                                                                                                                ],
                                                                            )
                                                                  ],
                                    ),   
                            dcc.Tabs(
                                id="tabs",
                                value="miner-tab",
                                mobile_breakpoint=0,
                                children=[
                                    dcc.Tab(
                                        label="Miner View",
                                        id="miner-tab",
                                        value="miner-tab",  # used for switching tabs programatically
                                        className="tab",
                                        children=[
                                            dcc.Interval(id="miner-graph-update", interval=DISPLAY_REFRESH_RATE),
                                            html.Img(id="miner-display", width=GRAPH_WIDTH),                                  
                                        ],
                                    ),
                                    dcc.Tab(
                                        label="Global View",
                                        id="global-tab",
                                        value="global-tab",
                                        className="tab",
                                        children=[
                                            dcc.Interval(id="global-graph-update", interval=DISPLAY_REFRESH_RATE),
                                            html.Img(id="global-display", width=GRAPH_WIDTH),
                                        ]
                                    ),
                                ],
                            )
                        ],
                    ),
                ],
            ),
        ],
    )
