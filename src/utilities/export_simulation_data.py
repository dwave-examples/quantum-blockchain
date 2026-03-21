
import os

from src.values import OUTPUTS_PATH
from demo_configs import MINER_NAMES
from src.structures.block import Block

def export_simulation_data(blockchain_data: list, simulation_id: str):
    """Export the blockchain data from a simulation to a JSON file."""

    # Format the blockchain data so that each dictionary in the list is a single line of a CSV file, with the keys as the column headers. 
    # This makes it easier to read and analyze the data in a spreadsheet program or with pandas.

    data_rows = []
    for block_dict in blockchain_data:
        block = Block.from_json(block_dict["block_json"])
        row = {
            "block_number": block_dict["block_number"],
            "miner": block_dict["miner_id"],
            "hash": block.hash,
            "previous_hash": block.previous_hash,
            "timestamp": block.timestamp,
            "nonce": block.nonce,
        }

        scores = block_dict["scores"]
        solvers = block_dict["solvers"]
        for miner_id in MINER_NAMES[:len(scores)]:
            row[f"{miner_id}_score"] = scores[miner_id]
            row[f"{miner_id}_solver"] = solvers[miner_id]

        data_rows.append(row)

    # Save the data to a CSV file in the outputs directory, with the filename as the simulation ID.
    # Check if a file with the same name already exists, and if so, append a number to the filename
    # to avoid overwriting.
    output_file = os.path.join(OUTPUTS_PATH, f"{simulation_id}_blockchain_data.csv")
    if os.path.exists(os.path.join(OUTPUTS_PATH, f"{simulation_id}_blockchain_data.csv")):
        i = 1
        while os.path.exists(os.path.join(OUTPUTS_PATH, f"{simulation_id}_blockchain_data_{i}.csv")):
            i += 1
        output_file = os.path.join(OUTPUTS_PATH, f"{simulation_id}_blockchain_data_{i}.csv")
    with open(output_file, "w") as f:
        # Write the column headers
        headers = data_rows[0].keys()
        f.write(",".join(headers) + "\n")
        # Write the data rows
        for row in data_rows:
            f.write(",".join(str(row[header]) for header in headers) + "\n")    