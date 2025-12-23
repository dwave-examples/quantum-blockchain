import math

from dash import html
import plotly.graph_objects as go

from demo_configs import MAX_MINER_ROWS, MAX_MINER_COLUMNS
from demo_objects import TEST_TREE
from src.values import MINER_NAMES
from src.utilities.spiral_plotter import SpiralPlotter
from src.utilities.graph_processor import generate_graph_data


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

def render_graphs(graph_data: dict):
    """Updates the display for the miner tab, showing the graph
        of the current chain state if it is available.


        Args:
            miner-graph-update: interval set to check if there is anything to update
            run-status: if run status alters, display should alter
            tabs: should automatically render on switching tabs.

        Returns:
            graph-file"""
   

    plotter = SpiralPlotter()
    graph_data = generate_graph_data(graph_data)
    plotter.import_plotting_data(tree_data=graph_data, num_nodes=8)
    plot_data = plotter.plot_spiral()
    fig = go.Figure(plot_data)

    fig.update_layout( #TODO move to configs and figure out how to use relative units for graph size
        autosize=False,
        width=700,
        height=700,
        showlegend = False,
        xaxis = dict(showticklabels=False),
        yaxis = dict(showticklabels=False),
        margin=dict(
            l=0,
            r=0,
            b=0,
            t=0,
            pad=4
            ),
        paper_bgcolor="White",
        plot_bgcolor="White",
        )

    return fig