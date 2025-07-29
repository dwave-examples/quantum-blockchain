import json
import logging
from datetime import datetime
import sys
from typing import Union

from src.node.proof_of_work.proof_of_work import ProofOfWork, BlockException
from src.node.new_block_validation.validation_result import ValidationResult
from src.common.block import Block, BlockHeader
from src.common.blockchain_memory import BlockchainMemory
from src.common.merkle_tree import get_merkle_root
from src.common.owner import Owner
from src.common.transaction import Transaction, TransactionOutput
from src.common.utils import calculate_hash
from src.common.values import BLOCK_REWARD, NUMBER_OF_LEADING_ZEROS
import src.quantum.quantum_cubic_utils as quantum_cubic_utils
from src.quantum.random_projection import RandomProjectionHasher
from src.quantum.protocols.proof_of_work_protocol import ProofOfWorkProtocol

import numpy as np

class ProofOfWorkQuantum(ProofOfWork):

    def __init__(self,
                 hostname,
                 mempool,
                 blockchain: BlockchainMemory,
                 proof_of_work_protocol: ProofOfWorkProtocol,
                 known_nodes_filepath: str=None,
                 submission_randomization_seed: Union[None, int, np.random.Generator]=None,
    ):
        super().__init__(hostname, mempool, known_nodes_filepath=known_nodes_filepath, blockchain=blockchain)
        self.proof_of_work_protocol = proof_of_work_protocol
        self.available_solvers = list(quantum_cubic_utils.get_GA_solver_energy_scales().keys())
        self.submission_randomization_prng = np.random.default_rng(submission_randomization_seed)
    
    #Why does this need to exist? BlockHeader class already has a calculate_hash function.
    def get_block_header_hash(self, nonce: int, block_header: BlockHeader) -> str:
        """Gets the block header hash for the given block_header, if the original
        nonce is replaced by the input nonce. This is used to generate a 
        random seed for the is_valid_nonce() function

        Args:
            nonce (int): The nonce to use for the block header hash
            block_header (BlockHeader): The block header to use for the block header hash

        Returns:
            str: The block header hash for the given block_header and nonce
        """
        block_header_content = {
            "previous_block_hash": block_header.previous_block_hash,
            "merkle_root": block_header.merkle_root,
            "timestamp": block_header.timestamp,
            "noonce": nonce
        }
        block_header_hash = calculate_hash(json.dumps(block_header_content))
        return block_header_hash
    

    def is_valid_nonce(self, nonce: int, block_header: BlockHeader, allowable_err: int=0) -> ValidationResult:
        """Checks to see whether the input nonce is valid for the given block_header, within
        the tolerance provided by allowable_err. This is done by generating a random seed
        from the block header hash, running the annealer with parameters generated with this
        random seed, and checking the number of leading zeros in the output. If the first
        NUMBER_OF_LEADING_ZEROS bits (less the allowable_err) of the output are all 0s,
        then the nonce is valid. Otherwise, it is not.

        Args:
            nonce (int): The nonce to check
            block_header (BlockHeader): The block header to use for the block header hash
            allowable_err (int, optional): The allowable error in the number of leading zeros.
                Defaults to 0.

        Returns:
            bool: _description_
        """
        block_header_hash = self.get_block_header_hash(nonce, block_header)
        random_seed = int(block_header_hash, 16)  #TODO Specific to protocol, don't make a block property
        h, J = quantum_cubic_utils.default_ising_model(self.proof_of_work_protocol.model_size, random_seed,
            ensemble=self.proof_of_work_protocol.ensemble)
        use_qpu = (self.proof_of_work_protocol.solver_type == 'QPU')

        if self.proof_of_work_protocol.randomize_solver:
            solver, qpu = self.proof_of_work_protocol.get_random_solver()
        else:
            solver = self.proof_of_work_protocol.solver
            qpu = self.proof_of_work_protocol.qpu
        sampler, sampler_kwargs = quantum_cubic_utils.generate_default_sampler(
            J,
            use_qpu=use_qpu,
            solver=solver,
            randomize_embedding=self.proof_of_work_protocol.randomize_embedding,
            embedding_directory=self.proof_of_work_protocol.embedding_directory,
            annealing_time=self.proof_of_work_protocol.annealing_time,
            qpu=qpu,
            use_pynauty=(self.proof_of_work_protocol.ensemble == 'DimBiClique')
        )
        sampler_kwargs['J'] = J
        sampler_kwargs['h'] = h
        #TODO parameterize this randomization
        if use_qpu:
            pass
        else:
            sampler_seed = datetime.now().microsecond
            sampler_kwargs['seed'] = sampler_seed
        sampler_output = sampler.sample_ising(**sampler_kwargs)

        stats = quantum_cubic_utils.build_stats(sampler_output, J.keys())
        problem_id = sampler_output._info['problem_id']
 
        del sampler_output
        del sampler
        hv = RandomProjectionHasher(
            random_seed=random_seed + 1,
            input_dimension=stats.size, nbits=64)
        vector_output, dot_vector = hv.hash_vector(stats.reshape(-1))

        valid = False

        if (vector_output[:NUMBER_OF_LEADING_ZEROS] == 1).sum() <= allowable_err:
            valid = True

        response = ValidationResult(valid, vector_output, stats, dot_vector, solver=solver, chip_id=self.proof_of_work_protocol.chip_id,
            problem_id=problem_id)
        return response

    def get_noonce(self, block_header: BlockHeader) -> int:
        logging.info("Trying to find noonce")
        noonce = block_header.noonce
        starting_zeros = "".join([str(0) for _ in range(NUMBER_OF_LEADING_ZEROS)])
        block_header_hash = ''
        while not block_header_hash.startswith(starting_zeros):
            logging.info("Mining attempt number: ", noonce)
            noonce = noonce + 1
            success, vector, stats, dot_vector = self.is_valid_nonce(noonce, block_header)
            if success:
                break
        logging.info("Found the noonce!")
        return noonce

    def prep_new_block(self, owner: Owner):
        """Prepares a new block by getting all transactions from the mempool
        and adding them to the block header.

        Args:
            owner: the Owner object associated with the miner that is mining the block

        Raises:
            BlockException: If there are no transactions in the mempool,
                a BlockException is raised.
        """
        logging.info("Creating new block")
        transactions = self.mempool.get_transactions_from_memory()
        if transactions:
            transaction_fees = self.get_transaction_fees(transactions)
            coinbase_transaction = self.create_miner_reward(transaction_fees, owner)
            transactions.append(coinbase_transaction)
            block_header = BlockHeader(
                merkle_root=get_merkle_root(transactions), #TODO this will need to change eventually
                previous_block_hash=self.blockchain.get_strongest_block().hash, #Leaving a note for something that will likely want to be changed eventually.
                timestamp=datetime.timestamp(datetime.now()),
                noonce=0
            )
        else:
            raise BlockException("", "No transaction in mem_pool")
        self.tentative_block_header = block_header
        self.tentative_transactions = transactions

    def test_noonce(self, nonce: int) -> bool:
        valid, vector = self.is_valid_nonce(nonce, self.tentative_block_header, allowable_err=0)
        self.validation_vector = vector
        return valid

    #Is this function deprecated? It's almost completely redundant with prep_new_block.
    def create_new_block(self, owner: Owner):
        logging.info("Creating new block")
        transactions = self.mempool.get_transactions_from_memory()
        if transactions:
            transaction_fees = self.get_transaction_fees(transactions)
            coinbase_transaction = self.create_miner_reward(transaction_fees, owner)
            transactions.append(coinbase_transaction)
            block_header = BlockHeader(
                merkle_root=get_merkle_root(transactions),
                previous_block_hash=self.blockchain.get_strongest_block().hash,
                timestamp=datetime.timestamp(datetime.now()),
                noonce=0
            )
            block_header.noonce = self.get_noonce(block_header)
            block_header.hash = block_header.get_hash()
            self.new_block = Block(transactions=transactions, block_header=block_header)
        else:
            raise BlockException("", "No transaction in mem_pool")
