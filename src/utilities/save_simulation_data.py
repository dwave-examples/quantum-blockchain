import os
import csv

from src.values import OUTPUTS_PATH
from demo_configs import MINER_NAMES
from src.structures.block import Block

def get_save_data_filename(simulation_id: str) -> str:
    """Generate a filename for saving the blockchain data from a simulation, using the simulation ID as the first part of the filename. 
    If a file with the same name already exists, append a number to the filename to avoid overwriting.
    
    Args:
        simulation_id (str): The unique identifier for the simulation, used as the first part of the filename for the output CSV."""
    
    basename = f"{simulation_id}_blockchain_data"

    candidate_filename = f"{basename}.csv"
    i=1
    while os.path.exists(os.path.join(OUTPUTS_PATH, candidate_filename)):
        i += 1
        candidate_filename = f"{basename}_{i}.csv"
        
    return candidate_filename

def save_simulation_data(blockchain_data: list, filename: str):
    """Export the blockchain data from a simulation to a CSV file in the outputs directory, using 
    the provided filename. 
    
    Args:
        blockchain_data (list): A list of dictionaries, each containing data for a single block.
        filename (str): The name of the file to save the blockchain data to, including the .csv extension."""

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
            if miner_id in scores:
                row[f"{miner_id}_score"] = scores[miner_id]
                row[f"{miner_id}_solver"] = solvers[miner_id]

        data_rows.append(row)

    if not os.path.exists(OUTPUTS_PATH):
        os.makedirs(OUTPUTS_PATH)

    output_filepath = os.path.join(OUTPUTS_PATH, filename)

    with open(output_filepath, "w") as f:
        writer = csv.DictWriter(f, fieldnames=data_rows[0].keys(), restval="")
        writer.writeheader()
        writer.writerows(data_rows)
