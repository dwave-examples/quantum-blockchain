import sys, os, time, json, copy
from multiprocess import Process
from src.trials.trial_manager import TrialManager
from src.trials.trial_owners import TrialOwners
from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu
from src.common.values import TRIAL_PARAMETERS_FILE
from demo_configs import EMBEDDINGS_DIRECTORY, TRIAL_INIT_FILE, PAUSE_FILE, RESET_FILE

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

class TrialProcess(Process):
    def __init__(self, trial_directory: str):
        super().__init__()
        self.trial_directory = trial_directory

    def run(self):

        #Wait for first initialization
        while(True):
            if os.path.exists(TRIAL_INIT_FILE):
                with open(TRIAL_INIT_FILE, 'r') as f:
                    trial_params = json.load(f)
                break
            else:
                time.sleep(0.3)

        #Perform first-time setup
        trial_owners = TrialOwners()
        self.owner_keys = [owner.private_key.export_key().decode('utf8') for owner in trial_owners]
        del trial_owners

        pow_protocol = ProofOfWorkProtocolQpu(embedding_directory=EMBEDDINGS_DIRECTORY,
                                          randomize_solver=trial_params["Random_Solver"], 
                                          randomize_embedding=trial_params["Random_Solver"], 
                                          profile=trial_params["Profile"],
                                          solver=trial_params["Solver"], 
                                          annealing_time=trial_params["Annealing_Time"], 
                                          ensemble=trial_params["Ensemble"])

        pow_protocol.to_json(self.trial_directory)


        while os.path.exists(self.trial_directory):

            trial_params.update({"Owners": self.owner_keys})
            with open(os.path.join(self.trial_directory, TRIAL_PARAMETERS_FILE), 'w') as f:
                json.dump(trial_params, f)
            manager = TrialManager(self.trial_directory)
            while not os.path.exists(RESET_FILE):
                if not(os.path.exists(PAUSE_FILE) or manager.iteration_number >= manager.max_blocks):
                    manager.miner_step()
                time.sleep(0.1)

            with open(RESET_FILE, 'r') as f:
                self.trial_directory = f.read()
            with open(TRIAL_INIT_FILE, 'r') as f:
                trial_params = json.load(f)
            os.remove(RESET_FILE)
