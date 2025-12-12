import os
import random
import time

from src.agents.miner import Miner
from src.agents.trial_params import GlobalTrialParams, PowProtocolParams
from src.values import MINER_NAMES
from src.protocols.hash_calculator import (
    BootstrappingHashSolver,
    QuantumHashSolver,
    SolverParams,
    initialize_solver,
)

from dwave.system import DWaveSampler
from dwave.cloud import Client


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

    def __init__(self, trial_params: GlobalTrialParams, pow_params: PowProtocolParams):
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

        self.global_params = trial_params
        self.max_blocks = self.global_params.num_blocks
        num_miners = self.global_params.num_miners
        self.trial_id = self.global_params.trial_id  # In general, should match directory name

        self.solver_params = self.global_params.solver_params
        self.solver_randomization = self.global_params.solver_randomization
        self.solver_list = None
        self.miner_solvers = None
        self.initialize_solvers()

        self.pow_protocol = pow_params
        self.trial_init_time = time.time()
        self.global_params.start_time = self.trial_init_time


        self.initialize_miners(num_miners)


        self.max_mining_attempts = 1000000  # should definitely have some cutoff, but what's a good value depends a lot on use-case
        self.mining_miner = None
        self.block_broadcast = None
        self.block_broadcast_solver = None
        self.sender = None
        self.sent_time = None
        self.validation_successes = 0
        self.total_validation_successes = 0
        self.round_start_time = 0
        self.round_end_time = 0
        self.round_order = None


    @property
    def num_miners(self):
        return len(self.miners)

    @property
    def blocks_mined(self):
        return self.global_params.trial_progress

    def initialize_solvers(self, individual_solvers: bool = False):
        """Initializes the set of solver objects required by the simulation settings. This will be a single solver
        if 'solver_randomization' is set to 'none,' or a set of either QPU solvers or Bootstrapping solvers if
        given any other setting. TrialManager will share this list of solvers with every miner, allowing the
        same pool of solvers to be re-used without constantly creating and breaking connections.

        Args:
            individual_solvers (bool): Defaults to False. Determines whether each miner is allocated their own solvers,
                or whether all miners share the same pool of solvers."""

        if self.solver_randomization == "none":
            self.solver_list = [initialize_solver(self.solver_params)]
            solver_param_list = [self.solver_params]

        else:
            if (
                "simulated" in self.solver_params.solver_name
            ):  # Bootstrapping solvers don't care about any parameter except solver name
                solver_param_list = [
                    SolverParams(solver_name=name)
                    for name in BootstrappingHashSolver.allowed_solvers()
                ]
            else:
                allowed_solvers = set(QuantumHashSolver.allowed_solvers())
                self.client = Client.from_config(profile=self.solver_params.profile)
                available_solvers = set([solver.name for solver in self.client.get_solvers()])
                if "strict" in self.global_params.solver_randomization:
                    num_retries = 8
                    while num_retries > 0:
                        if allowed_solvers.issubset(available_solvers):
                            break
                        else:
                            time.sleep(2 ** (8 - num_retries) + random.randint(1, 1000) / 1000)
                            self.client = Client.from_config(profile=self.solver_params.profile)
                            available_solvers = set(
                                [solver.name for solver in self.client.get_solvers()]
                            )
                            num_retries -= 1

                    if not allowed_solvers.issubset(available_solvers):
                        raise Exception(
                            f"Strict randomization requires all solvers from list {allowed_solvers} to be available. List of available solvers {available_solvers} was inadequate."
                        )
                name_list = list(allowed_solvers & available_solvers)

                solver_param_list = [
                    SolverParams(
                        name,
                        self.solver_params.randomize_embedding,
                        self.solver_params.annealing_time,
                        self.solver_params.profile,
                    )
                    for name in name_list
                ]

            self.solver_list = [initialize_solver(params) for params in solver_param_list]

        if individual_solvers:
            num_solver_lists = self.global_params.num_miners
            self.miner_solvers = []
            for i in range(num_solver_lists):
                next_list = [initialize_solver(params) for params in solver_param_list]
                self.miner_solvers.append(next_list)

        assert (
            len(self.solver_list) > 0
        ), "No solvers found. At least one solver must be available for algorithm to run."



    def initialize_miners(self, num_miners: int):
        """Creates all the Miner objects necessary to run the trial, passing each one a reference to
        the subdirectory where its initial blockchain.txt file is stored, and having it run initialization
        for both the blockchain, its ProofOfWorkProtocol class and its logs..

        Args:
            num_owners: the number of miners to initialize

        Raises:
            Exception: if one of the necessary owner directories does not exist."""
        self.miners = {}

        for i in range(num_miners):

                next_miner = Miner(miner_dir, init_time=self.trial_init_time)
                if self.miner_solvers is not None:
                    miner_solver_list = self.miner_solvers.pop(0)
                else:
                    miner_solver_list = self.solver_list
                next_miner.initialize_pow(
                    self.pow_protocol, miner_solver_list, self.solver_randomization
                )
                self.miners.update({next_miner.id: next_miner})



    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Mining Round Primary Steps                                    |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def setup_step(self):
        """Runs setup for a single round of mining. This includes creating a random transaction, 'broadcasting' it to all
        miners (who store it in their mempools), and randomly ordering the miners, the first of whom will mine this round
        and the rest of whom will validate.

        Modifies:
            self.round_order: sets the round order at random
            self.owners: one owner, selected at random, will create a Transaction (modifying their internal state in the process)
            self.miners: all Miners will receive the created transaction, storing it in their mempools.

        Returns:
            a string summary of the round order, to use as console output if desired."""
        self.round_start_time = time.time()
        miner_order = [miner_id for miner_id in self.miners.keys()]
        random.shuffle(miner_order)
        self.round_order = miner_order

        return f"{miner_order[0]} selected as active miner."

    def mining_step(self, miner_id: str):
        """Executes the mining step for the single round of the trial. Miner mines a single block (or times
        out after exceeding the maximum number of attempts) and stores it serialized form in self.block_broadcast.

        Args:
            miner_id: (str) The ID of the miner who is going to mine the block

        Modifies:
            self.block_broadcast: stores the newly-mined block here, serialized in JSON format

        Returns:
            Mining Description: string including the miner_id and number of attempts for the mined block.
        """
        if miner_id in self.miners:
            self.mining_miner = self.miners[miner_id]
        else:
            raise Exception(
                f"Attempted to mine with invalid id {miner_id}. Valid ids are {self.miners.keys()}"
            )
        mining_attempts = 0
        mine_success = False
        self.mining_miner.pow.hashing_times = []
        mining_times = []
        while mining_attempts <= self.max_mining_attempts and not mine_success:
            start_time = time.time()
            mining_attempts += 1
            mine_success, sample_time = self.mining_miner.attempt_mine()
            self.mining_miner.qpu_sample_time_total += sample_time
            if mine_success:

                self.block_broadcast, self.sender, self.block_broadcast_solver, self.sent_time = (
                    self.mining_miner.broadcast_mined_block()
                )

                end_time = time.time()
                
            else:
                end_time = time.time()

            total_time = end_time - start_time
            mining_times.append(total_time)

        return f"{self.mining_miner.id} mined a block in {mining_attempts} attempts"

    def validation_step(self, validator_id: str):
        """Chooses the next miner in validation order to perform validation for the mined block.

        Args:
            validator_id (str): the ID of the miner who should validate during this step

        Returns:
            string containing the score the Miner assigned to the block and whether it passed or failed, formatted
                to be printed to the console."""

        if validator_id in self.miners:
            self.validating_miner = self.miners[validator_id]
        else:
            raise Exception(
                f"Attempted to validate with invalid id {validator_id}. Valid ids are {self.miners.keys()}"
            )

        print(validator_id, end=":", flush=True)

        score = self.validating_miner.receive_block(
            self.block_broadcast, self.sender, self.sent_time, self.block_broadcast_solver
        )


        if score > 0:
            result = f"{round(score,2)} (pass)"
            self.validation_successes += 1
        else:
            result = f"{round(score,2)} (fail)"

        return f" {result} |"

    def cleanup_step(self):
        """Resets all the necessary internal attributes to prepare for starting the next round. Updates progress
            validation stat trackers.

        Returns:
            String containing a round summary, formatted to be printed to the console."""
        self.round_end_time = time.time()
        self.block_broadcast = None
        self.block_broadcast_solver = None
        self.round_order = None
        successful_validators = self.validation_successes
        failed_validators = self.num_miners - successful_validators - 1
        self.total_validation_successes += self.validation_successes
        self.validation_successes = 0
        for miner in self.miners.values():
            assert (
                miner.chain_size == self.blocks_mined + 1
            ), f"{miner.id} has chain size {miner.chain_size}. Expected {self.blocks_mined + 1}"

        return f"Round {self.blocks_mined} complete in {round(self.round_end_time - self.round_start_time,4)} seconds. Block accepted by {successful_validators} and rejected by {failed_validators}"

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Other Round Tasks                                            |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



    def single_step(self, print_result=True):
        """Executes a single, atomic step of the simulation algorithm. Logging and recovery can capture"""
        if self.round_order is None:
            self.setup_step()
        elif len(self.round_order) == self.num_miners:
            mining_miner_id = self.round_order.pop(0)
            self.mining_step(mining_miner_id)
        elif len(self.round_order) > 0:
            validating_miner_id = self.round_order.pop(0)
            self.validation_step(validating_miner_id)
        else:
            self.cleanup_step()


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


     