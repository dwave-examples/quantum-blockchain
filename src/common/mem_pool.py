import json
import logging
import os
import copy

from src.common.transaction import Transaction
from src.common.values import MEMPOOL_FILE

#TODO once transaction and genesis code is in a better state, make a pass to strictly enforce typing.
#Nothing should ever go in the mempool that isn't a Transaction: trying to pass an inapropriate type should throw an exception.
class MemPool:
    """
    This class is responsible for managing the memory pool of transactions. 
    These transactions are stored in memory until they are added to a block.
    
    Update: the "mem" in "mempool" now actually means memory. Not sure why a set of temporary
    objects were being constantly read to and written from files.
    """
    def __init__(self, directory: str):
        self.directory =  directory
        self.mem_pool_dict = {} 

    def get_transactions_from_memory(self) -> list:
        """Gets a list of all transactions in memory

        Returns:
            list: a deep copy of the dict of transactions in memory
        """
        logging.info("Getting transaction from memory")
        transaction_list = [copy.deepcopy(x) for x in self.mem_pool_dict.values()]
        return transaction_list


    def store_transactions_in_memory(self, transactions: list[Transaction]):
        """Stores a list of transactions in memory

        Args:
            transactions (list): A list of transactions to store in
                memory
        """
        logging.info("Storing transaction in memory") 
        if (len(transactions) > 0) and (type(transactions[0]) == Transaction):
            self.mem_pool_dict.update({transaction.transaction_hash:copy.deepcopy(transaction) for transaction in transactions})

    def remove_transactions_from_memory(self, transactions: list):
        if transactions:
            if type(transactions[0]) == str: #TODO clean up the rest of the code base sufficiently that it's practical to enforce strict typing
                t_hashes = transactions #TODO clean this up
            else:
                t_hashes = [txn.transaction_hash for txn in copy.deepcopy(transactions)] #Not 100% sure copy in necessary. Depends on details of how Python handle attributes
            for t_hash in t_hashes:
                if t_hash in self.mem_pool_dict:
                    self.mem_pool_dict.pop(t_hash)
    

    def store_pool_in_file(self, filename: str = None):
        """Stores all current transactions in file. Defaults to storing transactions in
           the MemPool object's working directory. Only pass in another filename if you want
           to save a copy elsewhere for some reason.
        """
        logging.info("Storing transaction in memory")
        if not filename:
            filename = os.path.join(self.directory, MEMPOOL_FILE)
        text = json.dumps([txn.transaction_data for txn in self.mem_pool_dict.values()]).encode("utf-8")
        with open(filename, "wb") as file_obj:
            file_obj.write(text)

    
    def get_transactions_from_file(self, filename = None) -> list:
        """Gets a list of all transactions in memory

        Returns:
            list: A list of all transactions in memory
        """
        logging.info("Getting transaction from memory")
        if not filename:
            filename = os.path.join(self.directory, MEMPOOL_FILE)
        with open(filename, "rb") as file_obj:
            mem_pool_str = file_obj.read()
            transactions = []
            if len(mem_pool_str):
                mem_pool_dict_list = json.loads(mem_pool_str)
                for item in mem_pool_dict_list:
                    txn = Transaction(inputs=item['inputs'],outputs=item['outputs'])
                    transactions.append(txn)
        return transactions  

