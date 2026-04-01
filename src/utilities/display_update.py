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

from dash import dash, html

from demo_configs import MINER_NAMES
from src.demo_enums import InterfaceButton


def change_button_visibility(
    buttons_to_show: list[InterfaceButton], buttons_to_hide: list[InterfaceButton]
) -> list[dict]:
    """Returns a list of style dicts to show or hide the given buttons. The order of the list
        corresponds to the order of the InterfaceButton enum, so for example if buttons_to_show
        is [InterfaceButton.PAUSE], the returned list will have a dict of {} at index 0 and
        dash.no_update at all other indices.

    Args:
        buttons_to_show: List of buttons to show.
        buttons_to_hide: List of buttons to hide.

    Returns:
        List of style dicts to show or hide the given buttons.
    """
    outputs = [dash.no_update] * len(InterfaceButton)
    for button in buttons_to_show:
        outputs[button.value] = {}
    for button in buttons_to_hide:
        outputs[button.value] = {"display": "none"}

    return outputs


def render_miner_status(current_block_data: dict, num_miners: int, show_solvers=False) -> list:
    """Renders the status of the miners in the current simulation. Miner names will be drawn from
        the MINER_NAMES list in demo_configs.py. Miners will have a status of "Mined" or "Validate"
        if they've started acting this round, and blank status otherwise.

    Args:
        current_block_data: The data for the current block, which includes the miner IDs, their scores,
            and the solvers they used.
        num_miners: The total number of miners in the simulation
        show_solvers: Whether to have a third column showing the solver used.

    Returns:
        str: Header to show above status table.
        list: Miner status table.
    """

    mining_id = current_block_data["miner_id"]

    miner_status_dict = {MINER_NAMES[i]: ["", ""] for i in range(num_miners)}
    for miner_id, score in current_block_data["scores"].items():
        status = "Validated" if score > 0 else "Rejected"
        miner_status_dict[miner_id][0] = status

    miner_status_dict[mining_id][0] = "Mined"

    for miner_id, solver in current_block_data["solvers"].items():
        if "simulated_" in solver:
            solver_str = solver.replace("simulated_", "")
        else:
            solver_substrings = solver.split("_system")
            solver_str = f"{solver_substrings[0]} {solver_substrings[1]}"
        miner_status_dict[miner_id][1] = solver_str

    table_head = html.Thead(
        html.Tr(
            [
                html.Th("Miner"),
                html.Th("Status"),
                html.Th("Solver") if show_solvers else (),
            ],
        )
    )

    miner_entries = [
        (miner_id.replace("_", " "), *status[: 2 if show_solvers else 1])
        for miner_id, status in miner_status_dict.items()
    ]

    table_rows = []
    for row in miner_entries:
        new_row = []
        for cell in row:
            new_row.append(html.Td(cell, className=f"{cell.lower()}-cell"))

        table_rows.append(html.Tr(new_row))

    return [table_head, html.Tbody(table_rows)]
