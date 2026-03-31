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

from src.agents.trial_manager import TrialManager
from src.protocols.simulation_identification import (
    generate_simulation_id,
    get_simulation_params_from_id,
)
from src.utilities.get_solvers import get_all_solvers

miner_nums = [7, 4, 189, 27]
block_nums = [20, 531, 3, 2917]
solver_dict = get_all_solvers()
solver_list = [solver for solver in solver_dict.values()]
solver_lists = [  # Test shouldn't fail because a specific solver is unavailable, lists are built
    [solver_list[0], solver_list[1], solver_list[2]],  # from only available solvers
    [solver_list[-1], solver_list[-2], solver_list[-3], solver_list[-4]],
    [solver_list[2], solver_list[4], solver_list[-1]],
    [solver_list[3]],
]

zero_nums = [0, 77, 6, 155]
quantum_hash_lens = [64, 9800, 88, 12]
allowable_errs = [1, 133, 19, 83]
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


def test_manager_state_recovery():
    """This test checks that a TrialManager object's initialization state is being faithfully
    captured by the generate_simulation_id function and successfully reconstructed by the
    get_simulation_params_from_id function. It compares the parameters of the original TrialManager
    object to those of a new TrialManager object whose initialization parameters are recovered
    from the Simulation ID, and fails if any of those parameters differ."""

    for param_set in parameter_sets:
        orig_manager = TrialManager(*param_set)
        manager_id = generate_simulation_id(orig_manager)
        recovered_manager = TrialManager(**get_simulation_params_from_id(manager_id))
        assert (
            orig_manager.num_miners == recovered_manager.num_miners
        ), f"Original manager and recovered manager had different num_miners, \
            {orig_manager.num_miners} and {recovered_manager.num_miners} respectively."
        assert (
            orig_manager.max_blocks == recovered_manager.max_blocks
        ), f"Original manager and recovered manager had different max_blocks, \
            {orig_manager.max_blocks} and {recovered_manager.max_blocks} respectively."
        assert (
            orig_manager.n_zeroes == recovered_manager.n_zeroes
        ), f"Original manager and recovered manager had different n_zeroes, \
            {orig_manager.n_zeroes} and {recovered_manager.n_zeroes} respectively."
        assert (
            orig_manager.quantum_hash_length == recovered_manager.quantum_hash_length
        ), f"Original manager had recovered manager had different quantum hash lengths,\
            {orig_manager.quantum_hash_length} and {recovered_manager.quantum_hash_length} \
            respectively."
        assert (
            orig_manager.allowable_err == recovered_manager.allowable_err
        ), f"Original manager and recovered manager had different values for allowable_err, \
                {orig_manager.allowable_err} and {recovered_manager.allowable_err} respectively."

        assert (
            orig_manager.prng_seed == recovered_manager.prng_seed
        ), f"Original manager and recovered manager had different prng seeds, \
            {orig_manager.prng_seed} and {recovered_manager.prng_seed} respectively."

        orig_solver_set = {solver.solver_name for solver in orig_manager.solvers}
        recovered_solver_set = {solver.solver_name for solver in recovered_manager.solvers}
        assert (
            orig_solver_set == recovered_solver_set
        ), f"Original manager and recovered manager had different solver lists {orig_solver_set} \
            and {recovered_solver_set} respectively. \n Params {param_set}, ID {manager_id}"


# In most positions, and valid hex digit (0-9 and a-f) will yield a usable ID. However, the 7th
# and 8th place represent the solver configuration, and with the current 7 solvers,  can't tolerate
# hex value of 80 (equivalent to 128 is decimal notation) or greater, as they encode solver
# configurations that don't exist.
test_ids = [
    "001409700000400100002a",  # All QPU solvers (hex: 70, binary: 01110000)
    "0b050c0f0302b002c151d6",  # All simulated solvers (hex: 0f, binary: 00001111)
    "2f015ac80034032111f1c4",  # Invalid solver configuration (hex: c8, binary: 11001000)
    "c1c31c042f05043a4a33d9",
]  # Single simulated solver (hex: 04, binary: 00000100)


def test_id_recovery():
    """This test checks to ensure that a TrialManager instantiated from a Simulation ID via
    get_simulation_params_from_id will yield back an identical Simulation ID when passed into
    get_simulation_params_from_id. It also checks that an invalid solver configuration properly
    causes get_simulation_params_from_id to raise an Exception."""

    for orig_id in test_ids:
        if (
            int(orig_id[6:8], 16) >= 128
        ):  # Validation checks in get_simulation_params_from_id should
            error_params = ""  # Catch IDs above 127 (hex values over 7f), raising an Exception.
            try:
                error_params = get_simulation_params_from_id(orig_id)
                raised_exception = False
            except:
                raised_exception = True

            assert (
                raised_exception
            ), f"Test passed simulation ID {orig_id} with invalid solver code \
                {orig_id[6:8]}:{int(orig_id[6:8], 16)}, yielding simulation parameters {error_params}."

        else:
            solvers_available = True
            try:
                manager_params = get_simulation_params_from_id(orig_id)
            except:
                print(f"Could not test ID {orig_id} due to missing solver")
                solvers_available = False
            if solvers_available:
                manager = TrialManager(**manager_params)
                recovered_id = generate_simulation_id(manager)
                assert (
                    orig_id == recovered_id
                ), f"orig_id {orig_id} and recovered_id {recovered_id} differ"
