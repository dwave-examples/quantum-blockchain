import pytest

import numpy as np

import dimod
from dwave.system import DWaveSampler
from dwave.system.testing import MockDWaveSampler


from src.protocols.hash_calculator import (
    SolverName,
    initialize_solver,
    BootstrappingHashSolver,
)

client_supported_solver_name = None

for sv in SolverName:
    try:
        DWaveSampler(solver=sv.value, profile="defaults")
        client_supported_solver_name = sv.value
        print(sv.value)
        break
    except:
        pass


def test_SolverName():
    assert "Advantage" in SolverName.SOLVER1.value
    assert "simulated" in SolverName.BOOTSTRAP1.value
    assert SolverName.SOLVER1.name == "SOLVER1"
    assert SolverName.SOLVER1 in SolverName


@pytest.mark.skipif(client_supported_solver_name is None, reason="supported QPU client unavailable")
def test_initialize_solver_qpu_client():
    initialize_solver(solver_name=client_supported_solver_name)


def test_initialize_solver_bootstrap():
    initialize_solver(solver_name = SolverName.BOOTSTRAP1.value)
    pass


def test_BootstrappingHashSolver():
    mean_witnesses = np.array([0, 1])
    var_witnesses = np.array([0, 1e-6])  # Exactly 0, and close to 1
    bhs1 = BootstrappingHashSolver(mean_witnesses=mean_witnesses)
    hash_length = 100
    str_id, hash1, timing = bhs1.calculate_quantum_hash(hash_length, rng_seed=0)
    print(str_id, timing)
    assert hash1.size == hash_length
    assert np.array_equal(
        np.unique(hash1), np.arange(2)
    ), "0. and 1. should be only resampled values. Both occurring with high probability"

    bhs2 = BootstrappingHashSolver(
        mean_witnesses=mean_witnesses, var_witnesses=var_witnesses, var_rescaling=0.0
    )
    _, hash2a, _ = bhs2.calculate_quantum_hash(hash_length, rng_seed=0)
    assert np.array_equal(hash1, hash2a), "Same seed, but not same result"
    _, hash2b, _ = bhs2.calculate_quantum_hash(hash_length, rng_seed=1)
    assert not np.array_equal(hash2a, hash2b), "Different seed, same result"

    bhs3 = BootstrappingHashSolver(mean_witnesses=mean_witnesses, var_witnesses=var_witnesses)
    # With high probability, all values bigger than 1, 1 absent and 0. present.
    _, hash3, _ = bhs3.calculate_quantum_hash(hash_length, rng_seed=2)
    assert np.all(hash3 >= 0), "Values are 0. and 1 + small random, shouldn't be negative numbers"
    assert np.any(hash3 == 0.0), "Value 0. should be present with high probability"
    assert not np.any(hash3 == 1.0), "Value 1. should be absent with high probability"
