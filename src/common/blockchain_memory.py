import json
import logging
import os

from src.common.block import Block, BlockHeader
from src.common.block_score_tree import BlockScoreTree
from src.common.transaction import Transaction, TransactionInput, TransactionOutput
from src.common.values import BLOCKCHAIN_FILE

class BlockchainMemory:


    """ Intended Usage: this class is intended to store and maintain all the information for a complete blockchain for
            a node in the network, including soft forks and all blocks in them. It's particularly designed to help track
            chainstates with multiple forks, and consistently maintain one of them as the canonical chain: i.e. the
            chain whose blocks and transactions are considered valid.

           Ownership:
             self.tree: ScoredBlockchain object. Tracks the location, contents and strength of all forks
                    in the chain, and rearranges them as necessary
            self.blocks: dictionary. Syntax is {block_hash: Block}. Holds references to all Block objects currently
                    in the blockchain. (Note that blocks are NOT currently exclusive to one instance, being shared
                    by default by all instances on a given node.)
            self._transaction_block_lookup: dictionary. Syntax is {transaction_hash, [block_hash1, block_hash2, ....]} Allows
                    lookup of which blocks contain a given transaction. Should be considered
                    private/protected: only access through class methods. """

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def __init__(self, directory: str):


        self.directory = directory
        self.tree = BlockScoreTree()
        self.blocks = {}   
        self._transaction_block_lookup = {} #treat as private


#TODO write __str__ method and similar useful things

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Blockchain Management                                         |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def add_block(self, block: Block, score: float=1):

        """ Adds a block and associated score to the chain, including storing it in the self.blocks dict,
            adding a representation of it to the blockchain tree and adding its transactions to 
            self.transaction_block_lookup."""

        self.blocks.update({block.hash:block})
        self.tree.add_block(block.hash, block.previous_block_hash, score)
        #Consider moving up to miner.
        for txn in block.transactions: 
            if txn.transaction_hash in self._transaction_block_lookup:
                self._transaction_block_lookup[txn.transaction_hash].append(block.hash)
            else:
                self._transaction_block_lookup.update({txn.transaction_hash:[block.hash]})
            

    #Please use this instead of directly calling the blocks[] dict. It will make updating
    #function for memory management (planned for future) much easier.
    def get_block(self, block_hash):

        """ Takes a hash, returns the block object with that hash."""

        return self.blocks[block_hash]


    def remove_block(self, block_hash):
        """ Takes the hash of a block and removes both the block from memory and
            the representation of the block in the ScoredBlockchain tree. Will only
            remove the block if it's at the tip of a branch (otherwise the tree would
            have a hole in it). Doesn't remove representations that have been
            written to file, as the intended use is for moving blocks, not discarding them
            entirely. If discarding blocks becomes useful, consider adding optional arg
            to remove block from files as well.

            Args:
                block_hash: the hash of the block to be removed"""

        if block_hash not in self.blocks:
            print("Error, block not found!")
            return
        
        branch = self.tree.get_branch(block_hash)

        if branch[-1][0] != block_hash:
            print("Error, can only remove branch tips!")
            return

        self.tree.pop_block(branch)
        for txn in self.get_block(block_hash).transactions: 
            self._transaction_block_lookup[txn.transaction_hash].remove(block_hash)
        self.blocks.pop(block_hash)

    #TODO rename to get_strongest_block_hash find where this is used
    def get_strongest_block(self):
        return self.blocks[self.tree.strongest_block_hash]

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: File I/O                                                      |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def store_block_in_file(self, block: Block, score: float = None, file_name: str = None):
        """ For storing blocks in memory one at a time. Appends the block (including score) to the specified file.
            If these are going to be read back and used to build a blockchain, it's important that
            they be appended in order.

            Args:
                block: Block. A Block object. 
                score: score assigned to block. Used if you want to store with a custom score, or to write a block
                not yet added to the chain.
                file_name: (string, optional) File name if you want to store the block somewhere else besides the 
                default blockchain file. Intended for making copies: blocks should always be stored in main file.""" 
        

        if not score:
            score = self.tree.get_block(block.hash).block_score
        block_dict = block.to_dict
        block_dict.update({"score": score})
        text = json.dumps(block_dict) + '\n'
        if not file_name:
            file_name = os.path.join(self.directory, BLOCKCHAIN_FILE)
        with open(file_name, "a") as file_obj:
            file_obj.write(text)


    def get_blockchain_from_memory(self, mem_file: str = None):
        """ For reading a stored blockchain from a file. Will read in and add the blocks in
            the order they are written into the file. Missing or out-of-order blocks will cause
            this to fail.
            
            Args:
                mem_file (str): file path of a file to be read in. Defaults to using
                blockchain's home directory and default filename."""
        
        if mem_file:
            fname = mem_file
        else:
            fname = os.path.join(self.directory, BLOCKCHAIN_FILE)
        logging.info("Getting blockchain from memory")
        with open(fname, "r") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                block_dict = json.loads(line)
                block_dict["header"].pop("hash")
                header = BlockHeader(**block_dict["header"])
                transactions = []
                for t_dict in block_dict['transactions']:
                    inputs = [TransactionInput.from_dict(i) for i in t_dict['inputs']]
                    outputs = [TransactionOutput.from_dict(i) for i in t_dict['outputs']]
                    transactions.append(Transaction(inputs=inputs, outputs=outputs))
                block_obj = Block(transactions=transactions, block_header=header)
                block_obj.sign_with_merkle_root()
                score = block_dict["score"]
                self.add_block(block_obj, score)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Transaction Handling                                          |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_transaction_block_hashes(self, transaction_hash: str) -> [str]:
        """ Returns a list of hashes of all the blocks that contain a particular transaction.

            Currently just a helper function for get_transaction, but seems likely
            to be useful on its own at some point."""

        try:
            block_hash_list = self._transaction_block_lookup[transaction_hash]
        except:
            print("Transaction hash doesn't match any transaction!")
            return None
        
        return block_hash_list

    def get_transaction(self, transaction_hash: str) -> Transaction:
        """O(1) transaction getter. Note that a transaction on the blockchain
            may be associated with multiple blocks (in different branches) but is currently
            only stored in memory once. Even if that changes, every copy with the same hash
            will have the exact same data, so it doesn't matter which one you retreive unless
            you're planning to alter it (which you shouldn't be!)
  
            Args:
                transaction_hash: the hash of a transaction

            Returns:
                The transaction with the matching hash (if it exists). None otherwise."""

        block_hash_list = self.get_transaction_block_hashes(transaction_hash)
        
        if block_hash_list:
            block = self.get_block(block_hash_list[0])
            transaction = block.get_transaction(transaction_hash)
        else:
            transaction = None

        return transaction

    def get_user_utxos(self, user_key_hash: str, amt_requested = None):
        """ Gets unspent transactions for a user on the blockchain. Gets utxos
            belonging to the user up to the total amount request. Will return
            the user's whole balance if no amount is passed or if the user has less than
            what was requested.
            
            Args:
                public_key_hash: users public key hash, used to identify them.
                amt_requested: optional parameter. Can stop search early if user only requests
                a certain amount. If no argument is passed or the user has less funds than requested,
                it will return their entire balance.

            Returns:
                 total: the sum of the amounts of all utxos returned
                 utxos_info: list of dicts formatted {"utxo":TransactionOutput, "hash": str, "index": int} 
                 where "hash" and "index" are the hash of the parent transaction and the output_index of the utxo
                respectively. Would love to find a less awkward way to do this, but TransactionOutputs contain no 
                pointers to their parent transactions, so at least two of these three have to be passed back. """

        total = 0
        utxos_info = [] 
        
        #TODO: alter to allow searches along any one chain
        #IMPORTANT: only search transactions in trunk because those are the only transactions considered canonical.
        for item in reversed(self.tree.trunk): #Consider ways to improve on linear search
            block_hash = item[0]
            block = self.get_block(block_hash)
            for transaction in block.transactions:
                for idx, output in enumerate(transaction.outputs):
                    locking_script = output.locking_script
                    for element in locking_script.split(" "):
                        if not element.startswith("OP") and element == user_key_hash:
                            total += output.amount
                            utxo_dict = {"utxo":output, "hash":transaction.transaction_hash, "index":idx}
                            utxos_info.append(utxo_dict)
                            if amt_requested:
                                if total >= amt_requested:
                                    break
        
        return total, utxos_info

    def get_locking_script_from_utxo(self, utxo_hash: str, utxo_index: int):
        transaction_data = self.get_transaction(utxo_hash).transaction_data
        return transaction_data["outputs"][utxo_index]["locking_script"]







