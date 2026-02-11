# Copyright 2024 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import random
import time

from src.agents.miner import Miner
from src.protocols.hash_calculator import HashSolver
from src.protocols.proof_of_work_protocol import ProofOfWorkProtocol
from src.structures.block import Block
from src.values import GENESIS_BLOCK_PREV_HASH, GENESIS_BLOCK_TIMESTAMP, MAX_MINING_ATTEMPTS, GENESIS_MINER_ID

def initialize_genesis_block(
    miner_id: str = GENESIS_MINER_ID, 
    previous_block_hash: str = GENESIS_BLOCK_PREV_HASH, 
    timestamp: float = GENESIS_BLOCK_TIMESTAMP,
):
    """ Initializes genesis block for the blockchain. In ordinary mining, these steps will
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
    the state of the trial as it progresses. The latest successful trial
    will be saved to a file location so that it can be recovered if there
    is a failure in subsequent trials.
    """

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Initialization                                               |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(
                self, num_blocks: int, 
                miner_names: list[str], 
                solvers: list[HashSolver], 
                quantum_hash_length: int, 
                n_zeroes: int, 
                allowable_err: int
                ):
        """ Initializes a new TrialManager object. Requires a file with name matching
            the name stored in TRIAL_PARAMETERS_FILE (found in common.values) to be located
            in the same directory and properly formatted in order to initialize. Such a
            file should be created automatically by trials_main anytime it is run without
            being passed a directory argument. If restarting a trial in the same directory, this
            will be initialized using the files already present.

            Instantiates:
                TrialMiners object: object which declares and initializes miners for the trial."""

        self.max_blocks = num_blocks
        self.solvers = solvers
        self.pow = ProofOfWorkProtocol(solvers, quantum_hash_length, n_zeroes, allowable_err)
        self.trial_init_time = time.time()
        self.genesis_block = initialize_genesis_block()
        self.initialize_miners(miner_names)
        self.max_mining_attempts = MAX_MINING_ATTEMPTS
        self.mining_miner = None
        self.block_broadcast = None
        self.round_order = []
        self.round_progress = 0
        self.blocks_mined = 0

    @property
    def num_miners(self):
        return len(self.miners)

    def initialize_miners(self, miner_names: list[str]):
        """ Creates all the Miner objects necessary to run the trial, passing each one an id, a 
            ProofOrWorkProtocol object (which should contain initialized solvers) and the 
            genesis block to form the basis for the new blockchain.

            Args:
                num_owners: the number of miners to initialize"""
        
        self.miners = {}

        for name in miner_names:
            next_miner = Miner(name, self.pow, self.genesis_block)
            self.miners.update({next_miner.id: next_miner})

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Mining Round Primary Steps                                    |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def reset_round(self):
        """ Runs setup for a single round of mining, currently limited to randomly setting the round order
            for mining and validation.

            Modifies:
                self.round_order: sets the round order at random. """

        self.block_broadcast = None
        self.round_progress = 0
        miner_order = [miner_id for miner_id in self.miners.keys()]
        random.shuffle(miner_order)
        self.round_order = miner_order

    def mining_step(self) -> tuple[str, float, str]:
        """ Executes the mining step for the single round of the trial. Miner mines a single block (or times
            out after exceeding the maximum number of attempts) and stores its serialized form in self.block_broadcast.

            Modifies:
                self.block_broadcast: stores the newly-mined block here, serialized in JSON format. """
        
        self.mining_miner_id = self.round_order[0]
        self.mining_miner = self.miners[self.mining_miner_id]

        for _ in range(self.max_mining_attempts):
            _, block_score, solver = self.mining_miner.attempt_mine()
            if block_score > 0:  # Deviates from paper methodology (for confidence-based scoring)
                self.block_broadcast = self.mining_miner.broadcast_mined_block()
                self.round_progress += 1
                self.blocks_mined += 1
                return self.mining_miner_id, block_score, solver

        raise Exception(f"TrialManager exceeded max mining attempts of {self.max_mining_attempts} without {self.mining_miner_id} finding mining a valid block.")

    def validation_step(self) -> tuple[str, float, str]:
        """ Chooses the next miner in validation order to perform validation for the mined block.

            Returns:
                validator_id (string): ID of the validating miner
                block_score (float): score that the validator assigned to the block
                solver (string): name of the solver used for validation """

        validator_id = self.round_order[self.round_progress]
        validator = self.miners[validator_id]
        block_score, solver = validator.receive_block(self.block_broadcast)
        self.round_progress += 1

        return validator_id, block_score, solver

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Other Round Tasks                                            |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def single_step(self) -> tuple[bool, str, float, str]:
        """ Executes a single, atomic step of the simulation algorithm, deciding based on the internal state
            of the TrialManager object which action needs to happen next.
            
            Returns:
                mined (bool): Indicates whether this step was a mining step
                miner_id (string): ID of the miner that mined or validated this round
                solver (string): name of the solver that was used for mining or validation this round"""
        
        if self.round_progress == 0 or self.round_progress >= self.num_miners:
            mined = True
            self.reset_round()
            miner_id, block_score, solver = self.mining_step()
        else:
            mined = False
            miner_id, block_score, solver = self.validation_step()
        return mined, miner_id, block_score, solver

    def run_trial(self, num_blocks: int = None):
        """Runs the trial through some number of complete block mining and validation events. By default it will run until the
            trial finishes, but this can be overridden by passing a smaller number as an argument.

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

    def get_active_block_hashes(self) -> list:
        """ Queries miners to get a list of the hashes of all blocks that are currently candidates for mining. 
            Each miner should have one block that they consider the strongest (may be the same for different
            miners), which they will mine on top of if they are selected for the next mining round. This 
            function collects a list of those block hashes and returns it (with duplicates removed).
            
            Returns:
                active_hash_list (list[str]). List of hashes of blocks that are candidates for mining."""
        
        active_hashes = [miner.blockchain.strongest_block_hash for miner in self.miners.values()]
        return list(set(active_hashes))

    def get_last_common_trunk_block(self) -> int:
        """ Finds the block number of the last block that all miners have in their trunks: that is, the last
            block that all miners consider to be a canonical part of the main chain. This is important in
            assessing the state of the blockchain, as once all miners agree on a block, it is effectively
            immutable, as every new block mined will include it as a predecessor.

            Returns:
                largest_common_block_num (int): the block number of the last block that all miners have
                    their trunk."""
        trunk_sets = [
            set([blk.block_number for blk in miner.blockchain.trunk])
            for miner in self.miners.values()
        ]
        common_block_nums = set.intersection(*trunk_sets)
        if len(common_block_nums) == 0:
            return 0

        largest_common_block_num = max(list(common_block_nums))
        return largest_common_block_num
