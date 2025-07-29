import logging
import requests

from src.common.block import Block
from src.common.mem_pool import MemPool
from src.common.io_known_nodes import KnownNodesMemory
from src.common.blockchain_memory import BlockchainMemory
from src.common.values import NUMBER_OF_LEADING_ZEROS, BLOCK_REWARD, ALLOWABLE_VALIDATION_ERROR
from src.node.new_block_validation.validation_result import ValidationResult
from src.node.transaction_validation.transaction_validation import TransactionValidation
from src.node.proof_of_work.proof_of_work_quantum import ProofOfWorkQuantum
from src.quantum.protocols.proof_of_work_protocol import ProofOfWorkProtocol

class NewBlockException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class NewBlock:
    def __init__(self, blockchain: BlockchainMemory,  hostname: str, known_nodes_filepath: str=None, 
            blockchain_filepath: str=None, mempool_filepath: str=None):
        self.blockchain = blockchain
        self.new_block = None
        self.sender = ""
        self.known_nodes_filepath = known_nodes_filepath
        self.blockchain_filepath = blockchain_filepath
        self.mempool_filepath = mempool_filepath
        self.mempool = MemPool(mempool_filepath)
        self.known_nodes_memory = KnownNodesMemory(known_nodes_filepath)
        self.hostname = hostname

    def receive(self, new_block: Block, sender: str):
        self.new_block = new_block
        self.sender = sender
        try:
            assert self.new_block.previous_block_hash in self.blockchain.blocks
        except AssertionError:
            raise NewBlockException("", "Previous block provided is not found in the chain")

    def validate(self, is_quantum: bool=False, validate_transactions: bool=True, **validate_kwargs) -> bool:
        if is_quantum:
            validation_result = self._validate_hash_quantum(**validate_kwargs)
        else:
            validation_result = self._validate_hash()
        if validate_transactions:
            self._validate_transactions()
        return validation_result

    def _validate_hash_quantum(self, proof_of_work_protocol: ProofOfWorkProtocol) -> bool:
        pow_ = ProofOfWorkQuantum(self.hostname, self.mempool, known_nodes_filepath=self.known_nodes_filepath,
                                 blockchain=self.blockchain, proof_of_work_protocol=proof_of_work_protocol)
        validation_result = pow_.is_valid_nonce(self.new_block.block_header.noonce, self.new_block.block_header,
                           allowable_err=ALLOWABLE_VALIDATION_ERROR)
        self.validation_vector = validation_result.vector
        return validation_result


    def _validate_hash(self) -> bool:
        new_block_hash = self.new_block.hash
        number_of_zeros_string = "".join([str(0) for _ in range(NUMBER_OF_LEADING_ZEROS)])
        try:
            assert new_block_hash.startswith(number_of_zeros_string)
            valid = True
        except AssertionError:
            valid = False
        validation_result = ValidationResult(valid)
        return validation_result

    def _validate_transactions(self):
        input_amount = 0
        output_amount = 0
        for transaction in self.new_block.transactions:
            transaction_validation = TransactionValidation(self.blockchain, self.hostname, self.mempool,
                                                              self.known_nodes_memory)
            transaction_validation.receive(transaction=transaction)
            transaction_validation.validate()
            input_amount = input_amount + transaction_validation.get_total_amount_in_inputs()
            output_amount = output_amount + transaction_validation.get_total_amount_in_outputs()
        self._validate_funds(input_amount, output_amount)

    @staticmethod
    def _validate_funds(input_amount: float, output_amount: float):
        assert input_amount + BLOCK_REWARD == output_amount

    def add(self): #TODO Figure out when/if this is used and remove it if it's superfluous.
        self.blockchain.add_block(self.new_block)
        self.blockchain.store_block_in_file(self.new_block)

    #Functionality moved to miner. Miners should manage their own chains and mempools!
    #def clear_block_transactions_from_mempool(self):
        #current_transactions = self.mempool.get_transactions_from_memory()
        #transactions_cleared = [i for i in current_transactions if not (i in self.new_block.transactions)]
        #self.mempool.store_transactions_in_memory(transactions_cleared)

    def broadcast(self):
        logging.info(f"Broadcasting block")
        node_list = self.known_nodes_memory.known_nodes
        for node in node_list:
            if node.hostname != self.hostname and node.hostname != self.sender:
                block_content = {
                    "block": {
                        "header": self.new_block.block_header.to_dict,
                        "transactions": self.new_block.transactions
                    },
                    "sender": self.hostname
                }
                try:
                    logging.info(f"Broadcasting to {node.hostname}")
                    node.send_new_block(block_content)
                except requests.exceptions.HTTPError as error:
                    logging.info(f"Failed to broadcast block to {node.hostname}: {error}")
