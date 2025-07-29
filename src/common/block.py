import json

from src.common.utils import calculate_hash
from src.common.transaction import Transaction

#TODO alter init function to remove merkle_root as argument. Should be added later.
#Consider whether timestamp and hash should also be treated this way: I believe timestamps are supposed to track when
#a block is (fully) assembled, not when the object is first declared. And allowing users to freely access non-final hashes
#seems like something that has few legitimate uses and lots of potential for errors.
class BlockHeader:
    def __init__(self, previous_block_hash: str, timestamp: float, noonce: int, merkle_root: str):
        self.previous_block_hash = previous_block_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.noonce = int(noonce)
        self.hash = self.get_hash()

    def __eq__(self, other):
        try:
            assert self.previous_block_hash == other.previous_block_hash
            assert self.merkle_root == other.merkle_root
            assert self.timestamp == other.timestamp
            assert self.noonce == other.noonce
            assert self.hash == other.hash
            return True
        except AssertionError:
            return False

    #Note: note quite the usual way of calculating a hash (which uses literally just the numbers). Not an issue
    #internally, but something that would need to be changed if we wanted interoperability with other code. 
    def get_hash(self) -> str:
        header_data = {"previous_block_hash": self.previous_block_hash,
                       "merkle_root": self.merkle_root,
                       "timestamp": self.timestamp,
                       "noonce": self.noonce}
        return calculate_hash(json.dumps(header_data))

    def set_hash(self):
        self.hash = self.get_hash()

    #TODO find anywhere in codebase nonce is changed manually and replace with this
    def set_noonce(self, noonce: int):
        if type(noonce) == int:
            self.noonce = noonce
            self.set_hash()
        else:
            raise Exception("Noonce must be an integer!")

    @property
    def to_dict(self) -> dict:
        return {
            "previous_block_hash": self.previous_block_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "noonce": self.noonce,
            "hash":self.get_hash()
        }

    def __str__(self):
        return json.dumps(self.to_dict)

    @property
    def to_json(self) -> str:
        return json.dumps(self.to_dict)

#TODO alter structure of Block class to enforce stricter typing, encapsulation and data hiding.
#This is very important to do here because load-bearing values (block hashes) depend on this being done correctly.
class Block:
    def __init__(
            self,
            transactions: list[Transaction],
            block_header: BlockHeader,
    ):
        self.block_header = block_header
        self.locked = False #Used to indicate a finalized block that should not be altered.
        self.transactions = [] 
        self.add_transactions(transactions)


    def get_transaction(self, transaction_hash: str) -> Transaction:
        """ Given a transaction hash returns the corresponding Transaction object 
            (if it is in the block) or None otherwise."""

        #block.transactions should always be O(1) size, so linear search is fine.
        for transaction in self.transactions:
            if transaction.transaction_hash == transaction_hash:
                return transaction
        
        return None
    
    #TODO find anywhere in the code base where transactions are set manually and replace with this
    def add_transactions(self, transactions: list[Transaction]):
        """ Add a list of transactions to the block, checking to see if they are correctly typed. 
            Once the transactions have been added, updates the merkle root and the hash of the block
            header to reflect the change.
            
            Args:
                transactions: list[Transactions] a list of transactions to add to the block.
            Returns:
                None
            Modifies:
                self.transactions: adds new transactions
                self.block_header.merkle_root: updates the merkle root
                self.block_header.hash: (via the add_merkle_root method)"""
        if self.locked:
            raise Exception("Cannot alter block that has been finalized!")
        else:
            for transaction in transactions:
                if isinstance(transaction, Transaction):
                    self.transactions.append(transaction)
                else:
                    raise Exception(f"Block.add_transactions received unexpected transaction type {type(transaction)}")
            
            self.sign_with_merkle_root()
    
    def sign_with_merkle_root(self) -> bool:
        """ Calculates the block's merkle root--a unique signature of the transactions stored in the block--and writes the
            value to the appropriate attribute in the block header. Note that if any alteration is made to the block's
            transactions, sign_with_merkle_root must be called again (this is done automatically if self.add_transactions()
            is called), otherwise this signiture will be incorrect and the block will likely be automatically rejected by 
            any node recieving it. If the block's self.locked flag is set to True this function will NOT alter the stored
            Merkle root, but will recalculate the root, returning True if any only if the result of the calculation matches
            the stored value.

            #TODO The functionality here should probably just be broken up into 2-3 methods. One that does the calculation
            and the others that call it for the appropriate use-cases (either appending the root or validating the 
            stored root).
            
            Args:
                None
            Returns:
                True if the block is not locked, or if the calculated Merkle root matches the stored root for
                a finalized block. False if the calcualated root doesn't match the stored root for finalized block
            Modifies:
                self.block_header.merkle_root
                self.block_header.hash: once the merkle root is changed, the hash should be updated to reflect it"""

        transaction_hashes = [transaction.transaction_hash for transaction in self.transactions]

        while(True):
            if (len(transaction_hashes) == 0):
                transaction_hashes.append(calculate_hash(''))
                break
            elif (len(transaction_hashes)%2 == 1): #Pad odd lists so they're even
                dummy_hash = transaction_hashes[-1]
                transaction_hashes.append(dummy_hash)
            new_hashes = []
            for i in range(0,len(transaction_hashes),2): #For each adjacent pair, concatenate and hash
                joined_hashes = calculate_hash(transaction_hashes[i] + transaction_hashes[i+1])
                new_hashes.append(joined_hashes)
            transaction_hashes = new_hashes
            if len(transaction_hashes) == 1:
                break

        if not self.locked:
            self.block_header.merkle_root = transaction_hashes[0]
            self.block_header.set_hash()

        return bool(transaction_hashes[0] == self.block_header.merkle_root)  #Automatically True if block isn't locked.

    #TODO consider whether this should be what adds the timestamp to the block header as well
    def lock(self):
        """ Updates the Merkle root in case it has fallen out of date and marks the block as
            locked, indicating its data should not be further altered."""
        self.sign_with_merkle_root()
        self.locked = True

    @property
    def hash(self) -> str:
        return self.block_header.get_hash()

    @property
    def previous_block_hash(self) -> str:
        return self.block_header.previous_block_hash

    #TODO revist this definition. No __eq__ defined for Transaction class, so it's probably just comparing references.
    def __eq__(self, other):
        try:
            assert self.block_header == other.block_header
            assert self.transactions == other.transactions
            return True
        except AssertionError:
            return False        

    #TODO alter these methods so storing and retrieving finalize blocks preserves finalized status.
    def __str__(self):
        return json.dumps({"timestamp": self.block_header.timestamp,
                           "hash": self.hash,
                           "transactions": [t.get_transaction_hash() for t in self.transactions]})

    @property
    def to_dict(self):

        block_data = {
            "header": self.block_header.to_dict,
            "transactions": [t.transaction_data for t in self.transactions]
            }

        return block_data

    @property
    def to_json(self) -> str:
        return json.dumps(self.to_dict)
    