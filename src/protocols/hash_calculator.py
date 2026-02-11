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

import binascii
import os
import time
from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum

import dimod
import numpy as np
from dwave.cloud import Client
from dwave.system import DWaveSampler

from directory_paths import (
    BOOTSTRAP_PATH,
    EMBEDDINGS_PATH,
)
from src.utilities import quantum_cubic_utils
from src.utilities.random_projection import RandomProjectionHasher
from src.values import (
    BOOTSTRAP_DATA_NUM_READS,
    DEFAULT_ANNEALING_TIME,
    DEFAULT_ENERGY_TIME_RESCALING,
    DEFAULT_NUM_READS,
)

class SolverName(Enum):
    SOLVER1 = "Advantage_system4.1"
    SOLVER2 = "Advantage_system6.4"
    SOLVER3 = "Advantage2_system1.11"
    BOOTSTRAP1 = "simulated_Advantage2_prototype2.6"  # No longer general access
    BOOTSTRAP2 = "simulated_Advantage_system4.1"
    BOOTSTRAP3 = "simulated_Advantage_system6.4"
    BOOTSTRAP4 = "simulated_Advantage_system7.1"  # Offline

SolverParams = namedtuple(
    "SolverParams",
    ["solver_name", "profile"],
    defaults=(None, None),
)

class HashSolver(ABC):
    @abstractmethod
    def calculate_quantum_hash(
        self, hash_length: int, rng_seed: int | None = None
    ) -> tuple[str, np.ndarray, float]:
        """Template for the method to calculate quantum hash values. Implementation will vary by solver type,
        but input and return values should stay consistent.

        Args:
            hash_length (int): length (in bits) of the hash to be calculated
            rng_seed (int): For the case of sampling from QPUs the random seed
                sets the unitary evolution parameters
                (for quantum experiments) and random projections defining witnesses.
                For the case of simulated sampling, it initiates the pseudorandom
                sampling of offline data models.

        Returns:
            hash_bits: a np vector whose values should be exclusively 0s and 1s, defining the quantum hash.
                    Note that this will be processed into a hex string and stored as such by the Block class: it's
                    more convenient to leave it as raw bits here.
            dot_vector: a np vector encoding the hyperplane distance for each bit (that is, the dot product of the
                        hash vector and the hyperplane's normal vector)
            sample_time: the time required by the sampler to generate the sampler_output
        """

    @property
    def solver_name(self) -> str:
        return self._solver_name


def initialize_solver(solver_name: str) -> HashSolver:
    """Function to allow a HashSolver of either type to be initiated from a SolverParams tuple, without
        having to check which type of solver it is and invoke either subclass directly.
    Args:
        solver_name: A SolverName compatible value used to initialize a QPU or simulated solver.
    Returns:
        A HashSolver
    """

    if solver_name not in [str(n.value) for n in SolverName]:
        raise Exception(
            f"Unrecognized solver name {solver_name} passed. Allowed names are {[str(n.value) for n in SolverName]}"
        )
    elif "simulated" in solver_name:
        return BootstrappingHashSolver(solver_name)
    else:
        return QuantumHashSolver(solver_name)


class BootstrappingHashSolver(HashSolver):
    def __init__(
        self,
        solver_name: str = None,
        *,
        bootstrap_path: str = BOOTSTRAP_PATH,
        mean_witnesses: np.ndarray | None = None,
        var_witnesses: np.ndarray | None = None,
        var_rescaling_factor: float | None = None,
    ) -> None:
        """Initializes a simulated solver from a source file or by provision of numpy arrays.

        Args:
            solver_name: The solver_name which specifies a lookup file for loading witness statistics.
            bootstrap_path: Path to the directory containing the witness data.
            mean_witnesses: A numpy array of expected witness values.
            var_witnesses: A numpy array of expected witness variances.
            var_rescaling: Variance rescaling allows emulation of variable sampling error (or high frequency control error) .
                Resampled witnesses are distributed as ~ N(mean, variance*variance_rescaling)).
                If fewer/more reads are to be simulated, relative to the value used in data correction we can scale accordingly.
        """
        if solver_name is None and mean_witnesses is None:
            raise Exception("Witness must be provided or a solver associated to a source file specified")
        if mean_witnesses is None:
            self._solver_name = solver_name
            mean_filepath = os.path.join(bootstrap_path, self.solver_name + "_mean.npy")
            var_filepath = os.path.join(bootstrap_path, self.solver_name + "_var.npy")
            self.mean_witnesses = np.load(mean_filepath)
            var_witnesses = np.load(var_filepath)
        else:
            self._solver_name = None
            self.mean_witnesses = mean_witnesses
            if var_witnesses is None:
                var_witnesses = np.zeros(shape=mean_witnesses.shape)
        if var_rescaling_factor is None:
            var_rescaling_factor = float(BOOTSTRAP_DATA_NUM_READS)/float(DEFAULT_NUM_READS)
        self.var_witnesses = var_rescaling_factor * var_witnesses
        self.num_witnesses = self.mean_witnesses.size

    def calculate_quantum_hash(
        self, hash_length: int, rng_seed: int
    ) -> tuple[str, np.ndarray, float]:
        """Implementation of quantum hash calculation for solvers simulated using bootstrapping. Requires
            Bootstrapping files for the current solver to be in place in order to function.

        Args:
            hash_length (int): length of the quantum hash to use, in bits
            rng_seed (int): a seed to use to determine which witnesses to draw from

        Returns:
            quantum_hash (str): the quantum hash formatted as a hexidecimal string. Note that
                this means that the length will be 1/4 (rounded up) of the passed hash length
                since a hex digit can store 4 binary digits.
            dot_vector (np.ndarray): vector of hyperplane distances. Used in calculating confidence
            sample_time (float): sampling time. Not much interest when bootstrapping, but must be
                included to match the output signature of the QPU version."""

        sample_start = time.perf_counter()
        prng_header = np.random.default_rng(rng_seed)
        prng_sampling = np.random.default_rng()
        indices = prng_header.integers(self.num_witnesses, size=hash_length)
        mu = self.mean_witnesses.ravel()[indices]
        var = self.var_witnesses.ravel()[indices]

        dot_vector = mu + np.sqrt(var) * prng_sampling.normal(size=hash_length)
        bool_vector = dot_vector > 0
        hash_bits = bool_vector.astype(int)
        sample_end = time.perf_counter()
        sample_time = sample_end - sample_start

        quantum_hash = binascii.hexlify(np.packbits(hash_bits)).decode(encoding="utf-8")

        return quantum_hash, dot_vector, sample_time


class QuantumHashSolver(HashSolver):
    """Implementation of quantum hash calculation with D-Wave Solver. Requires an active solver
    connection to run."""

    @property
    def solver_parameters(self) -> SolverParams:
        return SolverParams(
            solver_name=self.solver_name,
            profile=self.profile,
        )

    def __init__(
        self,
        solver_name: str | None = None,
        *,
        profile: str = None,
        num_reads: int = DEFAULT_NUM_READS,
        reference_annealing_time: float = DEFAULT_ANNEALING_TIME,
        energy_time_rescaling: tuple[float, float] | None = None,
        embedding_directory: str = EMBEDDINGS_PATH,
        sampler_kwargs: dict | None = None,
        sampler: dimod.Sampler | None = None,
    ) -> None:
        """Initializes the QuantumHashSolver object, which will create and maintain a connection to the
        indicated D-Wave Solver as long as this object in instantiated.

        Args:
            solver_name: The name of the QPU solver
            profile: client profile
            num_reads: number of QPU reads per hash calculation
            reference_annealing_time: targeted evolution time with respect to Advantage2_prototype2 schedule.
            energy_time_rescaling: problem Hamiltonian and time rescaling factors required
                 to emulate Advantage2_prototype2 dynamics with the given solver.
            embedding_directory: Location of embeddings
            sampler: A `dimod.Sampler`, when not specified the solver name and profile is used to select
                a QPU with the Leap client, and a suitable embedding is loaded. non-QPU samplers
                are used for testing.
            sampler_kwargs: Arguments for the dimod sampler, defaulted to QPU fast annealing
                arguments when not specified. Non defaulted arguments are used for testing.
        """

        if energy_time_rescaling is None:
            if solver_name not in DEFAULT_ENERGY_TIME_RESCALING:
                raise ValueError(
                    "Unsupported {solver_name}: See calibration/ for generation of energy-time rescaling values and embeddings"
                )
            problem_hamiltonian_rescaling, time_rescaling = DEFAULT_ENERGY_TIME_RESCALING[solver_name]
        else:
            problem_hamiltonian_rescaling, time_rescaling = energy_time_rescaling

        self._solver_name = solver_name
        if sampler_kwargs is None:
            self.sampler_kwargs = dict(
                fast_anneal=True,
                annealing_time=reference_annealing_time / time_rescaling,
                auto_scale=False,
                num_reads=num_reads,
                label=f"Examples - Quantum Blockchain",
            )
        else:
            self.sampler_kwargs = sampler_kwargs
        self.problem_energy_scale = problem_hamiltonian_rescaling
        self.profile = profile

        if sampler is None:
            qpu = DWaveSampler(solver=self.solver_name, profile=self.profile)
            _, source_edge_list = quantum_cubic_utils.create_lattice()

            self.sampler = quantum_cubic_utils.generate_default_sampler(
                source_edge_list,
                qpu=qpu,
                embedding_directory=embedding_directory,
            )
        else:
            self.sampler = sampler

    def calculate_quantum_hash(
        self, hash_length: int, rng_seed: int
    ) -> tuple[str, np.ndarray, float]:
        """Implementation of quantum hash calculation for QPU samplers

        Args:
            hash_length (int): length of the quantum hash to use, in bits
            rng_seed (int): a seed to use to determine parameters of the quantum experiment

        Returns:
            quantum_hash (str): the quantum hash formatted as a hexidecimal string. Note that
                this means that the length will be 1/4 (rounded up) of the passed hash length
                since a hex digit can store 4 binary digits.
            dot_vector (np.ndarray): vector of hyperplane distances. Used in calculating confidence
            sample_time (float): time spent sampling the D-Wave solver"""

        h, J = quantum_cubic_utils.create_model(
            seed=rng_seed, problem_energy_scale=self.problem_energy_scale
        )
        sample_start = time.perf_counter()
        sampler_output = self.sampler.sample_ising(h, J, **self.sampler_kwargs)
        sample_end = time.perf_counter()

        stats = quantum_cubic_utils.build_stats(sampler_output, J.keys())

        hv = RandomProjectionHasher(
            random_seed=rng_seed + 1, input_dimension=stats.size, nbits=hash_length
        )

        hash_bits, dot_vector = hv.hash_vector(stats.reshape(-1))
        sample_time = sample_end - sample_start
        quantum_hash = binascii.hexlify(np.packbits(hash_bits)).decode(encoding="utf-8")

        return quantum_hash, dot_vector, sample_time
