import json
import os
import random

from dwave.system import DWaveSampler
import dwave.cloud

from src.quantum.protocols.proof_of_work_protocol import ProofOfWorkProtocol
import src.quantum.quantum_cubic_utils as quantum_cubic_utils
from src.common.values import POW_QPU_FILE

class ProofOfWorkProtocolQpu(ProofOfWorkProtocol):
    
    def __init__(self, embedding_directory: str,  model_size: int=4,
                 ensemble: str='PMJ', randomize_solver: bool=False, randomize_embedding: bool=False, annealing_time:float =0.005,
                solver: str='Advantage2_prototype2.6', profile: str='defaults', validate_transactions: bool=True):
        """Initialize the ProofOfWorkQPU class

        Args:
            solver (str, optional): The name of the D-Wave solver to use. Defaults to "Advantage2_prototype2.6"
            embedding_directory (str, optional): The directory to use for the embedding. Defaults to "embeddings".
            model_size (int, optional): The size of the model to use. Defaults to 4.
        """
        super().__init__()
        self.solver_type = 'QPU'
        self.model_size = model_size
        self.ensemble = ensemble
        self.randomize_solver = randomize_solver
        self.randomize_embedding = randomize_embedding
        self.embedding_directory = embedding_directory
        self.annealing_time = annealing_time
        self.solver = solver
        self.validate_transactions = validate_transactions
        if self.randomize_solver:
            self.available_solvers = list(quantum_cubic_utils.get_GA_solver_energy_scales().keys())
            self._qpus = []
            for solver in self.available_solvers:
                try:
                    self._qpus.append(DWaveSampler(solver=solver, profile=profile))
                except dwave.cloud.exceptions.SolverNotFoundError as ee:
                    msg = f"Solver {solver} not found."
                    raise ValueError(msg)
        else:
            self._qpu = DWaveSampler(solver=solver)


    @property
    def qpu(self):
        if self.randomize_solver:
            qpu = random.choice(self._qpus)
            self._qpu = qpu
            return qpu
        return self._qpu

    
    @property
    def chip_id(self) -> str:
        """Returns the chip_id of the last qpu used. Returns None if no qpu was used.
        """
        if not hasattr(self, '_qpu'):
            raise ValueError("Attempting to access chip_id before qpu was set. This may be the " +\
                "case if you are using a random solver and have not yet access the qpu property.")
        return self._qpu.properties['chip_id']


    def get_random_solver(self) -> tuple[str, DWaveSampler]:
        """Returns a random solver and its corresponding DWaveSampler

        Returns:
            tuple[str, DWaveSampler]: The name of the solver and its corresponding DWaveSampler
        """
        idx = random.randint(0, len(self.available_solvers) - 1)
        qpu = self._qpus[idx]
        self._qpu = qpu
        return self.available_solvers[idx], qpu
    
    def to_json(self, directory: str) -> None:
        """Writes this objects attributes to a json file in the specified 
        directory

        Args:
            directory (str): The directory to save the json file
        """
        json_dict = {
            'solver': self.solver,
            'model_size': self.model_size,
            'ensemble': self.ensemble,
            'randomize_solver': self.randomize_solver,
            'randomize_embedding': self.randomize_embedding,
            'embedding_directory': self.embedding_directory,
            'annealing_time': self.annealing_time,
            'validate_transactions': self.validate_transactions
        }

        with open(os.path.join(directory, POW_QPU_FILE), 'w') as f:
            json.dump(json_dict, f)
        
    @staticmethod
    def from_json(directory: str):
        """Reads the attributes of this object from a json file in the specified
        directory

        Args:
            directory (str): The directory to read the json file from
        """
        with open(os.path.join(directory, POW_QPU_FILE), 'r') as f:
            json_dict = json.load(f)
        
        return ProofOfWorkProtocolQpu(**json_dict)