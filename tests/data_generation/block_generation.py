import random

from datetime import datetime

from src.structures.block import Block

class BlockGenerator:
    """Uses a transaction generator to generate blocks for addition to
    a blockchain. Can generate a list of sequential blocks with the
    generate_chain method."""

    def __init__(self):

        timestamp = datetime.timestamp(datetime.now())
        genesis_block = Block(miner_id="genesis", previous_block_hash="", timestamp=timestamp)
        genesis_block.set_quantum_hash()
        genesis_block.set_hash()
        genesis_block.lock()
        self.genesis_block = genesis_block

    def generate_block(self, previous_block=None):

        if previous_block:
            prev_hash = previous_block.hash
        else:
            prev_hash = self.genesis_block.hash

        timestamp = datetime.timestamp(datetime.now())
        nonce = random.randint(1, 2**30)
        new_block = Block( miner_id= "test_miner",
            previous_block_hash=prev_hash,
            timestamp=timestamp,
            nonce=nonce)
        
        new_block.set_quantum_hash()
        new_block.set_hash()
        new_block.lock()

        return new_block

    def generate_chain(self, num_blocks=2, initial_block=None):
        blocks = []

        prev_block = initial_block

        for i in range(num_blocks):
            new_block = self.generate_block(prev_block)
            blocks.append(new_block)
            prev_block = new_block

        return blocks
