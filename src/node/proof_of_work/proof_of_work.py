from abc import ABC, abstractmethod
import logging

import requests

from src.common.blockchain_memory import BlockchainMemory
from src.common.mem_pool import MemPool
from src.common.io_known_nodes import KnownNodesMemory
from src.common.block import Block
from src.common.owner import Owner
from src.common.values import BLOCK_REWARD
from src.common.transaction import Transaction, TransactionOutput


class BlockException(Exception):
    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class ProofOfWork (ABC):
    def __init__(self, hostname: str, mempool: MemPool=None, blockchain: BlockchainMemory=None, known_nodes_filepath: str=None):
        self.known_nodes_memory = KnownNodesMemory(known_nodes_filepath)
        self.hostname = hostname
        if mempool is None:
            self.mempool = MemPool()
        else:
            self.mempool = mempool
        self.blockchain = blockchain
        self.new_block = None


    @abstractmethod
    def create_new_block(self):
        """This method creates a new block with the transactions in the mempool
        and saves the new block in the new_block attribute

        Raises:
            BlockException: If there are no transactions in the mempool
        """
        pass

    def get_transaction_fees(self, transactions: list[Transaction]) -> float:
        """Gets the total transaction fees from the input list of 
        transactions. 

        Args:
            transactions (list[dict]): A list of the transaction data to
                calculate the fees from

        Returns:
            float: The total transaction fees from the input transactions
        """
        transaction_fees = 0.
        for transaction in transactions:
            input_amount = 0
            output_amount = 0
            for transaction_input in transaction.inputs:
                output_txn = self.blockchain.get_transaction(transaction_input.transaction_hash)
                if output_txn:
                    utxo_amount = output_txn.outputs[transaction_input.output_index].amount
                    input_amount += utxo_amount
            for transaction_output in transaction.outputs:
                output_amount += transaction_output.amount
            transaction_fees += (input_amount - output_amount)
        return transaction_fees


    def broadcast(self) -> bool:
        """Broadcasts the new block to all known nodes

        Returns:
            bool: True if the block was broadcasted to at least one node, 
                False otherwise
        """
        logging.info("Broadcasting to other nodes")
        node_list = self.known_nodes_memory.known_nodes
        broadcasted_node = False
        for node in node_list:
            if node.hostname != self.hostname:
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
                    broadcasted_node = True
                except requests.exceptions.ConnectionError as e:
                    logging.info(f"Failed broadcasting to {node.hostname}: {e}")
                except requests.exceptions.HTTPError as e:
                    logging.info(f"Failed broadcasting to {node.hostname}: {e}")
        return broadcasted_node


    #TODO Seems to be the same functionality as get_coinbase_transaction. Check later and consolidate
    @staticmethod
    def create_miner_reward(transaction_fees: float, owner: Owner) -> Transaction:
        """This function creates a miner reward transaction. The transaction
        contains the transaction fees and the block reward. The block reward is
        "new money", meaning it did not previously exist in the system. Thus, 
        there is no transction input.

        Args:
            transaction_fees (float): The amount of transaction fees to be 
                added to the miner reward #TODO: ultimately, the transaction
                fees should be taken from the transactees, not created
                out of thin air

        Returns:
            dict: The transaction data for the miner reward transaction
        """
        transaction_output = TransactionOutput(
            amount=transaction_fees + BLOCK_REWARD,
            public_key_hash=owner.public_key_hash
        )
        transaction = Transaction(inputs=[], outputs=[transaction_output])
        return transaction
