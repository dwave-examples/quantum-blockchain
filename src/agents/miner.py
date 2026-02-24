# Copyright 2026 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing permissions and limitations under
# the License.
#
# The use of code in the quantum-blockchain repository with a quantum computing system is protected
# by the intellectual property rights of D-Wave Quantum Inc. and its affiliates.
#
# The use of code in the quantum-blockchain repository with D-Wave's  quantum computing system will
# require access to D-Wave’s LeapTM quantum cloud service and will be governed by the Leap Cloud
# Subscription Agreement available at:
# https://cloud.dwavesys.com/leap/legal/cloud_subscription_agreement/


import numpy as np

from src.protocols.proof_of_work_protocol import ProofOfWorkProtocol
from src.structures.block import Block
from src.structures.block_score_tree import BlockScoreTree


class Miner:
    """This class is intended to encapsulate all necessary functions for running a miner
    on the blockchain network."""

    def __init__(self, miner_id: str, pow_protocol: ProofOfWorkProtocol, genesis_block: Block):
        """Instantiates a new miner at the given hostname. The subdir is the
        directory to store the mempool, known nodes, and blockchain.

        Args:
            subdir (str): name of subdirectory with initialization files and where
            file outputs will be written.
        """

        self.id = miner_id
        self.blockchain = BlockScoreTree()
        self.add_block_to_chain(genesis_block, 1.0)
        self.pow = pow_protocol

        # Holds block that is currently being mined but not yet finalized or broadcast.
        self.mining_block = None
        self.mined_block = None
        self.mined_block_score = None

    def re_initialize_blockchain(self, node_list: list[dict]):
        """ Recreates the miner's blockchain from a dictionary of miner blockchain data. This is used
            when re-starting the demo when it has been paused. Persistent blockchain data will be saved
            in a list of dicts, where each dict contains a JSON-formatted block, plus several fields
            of metadata about that block, including the scores assigned to it be each miner. When
            a miner calls this function, it will look for a score keyed to its miner_id in the
            score list of each block in order (starting from the first block mined) and add that
            block to its chain with that score. This should reproduce an identical blockchain
            to the one the miner had before the simulation was paused.
            
            Args:
                node_list (list of dicts): A list of dicts containing JSON blocks and metadata.  
                    should be passed to each miner by simulation callback during restart.
                    
            Modifies:
                self.blockchain: should add nodes to the miner's blockchain to bring it up-to-date."""

        for block_entry in node_list:
            scores = block_entry["scores"]
            score = scores[self.id]
            block = Block.from_json(block_entry["block_json"])
            self.add_block_to_chain(block=block, block_score=score)

    def add_block_to_chain(self, block: Block, block_score: float = 0.0):
        """Adds a block to the block_score_tree object stored in self.blockchain. Updates
            blockchain beliefs based on the logic of the update_blockchain_beliefs function.

        Args:
            block (Block): a block
            block_score (int or float): score assigned to the block

        Modifies:
            self.blockchain: the miner's blockchain
        """

        self.blockchain.add_block(block.hash, block.previous_hash, block_score)

        # Only need to update on blocks that are good and not already in trunk
        if self.blockchain.score_predicate(block_score):
            self.update_blockchain_beliefs()

    def update_blockchain_beliefs(self):
        """Updates the blockchain tree so that the branch containing the highest scoring block is now the trunk.


        Modifies:
           self.blockchain.tree: the representation of the miner's chain structure"""

        if self.blockchain.trunk.tip.hash != self.blockchain.strongest_block_hash:
            best_branch = self.blockchain.hash_to_branch_lookup[
                self.blockchain.strongest_block_hash
            ]
            self.blockchain.promote_to_trunk(best_branch)

    def assemble_new_block(self, previous_block_hash: str | None = None) -> Block:
        """Assembles a new block

        Returns:
            new_block (Block): a new block that is assembled with a random nonce, but has not yet had its quantum hash
                or block hash set."""

        if previous_block_hash is None:
            previous_block_hash = self.blockchain.tip_hash

        nonce = np.random.randint(0, 2 ** 15)
        new_block = Block(miner_id=self.id, previous_block_hash=previous_block_hash, nonce=nonce)
        return new_block

    def attempt_mine(self, mining_block: Block | None = None) -> tuple[Block, float, str]:
        """Attempts to mine a new block, choosing the nonce at random, calculating the quantum hash
            and the block hash and validating against the PoW requirement.

        Returns:
            succeeded (bool): whether the mining succeeded or failed
            sample_time (float): the time in seconds spent performing the quantum experiment."""

        if mining_block is None:
            if self.mining_block is None:
                mining_block = self.assemble_new_block()
            else:
                mining_block = self.mining_block
                mining_block.nonce += 1

        new_block, block_score, solver = self.pow.mine_block(mining_block)
        new_block.lock()
        self.mined_block = new_block
        self.mined_block_score = block_score
        self.mining_block = None
        return new_block, block_score, solver

    def receive_block(self, new_block_str) -> tuple[float, str]:
        """Processes a new block that has been received as a JSON-formatted string, validates it
            and adds it to the miner's blockchain.

        Args:
            new_block_str (str): A new block, serialized into a JSON-formatted string.

        Returns:
            score: the score assigned to the block."""

        new_block = Block.from_json(new_block_str)
        score, solver = self.validate_block(new_block)
        self.add_block_to_chain(new_block, score)
        return score, solver

    def validate_block(self, block: Block) -> tuple[float, str]:
        """Validates the Block's compliance with the Proof of Work protocol. The Miner's
            ProofOfWork Object calls its own validate_block function to check the main block hash,
            the N_zeroes requirement, the Merkle root and the quantum hash, with the later
            assigning a float-values score rather than a strict pass or fail boolean flag. This
            final score is the only thing returned by this method (any other validation issue will
            raise an Exception).

        Args:
            block (Block): the Block object to be validated.

        returns:
            score (float): the Block's score, as determined from evaluating its quantum hash against the miner's
                scoring function. The current convention across all scoring functions is that positive score blocks
                are initially presumed valid (and added to the Miner's trunk if applicable) while zero or negative
                scores are presumed invalid and will create a secondary branch if their predecessor is in the trunk
                (or be added to an existing branch otherwise)."""

        valid, score, solver = self.pow.validate_block(block)

        if not valid:
            raise Exception(
                f"Block {block.hash} failed required protocol validation checks for miner {self.id}"
            )

        return score, solver

    def broadcast_mined_block(self) -> str:
        """Stores a copy of the Miner's most recently mined block in the Miner's own blockchain before serializing
            a mined block into a JSON-formatted string, which is returned.

        Returns:
            block_data (str): the mined block serialized as a JSON-formatted string"""

        if self.mined_block is None:
            raise Exception(f"Miner {self.id} attempted to broadcast with no block ready")

        if self.mined_block_score is None:
            raise Exception(
                f"Attempted to broadcast mined block with hash \
                            {self.mined_block.hash}, but it had not been scored."
            )
        else:
            self.add_block_to_chain(self.mined_block, self.mined_block_score)

        block_data = self.mined_block.to_json
        self.mined_block = None
        self.mined_block_score = None

        return block_data
