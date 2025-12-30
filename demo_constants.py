import os
import time
from datetime import datetime
from src.structures.block import Block
from src.structures.score_tree_branch import BlockNode

PAUSE_PATH = os.path.join("static", "pause")

PAUSE_FILE = os.path.join("static", "paused.txt")

TRIAL_OUTPUTS_PATH = os.path.join("src", "trials", "outputs")

STATIC_PARAMS_FILE = os.path.join("static", "defualt_params.json")

EMBEDDINGS_DIRECTORY = os.path.join("src", "trials", "embeddings")

RUNNING_DIRECTORY_LIST = [PAUSE_PATH]

EMPTY_BLOCK_DICT = {"block_json":"", "block_number": None, "scores": []}

timestamp = datetime.timestamp(datetime.now())
genesis_block = Block(miner_id="genesis", previous_block_hash="", timestamp=timestamp)
genesis_block.set_quantum_hash()
genesis_block.set_hash()
genesis_block.lock()
GENESIS_BLOCK = genesis_block
GENESIS_BLOCKNODE = BlockNode(
                                hash=GENESIS_BLOCK.hash,
                                prev_hash=GENESIS_BLOCK.previous_hash,
                                block_score=1.0,
                                total_score=1.0,
                                block_height=0,
                                block_number=0)