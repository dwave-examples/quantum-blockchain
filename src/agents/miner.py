import os
import time

import numpy as np

from src.protocols.scoring import Scoring
from src.structures.transaction import Transaction, TransactionOutput
from src.structures.score_tree_branch import BlockNode
from src.structures.block_score_tree import BlockScoreTree
from src.agents.owner import BroadcastType, BroadcastLogEntry

from src.protocols.proof_of_work_protocol import ProofOfWorkProtocol
from src.structures.block import Block
from src.values import BLOCK_REWARD, MAX_BLOCK_SIZE, CSV_LOG_SEP_CHAR, TRANSACTION_MAX_PRECISION
from src.agents.owner import Owner
from src.agents.agent_params import MinerParams
from src.agents.trial_params import PowProtocolParams
from src.utilities.crypto_utils import get_key_set


class Miner():
    """Intended Usage: this class is intended to encapsulate all necessary functions for running a miner
        on the blockchain network. Current ownership status is a bit of a mess, should consolidate some other
        classes and give more of their functions to this class.

    Ownership:
        self.blockchain: a BlockchainMemory object holding/tracking the state of the miner's blockchain.
        self.mempool: a MemPool object holding exclusive copies of proposed transactions for the miner to use
            to build blocks. Miner maintains it to ensure no transaction duplication.
        self.pow: a ProofOfWorkProtocol object. This object stores all the necessary properties to implement
            the agreed-on Proof of Work Protocol for the miner's blockchain, and encapsulates the
            functions that depend on those properties such as mining and validation. To assist with
            this it also holds some miner-specific parameters such as solver details and scoring function.

    Output:
       The following files will be created in the"""

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Initialization and Special Methods                            |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(self, miner_id: str, genesis_block: Block):
        """Instantiates a new miner at the given hostname. The subdir is the
        directory to store the mempool, known nodes, and blockchain.

        Currently set up to initialize entirely from files: as such, the only
        argument this function takes is the name of the subdirectory in which
        the files should be found (and where new output will be written)
        If any of the necessary files aren't present or are incorrectly formatted,
        initialization will fail. The file names are locked to defaults found in
        common.values

        Args:
            subdir (str): name of subdirectory with initialization files and where
            file outputs will be written.

        Input Files:
            MinerParams file: Expects 'miner_params.json' as file name. Stores static
            parameters, which are currently id, allowable_err and scoring_function.

            Blockchain text file: Expects 'blockchain.txt' as file name. stores the
            blocks in the miner's blockchain, along with their scores. At initialization,
            this should be storing at minimum one Block object, formatted as a json dict.

            Mempool text file (optional): Expects 'mempool.txt' as file name. Stores the
            miner's mempool. This should start empty for a freshly-created miner, so it's
            not required to exist. If a file does exist, the miner will read the contents
            into its self.mempool object. Being able to recover the mempool contents from
            file is important when restarting an interrupted trial.

        """

        self.id = miner_id

        genesis_block_node = BlockNode(
                hash=genesis_block.hash, 
                prev_hash=genesis_block.previous_hash, 
                block_score=1.0, 
                total_score=1.0, 
                block_height=0, 
                block_number=0)

        self.blockchain = BlockScoreTree(genesis_block=genesis_block_node)

        self.mining_block = (
            None  # Holds block that is currently being mined but not yet finalized or broadcast.
        )
        self.mined_block = None
        self.mined_block_score = None

    def initialize_pow(self, pow_params: PowProtocolParams, solver_list, solver_randomization):
        self.pow = ProofOfWorkProtocol(
            protocol_params=pow_params,
            hash_solvers=solver_list,
            solver_randomization=solver_randomization,
        )


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Blockchain Management                                         |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_block_to_chain(self, block: Block, block_score=0):
        """Adds a block to the blockchain memory stored in self.blockchain, which also
        adds its info to the score tree. Updates blockchain beliefs based on the logic of
        the update_blockchain_beliefs function. Writes the block data and its score to file.

        Args:
            block (Block): a block
            block_score (int or float): score assigned to the block


        Modifies:
            self.blockchain: the miner's blockchain
            self.mempool: the miners mempool
        """

        self.blockchain.add_block(block_hash=block.hash, 
                                  prev_block_hash=block.previous_hash,
                                  block_score=block_score)


        if self.blockchain.score_predicate(
            block_score
        ):  # Only need to update on blocks that are good and not already in trunk
            self.update_blockchain_beliefs()

    def update_blockchain_beliefs(self):
        """Updates the blockchain tree so that the branch containing the highest scoring block is now the trunk.
            Updates the mempool to reflect the change: transactions from blocks that are being moved off the trunk
            are returned to the mempool, transactions from blocks being moved onto the trunk are removed (often this will
            likely add and then remove many of the same transactions, which is fine). When with function is called and
            how it should work may need to change when miner behavior is allowed to be more flexible (i.e. different
            scoring functions or chain management policies).

        Modifies:
           self.blockchain.tree: the representation of the miner's chain structure
           self.mempool: the miner's mempool


        """

        if self.blockchain.trunk.tip.hash != self.blockchain.strongest_block_hash:
            best_branch = self.blockchain.hash_to_branch_lookup[
                self.blockchain.strongest_block_hash
            ]
            self.blockchain.promote_to_trunk(best_branch)


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Mining and Validation                                         |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def assemble_new_block(self, base_block: Block = None) -> Block:
        """Assembles a new block from the Transactions in the Miner's mempool, adding a coinbase transaction in
            amount determined by the block reward plus transaction fees. This function will typically only be called
            once in a single round of mining, even if the Miner makes multiple mining attempts, as the Transactions
            stored in the Block will not change and only the nonce must be altered.

        Args:
            base_block (Block, optional): Defaults to None. Passing a Block in this argument allows the Miner to mine
                on top of a Block other than the tip of their trunk. If left at default, the Miner will mine on
                top of the block at the tip of their trunk, which is the normal and expected usage.

        Returns:
            new_block (Block): a new block that is assembled with a random nonce, but has not yet had its quantum hash
                or block hash set."""

        if base_block is None:
            base_block = self.chain_tip_block

        coinbase_input = TransactionOutput(
            receiver_address=self.address, amount=BLOCK_REWARD
        )
        coinbase_transaction = Transaction(inputs=[], outputs=[coinbase_input])
        transactions = [coinbase_transaction]
        nonce = np.random.randint(0, 2**32)  # TODO check how to make non-arcitechture specific
        new_block = Block(
                transactions=transactions, previous_block_hash=base_block.hash, nonce=nonce
            )
        return new_block

    def attempt_mine(self) -> tuple[bool, float]:
        """Attempts to mine a new block, choosing the nonce at random, calculating the quantum hash
            and the block hash and validating against the PoW requirement. Miners will score their
            own blocks and only broadcast blocks that have passing scores (which is currently
            guaranteed in all systems other than confidence-based scoring).

        Returns:
            succeeded (bool): whether the mining succeeded or failed
            sample_time (float): the time spent performing the quantum experiment. Currently unused, but
                something we will likely wish to track eventually.
        """
        if self.mining_block is None:
            self.mining_block = self.assemble_new_block()
        else:
            self.mining_block.nonce += 1  # Unlikely to matter, but incrementing nonce is more efficient than new random choice each time

        new_block, block_score, sample_time = self.pow.mine_block(self.mining_block)

        succeeded = bool(block_score > 0)

        if succeeded:
            new_block.set_hash()
            new_block.lock()
            self.mined_block = new_block
            self.mined_block_score = block_score
            self.mining_block = None

        return succeeded, sample_time

   

    def validate_block(self, block: Block) -> float:
        """Validates the transactions and proof of work compliance for a single block by calling the appropriate
            methods. Transactions are validated and the fees calculated by calling Miner's validation_transaction()
            method separately on each transaction on the block. The total fees are compared to the block reward,
            after being very slightly rounded to ensure that a rounding error in the trailing decimals doesn't
            cause a validation failure. After transactions are validated, the Miner's ProofOfWork Object
            calls its own validate_block function to check the main block hash, the N_zeroes requirement,
            the Merkle root and the quantum hash, with the later assigning a float-values score rather
            than a strict pass or fail boolean flag. This final score is the only thing returned
            by this method (any other validation issue will raise an Exception).

        Args:
            block (Block): the Block object to be validated.

        returns:
            score (float): the Block's score, as determined from evaluating its quantum hash against the miner's
                scoring function. The current convention across all scoring functions is that positive score blocks
                are initially presumed valid (and added to the Miner's trunk if applicable) while zero or negative
                scores are presumed invalid and will create a secondary branch if their predecessor is in the trunk.
                (Or be added to an existing branch otherwise)."""

        pred_hash = block.previous_hash

        passes, score, validation_bits, sample_time = self.pow.validate_block(block)

        if not passes:
            self.blockchain.add_block(block_hash=block.hash, 
                                      prev_block_hash=block.previous_hash, 
                                      block_score=score) 
            raise Exception(
                f"Block {block.hash} failed required protocol validation checks for miner {self.id}"
            )
        else:
            return score

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Network Communication and Logging                             |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def broadcast_mined_block(self) -> tuple[str, str, str, float]:
        """Stores a copy of the Miner's most recently mined block in the Miner's own blockchain before serializing
            a mined block into a JSON-formatted string, which is passed along with the miner's ID and some
            miscellaneous data

        Returns:
            block_data (str): the mined block serialized as a JSON-formatted string
            Miner ID (str): the miner's ID
            current_solver_name (str): the name of the solver used to mine the block
            sent_time (float): the current time in seconds when the block is sent. Computed
                relative to the start time of the trial."""
        if self.mined_block is None:
            raise Exception(f"Miner {self.id} attempted to broadcast with no block ready")

        if self.mined_block_score is not None:
            self.add_block_to_chain(self.mined_block, self.mined_block_score)
        else:
            raise Exception(
                f"Attempted to broadcast mined block with hash {self.mined_block.hash}, but it had not been scored."
            )
        sent_time = time.time() - self.init_time
        broadcast_data = BroadcastLogEntry(
            Broadcast_Type=str(BroadcastType.BLOCK.value),
            Time_Sent=str(sent_time),
            Time_Received=str(sent_time),
            Sender_ID=self.id,
            Object_Hash=self.mined_block.hash,
            Previous_Hash=self.mined_block.previous_hash,
            Solver=self.pow.current_solver.solver_name,
        )
        self.log_broadcast(broadcast_data)
        block_data = self.mined_block.to_json
        self.mined_block = None
        self.mined_block_score = None

        return block_data, self.id, self.pow.current_solver.solver_name, sent_time

