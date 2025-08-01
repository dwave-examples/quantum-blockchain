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

from demo_utils import pad_name
from demo_configs import (
    DESCRIPTION,
    MAIN_HEADER,
    THEME_COLOR_SECONDARY,
    THUMBNAIL,
    MINER_STATS_FILE,
    MINER_SLIDER
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


def generate_miner_status_table() -> list[html.Tr]:
    """Generates table rows 
    """

    if os.path.exists(MINER_STATS_FILE):
        with open(MINER_STATS_FILE, 'r') as f:
            miner_dict = json.load(f)

        miner_status = miner_dict["Miners"]
        block_number = miner_dict["Block"] + 1
        miner_names = [f"Miner {i}" for i in range(1, len(miner_status)+1)]
        max_name = max([len(e) for e in miner_names])
        round_state = "Mining"
        max_state = max([len(e) for e in miner_status])
        if max_state > len(round_state):
            round_state = "Validating"
        max_length = max(max_name, max_state)
        for i in range(len(miner_names)):
            miner_names[i] = pad_name(miner_names[i], max_length)
            miner_status[i] = pad_name(miner_status[i], max_length)


        table_header = [" " for item in miner_status]
        start_index = (len(table_header)//2)
        table_header[start_index] = round_state
        table_header[start_index + 1] = f"Block {block_number}"
        table_rows = (
            table_header,
            [name for name in miner_names],
            [stat for stat in miner_status]
        )

    else:
        table_rows = ([""])

    return [html.Tr([html.Td(cell) for cell in row]) for row in table_rows]

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
                            dcc.Interval(id="miner-status-update", interval=101),  
                            html.Div(id="miner-status"),   
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
                                            dcc.Interval(id="miner-graph-update", interval=102),
                                            html.Img(id="miner-display", width=800),                                  
                                        ],
                                    ),
                                    dcc.Tab(
                                        label="Global View",
                                        id="global-tab",
                                        value="global-tab",
                                        className="tab",
                                        children=[
                                            dcc.Interval(id="global-graph-update", interval=103),
                                            html.Img(id="global-display", width=800),
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
