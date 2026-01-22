import random
import time

from src.agents.miner import Miner
from src.protocols.hash_calculator import HashSolver
from src.protocols.proof_of_work_protocol import ProofOfWorkProtocol
from src.structures.block import Block
from src.values import GENESIS_BLOCK_PREV_HASH, GENESIS_BLOCK_TIMESTAMP


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
        """Initializes a new TrialManager object. Requires a file with name matching
        the name stored in TRIAL_PARAMETERS_FILE (found in common.values) to be located
        in the same directory and properly formatted in order to initialize. Such a
        file should be created automatically by trials_main anytime it is run without
        being passed a directory argument. If restarting a trial in the same directory, this
        will simply initialized using the files already present.

        Instantiates:
            TrialMiners object: object which declares and initializes miners for the trial,
            often creating multiple files and subdirectories in the process

        """

        self.max_blocks = num_blocks
        num_miners = len(miner_names)

        self.solvers = solvers
        self.pow = ProofOfWorkProtocol(solvers, quantum_hash_length, n_zeroes, allowable_err)
        self.trial_init_time = time.time()
        genesis_block = Block(miner_id="genesis", previous_block_hash=GENESIS_BLOCK_PREV_HASH, timestamp=GENESIS_BLOCK_TIMESTAMP)
        genesis_block.set_quantum_hash()
        genesis_block.set_hash()
        genesis_block.lock()
        self.genesis_block = genesis_block
        self.initialize_miners(miner_names)

        self.max_mining_attempts = 1000000  # should definitely have some cutoff, but what's a good value depends a lot on use-case
        self.mining_miner = None
        self.block_broadcast = None
        self.round_order = []
        self.round_progress = 0
        self.blocks_mined = 0

    @property
    def num_miners(self):
        return len(self.miners)

    def initialize_miners(self, miner_names: list[str]):
        """Creates all the Miner objects necessary to run the trial, passing each one a reference to
        the subdirectory where its initial blockchain.txt file is stored, and having it run initialization
        for both the blockchain, its ProofOfWorkProtocol class and its logs..

        Args:
            num_owners: the number of miners to initialize

        Raises:
            Exception: if one of the necessary owner directories does not exist."""
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
        """Runs setup for a single round of mining. This includes creating a random transaction, 'broadcasting' it to all
        miners (who store it in their mempools), and randomly ordering the miners, the first of whom will mine this round
        and the rest of whom will validate.

        Modifies:
            self.round_order: sets the round order at random
            self.owners: one owner, selected at random, will create a Transaction (modifying their internal state in the process)
            self.miners: all Miners will receive the created transaction, storing it in their mempools.

        Returns:
            a string summary of the round order, to use as console output if desired."""

        self.block_broadcast = None
        self.round_progress = 0
        miner_order = [miner_id for miner_id in self.miners.keys()]
        random.shuffle(miner_order)
        self.round_order = miner_order
        return self.round_order

    def mining_step(self) -> tuple[str, float, str]:
        """Executes the mining step for the single round of the trial. Miner mines a single block (or times
        out after exceeding the maximum number of attempts) and stores it serialized form in self.block_broadcast.

        Args:
            miner_id: (str) The ID of the miner who is going to mine the block

        Modifies:
            self.block_broadcast: stores the newly-mined block here, serialized in JSON format

        """
        self.mining_miner_id = self.round_order[0]
        self.mining_miner = self.miners[self.mining_miner_id]
        mining_attempts = 0
        mine_success = False
        while mining_attempts <= self.max_mining_attempts and not mine_success:
            mining_attempts += 1
            mined_block, block_score, solver = self.mining_miner.attempt_mine()
            if block_score > 0:  #Deviates from paper methodology (for confidence-based scoring)
                self.block_broadcast = self.mining_miner.broadcast_mined_block()
                self.round_progress += 1
                self.blocks_mined += 1
                return self.mining_miner_id, block_score, solver

            # TODO figure out what to do if mining fails

        return "failed", -1.0, "none"

    def validation_step(self) -> tuple[str, float, str]:
        """Chooses the next miner in validation order to perform validation for the mined block.

        Args:
            validator_id (str): the ID of the miner who should validate during this step

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
        if self.round_progress == 0 or self.round_progress >= self.num_miners:  # TODO reconsider
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
            num_blocks (int): Defaults to None, which will simply cause the trial to run to completion. If an integer is passed that
            is less than the number of blocks currently remaining in the trial, TrialManager will run for that number of blocks and
            then pause. Passing exactly the number of blocks remaining is equivalent to the default behavior. Passing more than the
            remaining number will raise an Exception."""

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
        """Finds the block number of the last block that all miners have in their trunks: that is, the last
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
        largest_common_block_num = max(list(common_block_nums))  # TODO validity check
        return largest_common_block_num
