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

import dimod
import numpy as np
import pytest
from dwave.system import DWaveSampler

from src.protocols.hash_calculator import (
    QuantumHashSolver,
    SimulatedHashSolver,
    SolverName,
    initialize_solver,
)

client_supported_solver_name = None

for sv in SolverName:
    try:
        DWaveSampler(solver=sv.value)
        client_supported_solver_name = sv.value
        print(sv.value)
        break
    except:
        pass


def test_SolverName():
    assert "Advantage" in SolverName.SOLVER1.value
    assert "simulated" in SolverName.SIMULATED1.value
    assert SolverName.SOLVER1.name == "SOLVER1"
    assert SolverName.SOLVER1 in SolverName


def test_initialize_solver_simulated():
    initialize_solver(solver_name=SolverName.SIMULATED1.value)
    pass


def test_SimulatedHashSolver():
    mean_witnesses = np.array([0, 1])
    var_witnesses = np.array([0, 1e-6])  # Exactly 0, and close to 1
    bhs1 = SimulatedHashSolver(mean_witnesses=mean_witnesses)
    hash_length = 100
    str_id, hash1, timing = bhs1.calculate_quantum_hash(hash_length, rng_seed=0)
    print(str_id, timing)
    assert hash1.size == hash_length
    assert np.array_equal(
        np.unique(hash1), np.arange(2)
    ), "0. and 1. should be only resampled values. Both occurring with high probability"

    bhs2 = SimulatedHashSolver(
        mean_witnesses=mean_witnesses, var_witnesses=var_witnesses, var_rescaling_factor=0.0
    )
    _, hash2a, _ = bhs2.calculate_quantum_hash(hash_length, rng_seed=0)
    assert np.array_equal(hash1, hash2a), "Same seed, but not same result"
    _, hash2b, _ = bhs2.calculate_quantum_hash(hash_length, rng_seed=1)
    assert not np.array_equal(hash2a, hash2b), "Different seed, same result"

    bhs3 = SimulatedHashSolver(mean_witnesses=mean_witnesses, var_witnesses=var_witnesses)
    # With high probability, all values bigger than 1, 1 absent and 0. present.
    _, hash3, _ = bhs3.calculate_quantum_hash(hash_length, rng_seed=2)
    assert np.all(hash3 >= 0), "Values are 0. and 1 + small random, shouldn't be negative numbers"
    assert np.any(hash3 == 0.0), "Value 0. should be present with high probability"
    assert not np.any(hash3 == 1.0), "Value 1. should be absent with high probability"


def test_QuantumHashSolver():
    # Instantiation at defaults with client, exercising the default directory
    # structure is already tested, here we use a MockSampler
    sampler = dimod.RandomSampler()
    sampler_kwargs = {"num_reads": 100}
    qhs = QuantumHashSolver(
        sampler=sampler,
        energy_time_rescaling=(1.0, 1.0),
        embedding_directory="./",
        sampler_kwargs=sampler_kwargs,
    )
    assert qhs.solver_parameters.solver_name == None
    assert qhs.solver_parameters.profile == None
    for hash_length in [32, 64]:
        ascii_hash, qhs_hash, t = qhs.calculate_quantum_hash(hash_length=hash_length, rng_seed=0)
        assert t > 0
        assert len(qhs_hash) == hash_length, "ascii_hash should be ceil(hash_length /4)"
        assert len(ascii_hash) * 4 == hash_length, "ascii_hash should be ceil(hash_length /4)"


@pytest.mark.skipif(client_supported_solver_name is None, reason="supported QPU client unavailable")
def test_initialize_solver_qpu_client():
    qhs = initialize_solver(solver_name=client_supported_solver_name)
    hash_length = 1024
    _, qhs_hash1a, _ = qhs.calculate_quantum_hash(hash_length=hash_length, rng_seed=0)
    _, qhs_hash1b, _ = qhs.calculate_quantum_hash(hash_length=hash_length, rng_seed=0)
    _, qhs_hash2, _ = qhs.calculate_quantum_hash(hash_length=hash_length, rng_seed=1)
    overlap11 = qhs_hash1a @ qhs_hash1b
    overlap12a = qhs_hash1a @ qhs_hash2
    overlap12b = qhs_hash1b @ qhs_hash2
    assert (
        overlap11 > overlap12a
    ), "Verification for the same problem, should be better than for random pairs, with high probability"
    assert (
        overlap11 > overlap12b
    ), "Verification for the same problem, should be better than for random pairs, with high probability"
