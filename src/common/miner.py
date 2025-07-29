import json
import os
import copy

import numpy as np
import pandas as pd

from scipy.special import erf

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from src.common.utils import calculate_hash
from src.common.values import BLOCK_REWARD
from src.common.blockchain_memory import BlockchainMemory
from src.common.mem_pool import MemPool
from src.node.proof_of_work.proof_of_work_quantum import ProofOfWorkQuantum
from src.node.new_block_validation.new_block_validation import NewBlock, NewBlockException
from src.node.new_block_validation.validation_result import ValidationResult
from src.node.transaction_validation.script import Stack, StackScript
from src.common.block import Block, BlockHeader
from src.common.values import NUMBER_OF_LEADING_ZEROS, BLOCKCHAIN_FILE, MEMPOOL_FILE, MINER_DATA_FILE
from src.common.initialize_default_blockchain import initialize_blockchain
from src.common.owner import Owner
from src.common.miner_params import MinerParams
from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu



#TODO: either make these class methods or create a separate file for scoring functions.
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
def miner_func_basic(pending_result: ValidationResult, verification_result: ValidationResult,
    additional_validation: int=0, **kwargs) -> float:
    """A simple function to calculate the miner's score based on the pending and verification results

    Args:
        pending_resufrom Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA
        from Crypto.Signature import pkcs1_15

        (ValidationResult): The pending result of the miner
        verification_result (ValidationResult): The verification result of the miner
        additional_validation (int, optional): The additional validation to use (beyond the 
            NUMBER_OF_LEADING_ZEROS). Defaults to 0.
    Returns:
        float: The score of the miner
    """
    num_failures = int(np.sum([verification_result.vector != pending_result.vector][:NUMBER_OF_LEADING_ZEROS + additional_validation]))
    score = int(1-2*(num_failures!=0))

    return score

def miner_func_confidence_based(pending_result: ValidationResult, verification_result: ValidationResult,
    additional_validation: int=0, **kwargs) -> float:
    """A function to calculate the miner's score based on the pending and verification results
    
    Args:
        pending_result (ValidationResult): The pending result of the miner
        verification_result (ValidationResult): The verification result of the miner
        additional_validation (int, optional): The additional validation to use (beyond the 
            NUMBER_OF_LEADING_ZEROS). Defaults to 0.
    Returns:
        float: The score of the miner
    """

    Walpha = verification_result.dot_vector
    dWalpha = 0.18 #TODO: parameterize this
    W0alpha = 0 #TODO: parameterize this
    thresholds = None #TODO: parameterize this
    d_alpha = (
        (Walpha.ravel() - W0alpha) / dWalpha / np.sqrt(2)
    )  # Normalized distrance from threshold
    # Naive implementation:
  
    if thresholds is None:
        thresholds = d_alpha  # confidence in most probable sequence.
    thresholds = np.sign(thresholds.ravel())  # In case given d_alpha form.
    P_alpha = 0.5 * (1 + thresholds * erf(d_alpha))
    if np.any(P_alpha == 0):
        score = -float("inf")
    else:
        score = np.sum(np.log2(P_alpha))

    return score


class Miner:

    """ Intended Usage: this class is intended to encapsulate all necessary functions for running a miner
        on the blockchain network. Current ownership status is a bit of a mess, should consolidate some other
        classes and give more of their functions to this class.

    Ownership:
    self.blockchain: a BlockchainMemory object holding/tracking the state of the miner's blockchain.
    self.mempool: a MemPool object holding exclusive copies of proposed transactions for the miner to use
                  to build blocks. Miner maintains it to ensure no transaction duplication.
    self.pow: a ProofOfWorkQuantum object (currently) which is used to run proof of work checks for mining.
             This is one of the places where ownership/responsibility should be better delineated: fix soon!"""
    

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(self, subdir: str):
        """Instantiates a new miner at the given hostname. The subdir is the
        directory to store the mempool, known nodes, and blockchain. 

        Currently set up to initialize entirely from files: as such, the only
        argument this function takes is the name of the subdirectory in which
        the files should be found (and where new output will be written) 
        If any of the necessary files aren't present or are incorrectly formatted, 
        initialization will fail. The file names are locked to defaults found in
        common.values

        Args:
            subdir (str): name of subdirectory with initialization files and where
            file outputs will be written.

        Input Files:
            MINER_FILE: stores static parameters, which are currently
            id, allowable_err and scoring_function.

            BLOCKCHAIN_FILE: stores the blocks in the miner's blockchain,
            along with their scores. At initialization, this should be storing
            at minimum one Block object, formatted as a json dict.

            POW_QPU_FILE: stores initialization parameters for the miner's
            proof_of_work_protocol_qpu object. Should be automatically 
            formatted as a json dict by that class.

            MEMPOOL_FILE (optional): stores the miner's mempool. This should
            start empty for a freshly-created miner, so it's not required to exist.
            If a file does exist, the miner will read the contents into its 
            self.mempool object.

        """
        self.subdir = subdir

        #TODO make this actually useful
        if not os.path.exists(os.path.join(subdir, 'known_nodes')):
            open(os.path.join(subdir, 'known_nodes'), 'w').close()

        miner_params = MinerParams.from_file(subdir)

        if miner_params:
            self.id = miner_params.id
            self.allowable_err = miner_params.allowable_err
            self.scoring_function = miner_params.scoring_function
            self.private_key = miner_params.private_key #TODO consider whether this should create 
                                                        #a key if none is found in file 
        else:
            raise Exception("No Valid Parameter File was Found!")


        self.owner = Owner(self.private_key)
        self.blockchain = BlockchainMemory(subdir)
        self.blockchain.get_blockchain_from_memory()

        self.mempool = MemPool(subdir)
        if os.path.exists(self.mempool_filepath):
            self.mempool.get_transactions_from_file()
            
        self.hostname  = 'localhost:{}'.format(5000 + int(self.id))

        self.pow = ProofOfWorkQuantum(hostname=self.hostname, mempool=self.mempool,
            known_nodes_filepath=self.known_nodes_filepath, blockchain=self.blockchain,
            proof_of_work_protocol=ProofOfWorkProtocolQpu.from_json(subdir))


    @property
    def mempool_filepath(self):
        return os.path.join(self.subdir, MEMPOOL_FILE)

    @property
    def known_nodes_filepath(self):
        return os.path.join(self.subdir, 'known_nodes')

    @property
    def blockchain_filepath(self):
        return os.path.join(self.subdir, BLOCKCHAIN_FILE)

    
    def __str__(self) -> str:
        val = f"Miner {self.id} at {self.hostname}\n"
        val += f"Blockchain beliefs: {str(self.blockchain.tree)}\n"
        return val



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Blockchain Management                                         |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



    #Passes through to self.blockchain. Only really useful for brevity.
    def get_block(self, block_hash):
        return self.blockchain.get_block(block_hash)

    def is_good_block(self, block_score) -> bool:
        """ Determines whether a block is valid based on its score so methods don't
            have to pass around cumbersome validation vectors or bools along with the score. 
            This is mostly future proofing for alternate scoring functions: it works with
            our simple default or any other scoring function that associates a postive (negative)
            score with positive (negative) chainwork. If we ever break that assumption, we'll
            need to update several functions including this one.

            Args:
                block_score: the score of a block
            Returns:
                bool representing whether the block is valid or not
            """

        if block_score > 0: #Accept any block with positive score. They're good blocks, Brent.
            return True
        else:
            return False

    def add_block_to_chain(self, block: Block, block_score) -> list[tuple[str,float]]:
        """ Adds a block to the blockchain memory stored in self.blockchain, which also 
            adds its info to the score tree. Updates blockchain beliefs based on the logic of
            the update_blockchain_beleifs function. Writes the block data and its score to file. 

            Args:
                block (Block): a block
                block_score (int or float): score assigned to the block

            Returns:
                belief_changes: list of tuples. Format is (block_hash, update) where the hash belongs
                a block that has moved on or off the miner's trunk as a result of this addition. The
                update is either a 1 (if the block moved to the trunk) or a -1 (if it moved off),
                which will be aggregated over all miners to count how many consider that block canonical

            Modifies:
                self.blockchain: the miner's blockchain
                self.mempool: the miners mempool
            """
        blocks_promoted = []
        transactions_promoted = set()
        blocks_demoted = []
        transactions_demoted = set()

        self.blockchain.add_block(block, block_score, canonical = self.is_good_block(block_score))
        self.blockchain.store_block_in_file(block)

        if self.blockchain.tree.is_in_trunk(block.hash):
            blocks_promoted.append(block)
        elif self.is_good_block(block_score): #Only need to update on blocks that are good and not already in trunk
            blocks_promoted, blocks_demoted = self.update_blockchain_beliefs()

        for block in blocks_promoted: #All txns in block except coinbase
            transactions_promoted.update([t.transaction_hash for t in block.transactions if t.inputs])

        if blocks_demoted: #If we're both promoting and demoting, change only txns not in both sets
            for block in blocks_demoted: #All txns in block except coinbase
                transactions_demoted.update([t.transaction_hash for t in block.transactions if t.inputs])
            transactions_in_common = transactions_promoted & transactions_demoted
            transactions_promoted -= transactions_in_common
            transactions_demoted -= transactions_in_common
            self.mempool.store_transactions_in_memory(list(transactions_demoted))

        self.mempool.remove_transactions_from_memory(list(transactions_promoted))
        self.mempool.store_pool_in_file() #Once updates are done, store current state of mempool

        promoted_scores = [(block.hash, 1) for block in blocks_promoted]
        demoted_scores = [(block.hash, -1) for block in blocks_demoted]
        return  promoted_scores + demoted_scores #TODO encapsulate return type into its own class for clarity and easy transmission.

    def update_blockchain_beliefs(self) -> tuple[list[Block],list[Block]]:
        """ Updates the blockchain tree so that the branch containing the highest scoring block is now the trunk. 
            Updates the mempool to reflect the change: transactions from blocks that are being moved off the trunk
            are returned to the mempool, transactions from blocks being moved onto the trunk are removed (often this will
            likely add and then remove many of the same transactions, which is fine). When with function is called and
            how it should work may need to change when miner behavior is allowed to be more flexible (i.e. different
            scoring functions or chain management policies).
        
        Modifies:
           self.blockchain.tree: the representation of the miner's chain structure 

        Returns:
            promoted_blocks: list of block objects newly promoted to the trunk
            demoted blocks: list of block objects newly demoted from the trunk to a branch
        """

        #TODO implement better naming/data encapsulation for BlockScoreTree so this code becomes clearer.
        if self.blockchain.tree.high_score != self.blockchain.tree.trunk[-1][3]:
            best_branch = self.blockchain.tree.get_branch(self.blockchain.tree.strongest_block_hash)
            if best_branch == self.blockchain.tree.trunk: #Corner case: branch tip is tied with trunk tip, but strongest hash points to branch
                self.blockchain.tree.strongest_block_hash = self.blockchain.tree.trunk[-1][0] #Update hash but don't change tree
                return [],[]

            #Return all transactions from blocks no longer considered canonical
            join_block_idx = self.blockchain.tree.get_trunk_join_index(best_branch)
            demoted_block_hashes = [blk[0] for blk in  self.blockchain.tree.trunk[join_block_idx+1:]]
            demoted_blocks = [self.blockchain.blocks[idx] for idx in demoted_block_hashes]
            
            #Remove all transactions from blocks being promoted
            promoted_block_hashes = self.blockchain.tree.promote_to_trunk(best_branch)
            promoted_blocks = [self.blockchain.blocks[idx] for idx in promoted_block_hashes]

            return promoted_blocks, demoted_blocks
        else:
            return [],[] #If no changes to tree structure, nothing to return

    def get_strongest_block(self) -> Block:
        """Returns the strongest block in the miner's blockchain beliefs

        Returns:
            Block: The strongest block in the miner's blockchain beliefs
        """
        return self.blockchain.get_block(self.blockchain.tree.strongest_block_hash)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Mining and Validation                                         |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    #Ideally some functionality should be moved from PoW to Miner. This will need to be changed if that happens.
    #Will also likely need restructuring when mining is simultaneous (distributed) not sequential.
    def attempt_mine(self) -> ValidationResult:
        """Attempts to mine a new block by choosing a random nonce and checking if it is valid.

        Returns:
            ValidationResult: The result of the mining attempt, including whether it was successful,
                the success vector, statistics, and the dot vector.
        """
        noonce = np.random.randint(0, 2**32)
        validation_result = self.pow.is_valid_nonce(noonce, self.pow.tentative_block_header,
                                                     allowable_err=self.allowable_err)
        if validation_result.valid:
            block_header = self.pow.tentative_block_header
            block_header.noonce = noonce
            block_header.hash = block_header.get_hash()
            transactions = self.pow.tentative_transactions
            self.pow.new_block = Block(transactions=transactions, block_header=block_header)
            self.record_block_data(self.pow.new_block, validation_result, True, 0)
        return validation_result

    def validate_new_block(self, new_block, sender, 
        validation_result: ValidationResult, additional_validation: int=0) -> tuple[ValidationResult, int]:
        """Note that additional validation tests whether the first x bits are the same as
        the validation vector. This is for testing purposes to simulate longer blocks
        without having to spend extra time mining towards the additional validation
        """

        new_hash = new_block.hash        
        prev_hash = new_block.previous_block_hash

        tentative_new_block = NewBlock(blockchain=self.blockchain, hostname=self.hostname,
            known_nodes_filepath=self.known_nodes_filepath, mempool_filepath=self.mempool_filepath,
            blockchain_filepath=self.blockchain_filepath)
        tentative_new_block.receive(new_block, sender=sender) #Check for sender info
 
        tentative_result = tentative_new_block.validate(is_quantum=True, proof_of_work_protocol=self.pow.proof_of_work_protocol,
            validate_transactions=False) #Disabling transaction validation in this step entirely for now. See below
        valid = tentative_result.valid #check behavior

        #For now, only validate transactions for blocks that will become part of the main chain
        if valid and self.blockchain.tree.is_in_trunk(new_block.previous_block_hash):
            valid = self.validate_transactions(new_block)

        num_failures = 0
        if not valid:
            if validation_result.vector is not None:
                num_failures = np.sum(tentative_new_block.validation_vector[:NUMBER_OF_LEADING_ZEROS + additional_validation] != validation_result.vector[:NUMBER_OF_LEADING_ZEROS + additional_validation])
            else:
                raise ValueError("No validation vector provided")
        else:
            num_failures = np.sum(tentative_new_block.validation_vector[:NUMBER_OF_LEADING_ZEROS + additional_validation] != validation_result.vector[:NUMBER_OF_LEADING_ZEROS + additional_validation])
            valid = valid and num_failures == 0 

        self.record_block_data(new_block, tentative_result, False, num_failures)
        
        return tentative_result, num_failures

    def validate_transactions(self, new_block):        
        """ Transaction validation functionality replicated here because original
            implementation isn't portable enough to use how it needs to be used here.

            This port is a stupid hack but it works for now. Plan to refactor to make this
            unnecessary, so not worth doing better."""        
        block_reward = 0
        valid = True
        transaction_fees = 0
        coinbase_amount = 0
        for transaction in new_block.transactions:
            transaction_data = copy.deepcopy(transaction.transaction_data)
            if "transaction_hash" in transaction_data:
                transaction_data.pop("transaction_hash")
            stk = StackScript(transaction_data)
            output_amount = sum([output.amount for output in transaction.outputs])
            input_amount = 0

            for inpt in transaction.inputs:
                coinbase = False
                output = self.blockchain.get_transaction(inpt.transaction_hash).outputs[inpt.output_index]

                #We can skip some cumbersome code by assuming our scripts are always regular. Worth
                #doing more thoroughly later.
                sig, pub_key = inpt.unlocking_script.split(" ")
                pub_key_hash = output.locking_script.split(" ")[2]
                l_script_hash = calculate_hash(calculate_hash(pub_key), hash_function="ripemd160")
                if pub_key_hash == l_script_hash:
                    try:
                        stk.push(sig)
                        stk.push(pub_key)
                        stk.op_checksig()
                        input_amount += output.amount
                    except:
                        print("Checksig Failed for Index ", inpt.output_index)
                        valid = False
                else:
                    print(pub_key_hash, "-----", l_script_hash)
                    valid = False  #if any locking script fails, overall validation fails.

            remainder = input_amount - output_amount

            if remainder < 0:
                if input_amount == 0: #Only coinbase transactions should have no input
                    coinbase_amount = output_amount
                else: #Otherwise it's an overspend
                    print("Cost Overrun, Missing ", output_amount - input_amount)
                    valid = False
            elif remainder > 0:
                transaction_fees += remainder

        if coinbase_amount > transaction_fees + BLOCK_REWARD:
            valid = False
            print("Miner is counterfeiting ", coinbase_amount - transaction_fees - BLOCK_REWARD)
            

        return valid
    

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Trial Data Collection                                         |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def record_block_data(self, block: Block, result: ValidationResult, mined: bool, num_failures: int):
        """ Records trial data for this miner. Should be called every time the miner either validates or mines a block. 
            Thus it should record one line per block in the chain (other than the genesis block). 
            Known Bug: If a trial is interrupted and restarted, it will sometimes generate a spurious entry, which 
            corresponds to a block that some miners had seen and recorded and other miners had not (and thus was 
            discarded during the interruption). This is easy to identify, as it is the only circumstance where two 
            blocks in a row will have the same block number. The  behavior is not worth eliminating as it occurs 
            rarely right now, and will stop being an issue entirely when miners are run in distributed fashion rather than locally.
            #TODO veryify this behavior is fixed in distributed implementation, and remove above if it is.
            
            Args:
                block (Block): the block whosedetails are to be recorded
                result (ValidationResult): the ValidationResult object associated with the block.
                mined (book): indicates whether this miner mined the block
                num_failures (int): the number of validation failures.

            Output:
                Appends to the miner's data file, stored in the miner's subdirectory and named according to 
                the convention defined by the MINER_DATA_FILE constant in the common.values file. """

        output_dict = {}
        block_num = len(self.blockchain.blocks.keys())
        output_dict.update({'Block Number' :[block_num]})
        output_dict.update({"Block Hash" : block.hash})
        if mined:
            output_dict.update({'Validation': 'miner'})
        elif result.valid:
            output_dict.update({'Validation': 'pass'})
        else:
            output_dict.update({'Validation': 'fail'})
        output_dict.update({'Chip ID': result.chip_id})
        output_dict.update({'Problem ID': result.problem_id})
        output_dict.update({'Strongest Block Hash': self.get_strongest_block().hash})
        output_dict.update({'Chain Length': len(self.blockchain.tree.trunk)})

        header = bool(block_num <= 1)
    
        output_df = pd.DataFrame.from_dict(output_dict).set_index('Block Number')
        output_df.to_csv(os.path.join(self.subdir, MINER_DATA_FILE), mode='a', header = header)
        