from src.common.utils import calculate_hash
from src.common.transaction import Transaction


def get_merkle_root(transactions: list[Transaction]) -> str:
    """ Given a list of transactions (of any length) iteratively calculates their
        Merkle root. If the number of hashes at any step is odd, the last hash
        in the list will be duplicated so the total number is even. Terminates
        when the list has exactly one element, and returns that element.

        WARNING: the standard definitions of a Merkle tree seem to leave some amount 
        of wiggle room on the exact implementation. All implementations have the same
        important properties, but will produce different root hashes. In the unlikely
        event that we need to compare roots across different code implementations, we should
        check and make sure they're defined the same way.

        Args:
            transactions: a list of Transaction objects

        returns:
             the merkle root of those transactions."""

    transaction_hashes = [transaction.transaction_hash for transaction in transactions]

    while(True):
        if (len(transaction_hashes)%2 == 1): #Pad odd lists so they're even
            dummy_hash = transaction_hashes[-1]
            transaction_hashes.append(dummy_hash)
        new_hashes = []
        for i in range(0,len(transaction_hashes),2): #For each adjacent pair, concatenate and hash
            joined_hashes = calculate_hash(transaction_hashes[i] + transaction_hashes[i+1])
            new_hashes.append(joined_hashes)
        transaction_hashes = new_hashes
        if len(transaction_hashes) == 1:
            break
        
    return transaction_hashes[0]






