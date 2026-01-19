import math

from dash import html


def render_miner_status(
    block_number: int, miner_status: dict, show_solvers=False
) -> tuple[str, list]:
    """Renders the status of the miners in the current trial. Each miner will be named
        "Miner n" where n is one more than their ID in TrialManager (because numbering
        starting from Miner 0 is less aesthetic), and will have a status of "Mining, Mined,
        Validating, Valid" if they've started acting this round, or "..." if not.

    Args:
        block_number: The current block.
        miner_status: The current statuses of all the miners.
        show_solvers: Whether to have a third column showing the solver used.

    Returns:
        str: Header to show above status table.
        list: Miner status table.
    """

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
        for miner_id, status in miner_status.items()
    ]

    table_rows = []
    for row in miner_entries:
        new_row = []
        for cell in row:
            new_row.append(html.Td(cell, className=f"{cell.lower()}-cell"))

        table_rows.append(html.Tr(new_row))

    return f"Currently mining block {block_number}", [table_head, html.Tbody(table_rows)]
