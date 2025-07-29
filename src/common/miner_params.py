from Crypto.PublicKey import RSA
import json
import os

class MinerParams:

    json_filename = 'miner_params.json'

    def __init__(self, id: str, allowable_err: int, scoring_function: str, private_key = None) -> None:
        self.id = id
        self.allowable_err = allowable_err
        self.scoring_function = scoring_function
        
        if private_key:
            self.private_key = private_key
        else:
            new_key = RSA.generate(2048)
            self.private_key = new_key.export_key().decode('utf-8')
        
    @property
    def to_dict(self):
        params_dict = {
            'id': self.id,
            'allowable_err': self.allowable_err,
            'scoring_function': self.scoring_function,
            'private_key': self.private_key
        }

        return params_dict
    
    def to_file(self, dirname: str):
        with open(os.path.join(dirname, MinerParams.json_filename), 'w') as f:
            json.dump(self.to_dict, f)
    
    @staticmethod
    def from_dict(d: dict):
        if 'private_key' in d:
            miner_params = MinerParams(d['id'], d['allowable_err'], 
                                       d['scoring_function'], d['private_key'])
        else:
            miner_params = MinerParams(d['id'], d['allowable_err'], 
                                       d['scoring_function'])
            
        return miner_params
    

    @staticmethod
    def from_file(directory: str):
        filepath = os.path.join(directory, MinerParams.json_filename)
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                json_params = json.load(f)
            return MinerParams.from_dict(json_params)
        else:
            return None

