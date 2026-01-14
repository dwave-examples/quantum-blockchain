import math

from dash import html
import plotly.graph_objects as go

from demo_configs import MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_objects import TEST_TREE
from src.values import MINER_NAMES
from src.utilities.spiral_plotter import SpiralPlotter


def render_miner_status(block_number: int, miner_status: dict):
    """ Renders the status of the miners in the current trial. Each miner will be named
        "Miner n" where n is one more than their ID in TrialManager (because numbering 
        starting from Miner 0 is less aesthetic), and will have a status of "Mining, Mined,
        Validating, Valid" if they've started acting this round, or "..." if not.

    Args:
        n_intervals (unused)

    Returns:
        str: miner status table
    """

    num_miners = len(miner_status)


    table_header = f" Block {block_number}"

    miner_entries = [(miner_id, status) for miner_id, status in miner_status.items()]
    columns = min(math.ceil(num_miners / MAX_MINER_ROWS), MAX_MINER_COLUMNS)

    table_rows = []
    new_row = []
    for i in range(0, num_miners):
        new_row.append(html.Td(miner_entries[i][0]))
        new_row.append(html.Td(miner_entries[i][1]))
        if len(new_row) >= 2*columns:
            table_rows.append(html.Tr(new_row))
            new_row = []
    if len(new_row) > 0:
        table_rows.append(html.Tr(new_row))

    return table_header, table_rows

