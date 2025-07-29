from common.quantum.protocols.proof_of_work_protocol import ProofOfWorkProtocol

class ProofOfWorkProtocolSA(ProofOfWorkProtocol):
    
    def __init__(self):
        super().__init__()
        
    def generate_sampler(self):
        sampler = SimulatedAnnealingSampler()
        return sampler