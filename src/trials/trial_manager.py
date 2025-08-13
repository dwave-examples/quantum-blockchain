import json
import os
import random
import time
import copy

import networkx as nx
import numpy as np
import pandas as pd
from pathlib import Path

from src.trials.trial_owners import TrialOwners
from src.common.owner import Owner
from src.common.miner_params import MinerParams
from src.common.miner import Miner
from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu
from src.trials.graph_generator import graph_gen_main
from src.common.initialize_default_blockchain import initialize_blockchain
from src.common.values import NUMBER_OF_LEADING_ZEROS, TRIAL_PARAMETERS_FILE, BLOCKCHAIN_FILE
from demo_constants import BASE_GLOBAL_GRAPH_FILE, BASE_MINER_GRAPH_FILE, MINER_STATS_FILE

class TrialManager:
    """This class manages a trial of blockchain mining. The purpose of this
    class is to be able to iterate through a series of blocks and maintain
    the state of the trial as it progresses. The latest successful trial
    will be saved to a file location so that it can be recovered if there
    is a failure in subsequent trials.
    """

    def __init__(self, trial_directory: str):
        """ Initializes a new TrialManager object. Requires a file with name matching
            the name stored in TRIAL_PARAMETERS_FILE (found in common.values) to be located
            in the same directory and properly formatted in order to initialize. Such a
            file should be created automatically by trials_main anytime it is run without
            being passed a directory argument. If restarting a trial in the same directory, this
            will simply initialized using the files already present.
                
            """
        self.trial_directory = trial_directory
        with open(os.path.join(self.trial_directory, TRIAL_PARAMETERS_FILE), 'r') as f:
            input_dict = json.load(f)

        self.pow_protocol = ProofOfWorkProtocolQpu.from_json(self.trial_directory)
        self.additional_validation = int(input_dict['Validation'])
        self.validate_transactions = input_dict['Transactions']
        self.max_blocks = int(input_dict["Blocks"])
        self.num_miners = int(input_dict["Miners"])
        self.scoring_function = input_dict['Scoring_Function']
        self.allowable_err = 0

        self.timing_filename = os.path.join(trial_directory, 'timing_summary.csv')
        self.initialize_timing_data()

        #Owner/blockchain initialization
        self.owners = TrialOwners(input_dict['Owners'])
        if not self.timing["Mining_Time"]:
            self.iteration_number = 0
            self.initialize_chain()
        else:
            self.iteration_number = len(self.timing["Iter_Total_Time"])
            #TODO miner-by-miner reinitialization

        #Miner initialization
        self.miners = []
        for i in range(self.num_miners):
            subdir = os.path.join(self.trial_directory, 'mem_' + str(i))

            #If subdir doesn't exist, need to create all miner init files
            if not os.path.exists(subdir):
                self.initialize_miner_file(subdir, i)

            miner = Miner(subdir)
            miner.update_blockchain_beliefs()
            self.miners.append(miner)
        
        self.mining_miner = None
        self.mined_block = None
        self.mined_block_result = None
        self.max_mining_attempts = 1000
        self.waiting_miners = {i for i in range(self.num_miners)}
        self.chain_rep_file_suffix = "blockchain_picture.txt"

        #Intialize Output folders/structures
        self.output_dfs = []
        self.iteration_summaries = []
        self.miner_stats_list = ["..." for i in range(self.num_miners)]

        self.miner_dag_dir = os.path.join(self.trial_directory, 'miner_dags')
        if not os.path.exists(self.miner_dag_dir):
            os.makedirs(self.miner_dag_dir)
            
        
    def initialize_chain(self):
        initial_block_dict = initialize_blockchain(self.owners.initial_distributions).to_dict
        initial_block_dict.update({'score':1})
        self.init_block_text = json.dumps(initial_block_dict) + '\n'

    def initialize_miner_file(self, subdir: str, miner_id: int):
        os.makedirs(subdir)
        miner_params = MinerParams(miner_id, self.allowable_err, self.scoring_function)
        miner_params.to_file(subdir)
        with open(os.path.join(subdir, BLOCKCHAIN_FILE), "a") as file_obj:
            file_obj.write(self.init_block_text)
        self.pow_protocol.to_json(subdir)

    def initialize_timing_data(self):
        if os.path.exists(self.timing_filename):
            time_df = pd.read_csv(self.timing_filename, dtype = float)
            self.timing = time_df.to_dict(orient = 'list')
            self.timing.pop('Unnamed: 0') #Index column automatically added by pandas. Can't turn off, causes errors if left in.
        else: 
            self.timing = {"Mining_Time":[], "Validation_Time":[], "Iter_Total_Time":[], "Iter_Total_Time_Per_Miner":[], 
                           "Trial_Total_Time":[], "Trial_Total_Time_Per_Miner":[]}
            
    def reset_miners(self) -> None:

        self.waiting_miners = {i for i in range(self.num_miners)}
        self.mining_miner = None
        self.mined_block = None
        self.mined_block_result = None
        self.miner_stats_list = ["..." for i in range(self.num_miners)]

    def update_miner_stats(self, miner: Miner, mining: bool, finished: bool, failed: bool = False):

        if failed:
            miner_status = "Rejected"
        else:
            prefix = ["Validat", "Min"]
            suffix = ["ing", "ed"]
            miner_status = prefix[int(mining)] + suffix[int(finished)]

        self.miner_stats_list[miner.id] = miner_status

        stats_dict = {"Block": self.iteration_number, "Miners": self.miner_stats_list}
        with open(MINER_STATS_FILE, 'w') as f:
            json.dump(stats_dict, f)


    def record_iteration_timing(self):
        iter_total_time = self.timing["Mining_Time"][-1] + self.timing["Validation_Time"][-1]
        self.timing["Iter_Total_Time"].append(iter_total_time)
        self.timing["Iter_Total_Time_Per_Miner"].append(iter_total_time/self.num_miners)
        if len(self.timing["Trial_Total_Time"]) > 0:
            self.timing["Trial_Total_Time"].append(self.timing["Trial_Total_Time"][-1] + iter_total_time)
        else:
            self.timing["Trial_Total_Time"].append(iter_total_time)
        self.timing["Trial_Total_Time_Per_Miner"].append(self.timing["Trial_Total_Time"][-1]/self.num_miners)

    def create_random_transaction(self, multiplier: float=0.05) -> None:
        """Creates a random transaction between two owners. The amount is a random
        float between 0 and 1 multiplied by the multiplier. The transaction is added
        to the strongest block of each miner.

        Args:
            multiplier (float, optional): The multiplier to use for the amount. Defaults to 0.01.

        Modifies:
            self.miners: Adds the transaction to the strongest block of each miner
        """
        sender, receiver = self.owners.select_random_pair()
        amount = multiplier * random.randint(1,3)
        self.add_transaction(sender, receiver, amount)

    def add_transaction(self, sender: Owner, receiver: Owner, amount: float) -> None:
        """Creates a transaction between sender and reciever of amount and adds it
        to the strongest block of each miner

        Args:
            sender (Owner): The sender of the transaction
            receiver (Owner): The receiver of the transaction
            amount (float): The amount of the transaction
        """
        for miner in self.miners: 
            transaction = sender.create_transaction_to(receiver, amount, miner.blockchain) #IMPORTANT: decision point where miners decide what block to mine on top of. Is it though?
            miner.mempool.store_transactions_in_memory(transactions=[transaction])    #Important to change if mempool is updated
            miner.pow.prep_new_block(miner.owner) #TODO revisit this when miner functions get moved out of the PoW classes.

    def record_iteration_summary(self):
        iteration_summary = pd.DataFrame({
            'Iteration': self.iteration_number,
            'Time': self.timing["Iter_Total_Time"][-1],
            '# of Active Paths': len(set([miner.blockchain.tree.strongest_block_hash for miner in self.miners])),
            "Longest Path Length": max([len(miner.blockchain.tree.trunk) for miner in self.miners]), #first two blocks are genesis and initial transactions
            "Miner Path Length": (len(self.mining_miner.blockchain.tree.trunk) - 1), #Ignore initial transactions, include genesis (my convention)      
            #"New Block % Successful Validation": len([x for x in validated if x == "True"])/len(self.miners.miners),
            #"New Block Average Failures": np.nanmean([x for x in num_failures if x is not None]), #TODO figure out a way to collect these stats
            }, index=[0])
        self.iteration_summaries.append(iteration_summary)

    def mine_new_block(self, active_miner):
        attempts = 0
        while attempts < self.max_mining_attempts:
            attempts += 1
            print("") #Print EOL after validation row.
            print("Miner ", active_miner.id, " attempting to mine...", end = " ")
            miner_result = active_miner.attempt_mine()
            if miner_result.valid:
                self.mined_block = active_miner.pow.new_block
                self.mined_block_result = miner_result
                print("Result: Success!")
                print("Miners Attempting to Validate...")
                break
            else:
                print("Result: Failure!")

        return miner_result, 0
    
    def validate_new_block(self, active_miner):
        success = False
        while not success:
            try:  #This probably needs to be re-written as it involves passing pow.blockchain. But not for sure
                miner_result, num_failures = active_miner.validate_new_block(new_block=self.mined_block, sender=self.mining_miner.hostname, 
                                                validation_result=self.mined_block_result, additional_validation=self.additional_validation)
                success = True
                if miner_result.valid and num_failures == 0:
                    print("Miner",active_miner.id,": Pass |", end = " ", flush = True)
                else:
                    print("Miner",active_miner.id,": Fail |", end = " ", flush = True)
            except Exception as ee: #TODO: need to catch specific exceptions
                raise ee
            
        return miner_result, num_failures

    def miner_step(self):
        start_time = time.time()
        mining = False
        active_miner_id = random.sample(sorted(self.waiting_miners), 1)[0]
        self.waiting_miners.remove(active_miner_id)
        active_miner = self.miners[active_miner_id]
        if self.mining_miner == None:
            self.update_miner_stats(active_miner, True, False)
            self.create_random_transaction()
            mining = True
            self.mining_miner = active_miner
            miner_result, num_failures = self.mine_new_block(active_miner)
            self.update_miner_stats(active_miner, True, True)
        else:
            self.update_miner_stats(active_miner, False, False)
            miner_result, num_failures = self.validate_new_block(active_miner)
            self.update_miner_stats(active_miner, False, True, failed=(num_failures > 0))
                
        block_score = int(1 -2 * (num_failures > 0))
        active_miner.add_block_to_chain(self.mined_block, block_score)

        finish_time = time.time()
        total_time = finish_time - start_time
        if mining:
            self.timing["Mining_Time"].append(total_time)
        elif len(self.timing["Mining_Time"]) > len(self.timing["Validation_Time"]):
            self.timing["Validation_Time"].append(total_time)
        else:
            self.timing["Validation_Time"][-1] += total_time

        miner_stats = copy.deepcopy(self.miner_stats_list)

        if not self.waiting_miners:
            self.record_iteration_timing()
            self.record_iteration_summary()
            self.write_output()
            self.reset_miners()
            self.iteration_number += 1
            
        return self.iteration_number, miner_stats

    def iterate(self, stop_iter = None) -> None:
        """Iterates through the trial for a specified number of blocks.

        Args:
            stop_iter (int): The block number to stop at. Defaults to the max
                             number of blocks for the trial. Argument provided to 
                             allow stepping through the trial in smaller increments
                             for debugging or other purposes.
        """
        if not stop_iter:
            stop_iter = self.max_blocks
        
        while self.iteration_number < stop_iter:
            self.miner_step()

        print(f"\nTrial completed for {self.iteration_number} blocks.")

    def write_output(self) -> None:
        """Writes the following outputs to the trial directory:
        - iteration_summary.csv: A csv file containing the summary of each iteration
        - timing_summary.csv: A csv file tracking the start and stops times of mining, validation and
                             other for each iteration, including usual summary statistics derived
                             from these.
        -beliefs_summary.json: A json file containing a list of aggregate miner beliefs of blocks in the order 
                                they were mined, along with a corresponding dict mapping block hash to mining order. 
        """
        #TODO re-examine this. None of this info seems useful to be logging every iteration, but we might want
        #a different summary set instead.
        iteration_summary_df = pd.concat(self.iteration_summaries)
        iteration_summary_df['Leading Zeros'] = NUMBER_OF_LEADING_ZEROS
        iteration_summary_df['Additional Validation'] = self.additional_validation
        iteration_summary_df['Number of Miners'] = len(self.miners)

        iteration_summary_df.to_csv(os.path.join(self.trial_directory, 'iteration_summary.csv'), index=False)

        timing_df = pd.DataFrame(self.timing)
        timing_df.to_csv(self.timing_filename)

        for miner in self.miners: #TODO change as necessary to allow this to be easily read in.
            out_loc = os.path.join(miner.subdir, self.chain_rep_file_suffix)
            miner.blockchain.tree.write_to_file(out_loc)
            dag_file_name = f"dag_{miner.id}.json"
            miner.blockchain.tree.write_to_file_json(os.path.join(self.miner_dag_dir, dag_file_name))

        graph_gen_main(self.miner_dag_dir, save_as=BASE_MINER_GRAPH_FILE, miner_id=0)
        graph_gen_main(self.miner_dag_dir, save_as=BASE_GLOBAL_GRAPH_FILE)


