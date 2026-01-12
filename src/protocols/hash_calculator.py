import time
import os
import binascii

from abc import ABC, abstractmethod
from collections import namedtuple
from enum import Enum

from directory_paths import BOOTSTRAP_PATH, EMBEDDINGS_PATH
from src.utilities import quantum_cubic_utils
from src.utilities.random_projection import RandomProjectionHasher
from src.values import DEFAULT_NUM_READS, ADVANTAGE4_1_MAX_NUM_READS

from dwave.system import DWaveSampler
from dwave.cloud import Client

import numpy as np

from src.values import (
    DEFAULT_ENERGY_TIME_RESCALING,
)


class SolverName(Enum):
    SOLVER1 = "Advantage_system4.1"
    SOLVER2 = "Advantage_system6.4"
    SOLVER3 = "Advantage2_system1.10"
    BOOTSTRAP1 = "simulated_Advantage2_prototype2.6"  # No longer general access
    BOOTSTRAP2 = "simulated_Advantage_system4.1"
    BOOTSTRAP3 = "simulated_Advantage_system6.4"
    BOOTSTRAP4 = "simulated_Advantage_system7.1"  # Offline


SolverParams = namedtuple(
    "SolverParams",
    ["solver_name", "profile"],
    defaults=(None, "defaults"),
)


class HashSolver(ABC):

    @abstractmethod
    def calculate_quantum_hash(
        self, hash_length: int, rng_seed: int
    ) -> tuple[str, np.ndarray, float]:
        """Template for the method to calculate quantum hash values. Implementation will vary by solver type,
        but input and return values should stay consistent.

        Args:
            hash_length (int): length (in bits) of the hash to be calculated
            rng_seed (int): For the case of sampling from QPUs the random seed
                sets the unitary evolution parameters
                (for quantum experiments) and random projections defining witnesses.
                For the case of bootstrap sampling, it initiates the pseudorandom
                sampling of offline data models.

        Returns:
            hash_bits: a np vector whose values should be exclusively 0s and 1s, defining the quantum hash.
                    Note that this will be processed into a hex string and stored as such by the Block class: it's
                    more convenient to leave it as raw bits here.
            dot_vector: a np vector encoding the hyperplane distance for each bit (that is, the dot product of the
                        hash vector and the hyperplane's normal vector)
            sample_time: the time required by the sampler to generate the sampler_output
        """
        pass

    @property
    def solver_name(self) -> str:
        return self._solver_name


def initialize_solver(solver_name: str) -> HashSolver:
    """Function to allow a HashSolver of either type to be initiated from a SolverParams tuple, without
        having to check which type of solver it is and invoke either subclass directly.
    Args:
        init_params (SolverParams): Information about each of the fields can be found in the main docstring
                    in trials_main.py
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

    def __init__(self, solver_name: str, dW=1.0, num_reads=600) -> None:
        """Initializes a bootstrap solver. Does not use any of the passed parameters except the solver name,
            which it uses to determine which bootstrapping files to draw from. These file must be in place
            in the filesystem for the initialization to succeed.

        Args:
            init_params (SolverParams): Information about each of the fields can be found in the main docstring
                in trials_main.py
            dW: rescaling of witnesses. Relevant to confidence-based chainwork
                assessments.
        """

        self._solver_name = solver_name
        assert (
            self.solver_name in BootstrappingHashSolver.allowed_solvers()
        ), f"BootstrappingHashSolver was initialized with incompatible solver name {self.solver_name}. Allowed names are {self.allowed_solvers}"
        mean_filepath = os.path.join(BOOTSTRAP_PATH, self.solver_name + "_mean.npy")
        var_filepath = os.path.join(BOOTSTRAP_PATH, self.solver_name + "_var.npy")
        self.mean_witnesses = np.load(mean_filepath)
        self.var_witnesses = np.load(var_filepath)
        self.num_witnesses = self.mean_witnesses.size
        self.dW = dW
        self.num_reads = num_reads

    @staticmethod
    def allowed_solvers() -> list[str]:
        """The BootstrappingHashSolver class is specifically intended to implement bootstrapped simulations of quantum
        measurements, rather than the real things. As such, it only uses those Solver types that work in this way, and
        disallows the use of any of the actual QPU solvers."""
        return [str(sn.value) for sn in SolverName if "simulated" in str(sn.value)]

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

        sample_start = time.time()
        prng_header = np.random.default_rng(rng_seed)
        prng_sampling = np.random.default_rng()
        indices = prng_header.integers(self.num_witnesses, size=hash_length)
        mu = self.mean_witnesses.ravel()[indices]
        var = ADVANTAGE4_1_MAX_NUM_READS * self.var_witnesses.ravel()[indices] / self.num_reads
        dot_vector = (mu + np.sqrt(var) * prng_sampling.normal(size=hash_length)) / self.dW
        bool_vector = dot_vector > 0
        hash_bits = bool_vector.astype(int)
        sample_end = time.time()
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
        solver_name: str,
        randomize_embedding: bool = False,
        profile: str = "defaults",
        num_reads: int = 600,
    ) -> None:
        """Initializes the QuantumHashSolver object, which will create and maintain a connection to the
        indicated D-Wave Solver as long as this object in instantiated.

        Args:
            init_params (SolverParams): Information about each of the fields can be found in the main docstring
                in trials_main.py
        """
        if solver_name not in DEFAULT_ENERGY_TIME_RESCALING:
            raise ValueError(
                "Unsupported {solver_name}: See examples/ for generation of energy-time rescaling values and embeddings"
            )
        self._solver_name = solver_name
        assert (
            self._solver_name in QuantumHashSolver.allowed_solvers()
        ), f"QuantumHashSolver was initialized with incompatible solver name {self.solver_name}. Allowed names are {self.allowed_solvers}"
        self.embedding_directory = EMBEDDINGS_PATH
        self.sampler_kwargs = dict(
            fast_anneal=True,
            annealing_time=0.005 / DEFAULT_ENERGY_TIME_RESCALING[solver_name][1],
            auto_scale=False,
            num_reads=DEFAULT_NUM_READS,
        )
        self.problem_energy_scale = DEFAULT_ENERGY_TIME_RESCALING[solver_name][0]
        self.profile = profile
        self.client = Client.from_config(profile=self.profile)  # TODO check if this is needed
        self.qpu = DWaveSampler(solver=self.solver_name, profile="defaults")

    @staticmethod
    def allowed_solvers() -> list[str]:
        return [str(sn.value) for sn in SolverName if "simulated" not in str(sn.value)]

    def calculate_quantum_hash(
        self, hash_length: int, rng_seed: int
    ) -> tuple[str, np.ndarray, float]:
        """Implementation of quantum hash calculation for solvers simulated using bootstrapping. Requires
            Bootstrapping files for the current solver to be in place in order to function.

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
        sampler = quantum_cubic_utils.generate_default_sampler(
            J.keys(),
            qpu=self.qpu,
            embedding_directory=self.embedding_directory,
        )
        sample_start = time.time()
        sampler_output = sampler.sample_ising(
            h, J, **self.sampler_kwargs
        )  # TODO decide when and if passing sampleset info is useful
        sample_end = time.time()

        stats = quantum_cubic_utils.build_stats(sampler_output, J.keys())
        problem_id = sampler_output._info[
            "problem_id"
        ]  # TODO figure out where to pass through or eliminate
        del problem_id  # Failed attempts to work around memory leak issue, can likely delete
        del sampler_output  # Failed attempts to work around memory leak issue, can likely delete
        del sampler  # Failed attempts to work around memory leak issue, can likely delete

        hv = RandomProjectionHasher(
            random_seed=rng_seed + 1, input_dimension=stats.size, nbits=hash_length
        )

        hash_bits, dot_vector = hv.hash_vector(stats.reshape(-1))
        del stats
        sample_time = sample_end - sample_start
        quantum_hash = binascii.hexlify(np.packbits(hash_bits)).decode(encoding="utf-8")

        return quantum_hash, dot_vector, sample_time
