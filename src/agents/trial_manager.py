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
# The use of the quantum blockchain implementations below (including the Miner, Block, and Hash
# methods) with D-Wave's quantum computing system will require access to D-Wave’s LeapTM quantum
# cloud service and will be governed by the Leap Cloud Subscription Agreement available at:
# https://cloud.dwavesys.com/leap/legal/cloud_subscription_agreement/


import random

from src.agents.miner import Miner
from src.protocols.hash_calculator import HashSolver
from src.protocols.proof_of_work_protocol import ProofOfWorkProtocol
from src.structures.block import Block
from src.structures.block_score_tree import BlockScoreTree
from src.values import (
    GENESIS_BLOCK_PREV_HASH,
    GENESIS_BLOCK_TIMESTAMP,
    GENESIS_MINER_ID,
    MAX_MINING_ATTEMPTS,
)


def initialize_genesis_block(
    miner_id: str = GENESIS_MINER_ID,
    previous_block_hash: str = GENESIS_BLOCK_PREV_HASH,
    timestamp: float = GENESIS_BLOCK_TIMESTAMP,
) -> Block:
    """Initializes genesis block for the blockchain. In ordinary mining, these steps will
    need to be performed by the miners and interleaved with other operations. For the
    genesis block, we can just do them all at once based on constant values.

    Args:
        all args are dummy values that just need to be set to some constant. See documentation
            in src/structure/block.py for descriptions of Block class constructor args

    Returns:
        genesis_block (Block): If called with the default args, this Block will always have
            the same hash on every invocation, allowing for a consistent seed and starting
            point for different blockchain trials."""

    genesis_block = Block(miner_id, previous_block_hash, timestamp)
    genesis_block.set_quantum_hash()
    genesis_block.set_hash()
    genesis_block.lock()
    return genesis_block


class TrialManager:
    """This class manages a trial of blockchain mining. The purpose of this
    class is to be able to iterate through a series of blocks and maintain
    the state of the trial as it progresses."""

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Initialization                                               |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(
        self,
        num_blocks: int,
        miner_names: list[str],
        solvers: list[HashSolver],
        quantum_hash_length: int,
        n_zeroes: int,
        allowable_err: int,
    ):
        """Initializes a new TrialManager object.

        Args:
            num_blocks (int): the number of blocks the trial will run before it concludes
            miner_names (list[str]): a list of unique strings to use as names of miners in the
                trial. TrialManager will use all such names passed, thus the length of the list
                will determine the number of miners in the trial.
            solvers (list[HashSolver]): a list of HashSolver objects. One will be selected each
                time a miner attempts to mine or validate. To run a trial with a single solver,
                pass a list containing only that solver.
            quantum_hash_length (int): length in bits of the quantum hash. This partly determines
                the cross-validation difficulty for the trial.
            n_zeroes (int): the number of leading zeros a block hash must have to pass the PoW
                requirement. This determines how difficult mining is: each extra 0 will (on
                average) double the number of attempts required to mine successfully.
            allowable_err (int): how much error is allowed in cross validation. Increasing
                this will make cross-validation easier: see the 'scoring' function
                in the ProofOfWorkProtocol class for a full mathematical description.

        Instantiates:
            TrialMiners object: object which declares and initializes miners for the trial."""

        # Trial Parameters
        self.max_blocks = num_blocks  #
        self.solvers = solvers
        self.pow = ProofOfWorkProtocol(solvers, quantum_hash_length, n_zeroes, allowable_err)
        self.max_mining_attempts = MAX_MINING_ATTEMPTS

        # Data structures
        self.genesis_block = initialize_genesis_block()
        self.global_tree = BlockScoreTree()
        self.global_tree.add_block(self.genesis_block.hash, self.genesis_block.previous_hash, 1.0)
        self.chain_data = []
        self._initialize_miners(miner_names)

        # Attributes for tracking round status and progress
        self.mining_miner = None
        self.round_order = [miner_id for miner_id in self.miners.keys()]
        random.shuffle(self.round_order)
        self.round_progress = 0

    @property
    def num_miners(self):
        return len(self.miners)

    @property
    def blocks_mined(self):
        return len(self.chain_data)

    @property
    def mining_hashes(self) -> list[str]:
        hash_set = set([miner.mining_hash for miner in self.miners.values()])
        primary_hash = self.miners[self.round_order[0]].mining_hash
        hash_set.remove(primary_hash)
        return [primary_hash] + list(hash_set)

    def _initialize_miners(self, miner_names: list[str]):
        """Creates all the Miner objects necessary to run the trial, passing each one an id, a
        ProofOrWorkProtocol object (which should contain initialized solvers) and the genesis
        block to form the basis for the new blockchain.

        Args:
            num_miners: the number of miners to initialize"""

        self.miners = {}

        for name in miner_names:
            next_miner = Miner(name, self.pow, self.genesis_block)
            self.miners.update({next_miner.id: next_miner})

    def _reload_blockchain(self, blockchain_list: list[dict]):
        """Reloads the blockchain data from a list of dicts, each of which must contain a single
        JSON-formatted block. Each entry's block will also be added to the TrialManager's
        global blockchain representation. Should only be called by the restart_trial method.

        Args:
            blockchain_list (list[dict]): A list containing dicts of blockchain data, including
                JSON-formatted blocks. The list should also include scoring data for all
                the miners in the trial, but this won't be checked until reinitialize_miners
                is called (see that docstring for more info).

        Modifies:
            self.chain_data: Stores the passed list in the self.chain_data attribute; this
                will serve as the source for all the data needed to reload the blockchain
                by this and other functions.
            self.global_tree: Adds an entry to the global blockchain tree representation for
                each block in the passed list. Does not modify the structure beyond whatever
                structure is produced by adding all the blocks (but see _reinitialize_miners)"""

        self.chain_data = blockchain_list
        for data_dict in blockchain_list:
            block = Block.from_json(data_dict["block_json"])
            block_num = data_dict["block_number"]
            self.global_tree.add_block(block.hash, block.previous_hash, -1.0, block_num)

    def _reinitialize_miners(self):
        """Reinitializes all miners, reloading their blockchain data from the data stored in
        self.chain_data. This function will fail if self.chain_data does not include the
        correct block data and scoring data. In particular, every entry in self.chain_data
        must have a sub-dictionary named 'scores', whose keys match the miner names that the
        TrialManager object was instantiated with. The exception is the final block in
        self.chain_data, which can be missing some or all of the miner scores without causing
        an error. Should only be called by the restart_trial method, after _reload_blockchain
        has been called to populate the self.chain_data list with suitable data.

        Modifies:
            self.miners: All the miners stored in self.miners will have the internal states
                of their blockchains modified, bringing them up-to-date with the TrialManager's
                blockchain data.
            self.round_order: The round order will be set so that all the miners who have
                already validated the current block precede all the miners who have not.
                The latter group will be placed in a randomized order to finish validation."""

        short_blockchain = self.chain_data[:-1]
        last_block = self.chain_data[-1]
        finished_miners = [miner_id for miner_id in last_block["scores"].keys()]
        unfinished_miners = []

        for miner_id, miner in self.miners.items():
            if miner_id in last_block["scores"]:
                miner.re_initialize_blockchain(self.chain_data)
            else:
                miner.re_initialize_blockchain(short_blockchain)
                unfinished_miners.append(miner_id)

        self.round_progress = len(finished_miners)
        if self.round_progress == self.num_miners:
            self._reset_round()
        else:
            random.shuffle(unfinished_miners)
            self.round_order = finished_miners + unfinished_miners

        current_block = Block.from_json(self.chain_data[-1]["block_json"])
        for miner_id, miner in self.miners.items():
            if current_block.previous_hash not in miner.blockchain.hash_to_branch_lookup:
                raise Exception(
                    f"{miner_id} failed to have latest \
                                block {current_block.hash} with tree structure {miner.blockchain}"
                )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Mining Round Primary Steps                                    |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _reset_round(self):
        """Resets the self.round_progress counter to 0 and rerandomizes the mining and validation
            order for the next round.

        Modifies:
            self.round_order: sets the round order at random."""

        self.round_progress = 0
        random.shuffle(self.round_order)

    def _mining_step(self):
        """Executes the mining step for the single round of the trial. Miner mines a single block
        (or times out after exceeding the maximum number of attempts) and stores its
        serialized form in self.block_broadcast.

        Modifies:
            self.chain_data: Adds a new block entry to the chain_data list, containing a
                JSON-formatted copy of the block as well as the miner's score and solver data
            self.global_tree: adds the new block to the global blockchain representation
                maintained by the TrialManager.

        Returns:
            self.mining_miner_id: the id of the miner that mined this round."""

        self.mining_miner_id = self.round_order[0]
        self.mining_miner = self.miners[self.mining_miner_id]

        for _ in range(self.max_mining_attempts):
            mine_success, block_data_dict, blocknode = self.mining_miner.attempt_mine()
            if mine_success:
                self.chain_data.append(block_data_dict)
                self.global_tree.add_block(blocknode.hash, blocknode.prev_hash, -1.0)
                self.round_progress += 1
                return

        raise Exception(
            f"TrialManager exceeded max mining attempts of {self.max_mining_attempts}\
                         without {self.mining_miner_id} finding mining a valid block."
        )

    def _validation_step(self):
        """Chooses the next miner in validation order to perform validation for the mined block.

        Returns:
            validator_id (string): ID of the validating miner

        Modifies:
            self.chain_data: stores the validators score and solver info to the entry for the
                current block."""

        validator_id = self.round_order[self.round_progress]
        validator = self.miners[validator_id]
        current_block_dict = self.chain_data[-1]
        block_score, solver = validator.receive_block(current_block_dict["block_json"])
        self.round_progress += 1
        current_block_dict["scores"].update({validator_id: block_score})
        current_block_dict["solvers"].update({validator_id: solver})

    def _update_global_tree_structure(self):
        """Updates the structure of the global tree by finding the hash of the most recent block
        that every miner has in their trunk, and restructuring the global tree so that the
        trunk ends at that block (i.e. it consists of that block and all its predecessors).

        Modifies:
            self.global_tree: Rearranges the branch structure of the global tree, but does
                not add, remove or change the values of any of its blocks."""

        trunk_sets = [
            set([(block.hash, block.block_number) for block in miner.blockchain.trunk])
            for miner in self.miners.values()
        ]
        common_hash_tuples = set.intersection(*trunk_sets)  # Tuple of (hash, block_number)
        if len(common_hash_tuples) > 0:
            last_common_hash_tuple = max(common_hash_tuples, key=lambda x: x[1])
            if last_common_hash_tuple[0] not in self.global_tree.trunk:
                next_trunk = self.global_tree.hash_to_branch_lookup[last_common_hash_tuple[0]]
                self.global_tree.promote_to_trunk(next_trunk, last_common_hash_tuple[0])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Public Access Functions                                        |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def single_step(self) -> str:
        """Executes a single mining or validation step of the algorithm, including any internal
            state updates appropriate for that step. Which sort of step to execute and whether
            to finish and reset the round afterwards is determined by the self.round_progress
            attribute, which is incremented by one on each step executed.

        Returns:
            miner_id (string): ID of the miner that mined or validated this round"""

        miner_id = self.round_order[self.round_progress]
        if self.round_progress == 0:
            self._mining_step()
        else:
            self._validation_step()

        if self.round_progress >= self.num_miners:
            self._update_global_tree_structure()
            self._reset_round()

        return miner_id

    def run_trial(self, num_blocks: int | None = None):
        """Runs the trial through some number of complete block mining and validation events. By
            default it will run until the trial finishes, but this can be overridden by passing a
            smaller number as an argument.

        Args:
            num_blocks (int): Defaults to None, which will simply cause the trial to run to completion. If an integer
                less than or equal to the number of blocks remaining in the trial is passed, TrialManager will run for
                only that number of blocks, allowing the trial to be broken up into stages if desired. Passing more than
                the remaining number will raise an Exception."""

        if num_blocks is None:
            stopping_block = self.max_blocks
        elif num_blocks > self.max_blocks - self.blocks_mined:
            raise Exception(
                f"Attempted to run trial for {num_blocks} rounds, with only {self.max_blocks - self.blocks_mined} blocks remaining."
            )
        else:
            stopping_block = self.blocks_mined + num_blocks

        while self.blocks_mined < stopping_block:
            self.single_step()

    def restart_trial(self, blockchain_list: list[dict]):
        """Restarts and interrupted trial, reloading all necessary blockchain and miner data from
        the list passed as an argument.

        Args:
            blockchain_list (list[dict]): A list containing data for the interrupted trial.
                For this function to complete successfully, the list must include a dict for
                each block in the chain, with a JSON-formatted copy of that block as well
                as a dict of scores that the miners assigned to that block (keyed by miner id).
                For more info on each of these requirements, see _reload_blockchain and
                _reinitialize_miners respectively.

        Modifies:
            self.chain_data: see individual sub-functions for details
            self.global_tree"""

        self._reload_blockchain(blockchain_list)
        self._reinitialize_miners()
        self._update_global_tree_structure()
