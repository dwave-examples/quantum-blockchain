# Copyright 2026 D-Wave
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

import os

import pytest

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

from src.agents.trial_manager import TrialManager
from src.protocols.hash_calculator import SolverName, initialize_solver

simulated_solvers = [initialize_solver(s.value) for s in SolverName if "simulated" in s.value]

miner_nums = [7, 4, 189, 27]
block_nums = [20, 531, 7, 2917]  # Irrelevant to the test, but must be set to some value
solver_lists = [
    simulated_solvers,
    simulated_solvers[:2],
    [simulated_solvers[-2]],
    [simulated_solvers[0], simulated_solvers[1], simulated_solvers[-1]],
]

# Using too high a value for num_zeros, or too high a ratio of quantum_hash_length to
# allowable_err will cause the test to fail because miners will be unable to mine valid
# blocks in a reasonable number of attempts. Use caution when altering these.
zero_nums = [0, 1, 0, 2]
quantum_hash_lens = [64, 7201, 88, 12]
allowable_errs = [1, 150, 19, 83]
prng_seeds = [42, 793917, 118, 2113145]

parameter_sets = [
    [
        block_nums[i],
        miner_nums[i],
        solver_lists[i],
        quantum_hash_lens[i],
        zero_nums[i],
        allowable_errs[i],
        prng_seeds[i],
    ]
    for i in range(len(miner_nums))
]

num_blocks = 5


def test_prng_randomization():
    """Tests the repeatability of the random elements in the trial by initializing two
    TrialManager objects with identical parameters and in particular identical PRNG seeds. If
    everything is working correctly, these managers should get completely identical results when
    mining with any combination of simulated solvers. If an update causes this test to start
    failing, the most likely cause is that some randomization function was used that didn't
    use TrialManager's prng_seed value as its original source of entropy."""

    for parameter_set in parameter_sets:
        manager1 = TrialManager(*parameter_set)
        manager2 = TrialManager(*parameter_set)

        assert (
            manager1.prng_seed == manager2.prng_seed
        ), f"Managers have different prng seeds of {manager1.prng_seed} \
            and {manager2.prng_seed} respectively"

        assert (
            manager1.pow.prng_seed == manager2.pow.prng_seed
        ), f"PoWs have differing prng seeds of {manager1.pow.prng_seed} \
            and {manager2.pow.prng_seed} respectively"

        for _ in range(num_blocks):
            assert manager1.round_order == manager2.round_order, f"Managers had differing round \
                        orders of {manager1.round_order} and {manager2.round_order} respectively"
            for __ in range(parameter_set[1]):  # Second param is num_miners. Controls how many
                manager1.single_step()  # steps are in a given round
                manager2.single_step()
                active_miner1 = manager1.miners[manager1.round_order[manager1.round_progress]]
                active_miner2 = manager2.miners[manager2.round_order[manager2.round_progress]]
                assert (
                    active_miner1.mining_hash == active_miner2.mining_hash
                ), f"Active miners had different mining hashes of \
                    {active_miner1.mining_hash} and {active_miner2.mining_hash} respectively"
                latest_block1 = active_miner1.blockchain.most_recent_block
                latest_block2 = active_miner1.blockchain.most_recent_block
                assert (
                    latest_block1 == latest_block2
                ), f"Active miners differed in latest blocks: {latest_block1} vs {latest_block2}."
