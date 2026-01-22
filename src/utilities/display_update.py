from dash import html
from src.values import MINER_NAMES


def render_miner_status(
        current_block_data: dict,
        num_miners: int,
        show_solvers=False
) -> list:
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
