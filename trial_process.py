import sys, os, time, json, copy
from multiprocess import Process
from src.trials.trial_manager import TrialManager
from src.trials.trial_owners import TrialOwners
from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu
from src.common.values import TRIAL_PARAMETERS_FILE
from demo_configs import TRIAL_INIT_FILENAME, TRIAL_DEFAULTS, EMBEDDINGS_DIRECTORY

CUR_DIR = os.path.dirname(os.path.realpath(__file__))




class TrialProcess(Process):
    def __init__(self, trial_directory: str):
        super().__init__()
        self.trial_directory = trial_directory


    def run(self):
        filepath = os.path.join(self.trial_directory, TRIAL_INIT_FILENAME)
        while(True):
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    init_params = json.load(f)
                break
            else:
                time.sleep(0.3)

        num_miners = init_params["Miners"]
        num_blocks = init_params["Blocks"]
        trial_owners = TrialOwners()
        trial_params = copy.deepcopy(TRIAL_DEFAULTS)
        trial_params.update({'Miners':num_miners,'Blocks':num_blocks, 
                             'Owners': [owner.private_key.export_key().decode('utf8') 
                                        for owner in trial_owners] })

        with open(os.path.join(self.trial_directory, TRIAL_PARAMETERS_FILE), 'w') as f:
                json.dump(trial_params, f)


        pow_protocol = ProofOfWorkProtocolQpu(embedding_directory=EMBEDDINGS_DIRECTORY,
                                          randomize_solver=trial_params["Random_Solver"], 
                                          randomize_embedding=trial_params["Random_Solver"], 
                                          profile=trial_params["Profile"],
                                          solver=trial_params["Solver"], 
                                          annealing_time=trial_params["Annealing_Time"], 
                                          ensemble=trial_params["Ensemble"])

        pow_protocol.to_json(self.trial_directory)
        manager = TrialManager(self.trial_directory)

        while(manager.iteration_number < num_blocks):
            if True: #figure out file condition
                manager.miner_step()
            time.sleep(0.1)
