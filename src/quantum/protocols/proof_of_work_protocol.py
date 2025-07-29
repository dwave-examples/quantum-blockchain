from abc import ABC, abstractmethod

from dwave.system import DWaveSampler

class ProofOfWorkProtocol (ABC):
    
    def __init__(self):
        pass
    
    @abstractmethod
    def from_json(self, *args, **kwargs):
        raise NotImplementedError