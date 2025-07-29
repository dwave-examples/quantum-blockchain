from datetime import datetime

from src.common.block import Block, BlockHeader
from src.common.blockchain_memory import BlockchainMemory
from src.common.merkle_tree import get_merkle_root
from src.common.transaction import Transaction, TransactionInput, TransactionOutput
from src.common.owner import Owner


def initialize_blockchain(initial_distributions: dict[Owner, float]) -> Block:
    """This function initializes a blockchain by creating a genesis block
    with the initial distributions of coins to the owners. This block
    will create the initial coins from nothing and as such the network
    will have to coalesce around a single genesis block. The initial block
    will be saved to the blockchain memory.

    Args:
        blockchain_memory (BlockchainMemory): A memory object to store 
            the blockchain
        initial_distributions (dict[Owner, float]): A dictionary with the
            initial owners and the amount of coins they will receive
    """
    
    total_allocation = sum(initial_distributions.values())
    timestamp_0 = datetime.timestamp(datetime.fromisoformat('2025-01-01 00:00:00.000'))
    input_0 = TransactionInput(transaction_hash="0000", output_index=0)
    output_0 = TransactionOutput(public_key_hash=b"genesis", amount=total_allocation)
    transaction_0 = Transaction(inputs=[input_0], outputs=[output_0])

    block_header_0 = BlockHeader(previous_block_hash="0000",
                                    timestamp=timestamp_0,
                                    noonce=0,
                                    merkle_root=get_merkle_root([transaction_0]))
    block_0 = Block( 
        transactions=[transaction_0],
        block_header=block_header_0
    )

    distributions = []
    outputs = []
    input_ = TransactionInput(transaction_hash=transaction_0.transaction_hash, output_index=0)
    for owner, amount in initial_distributions.items():
        timestamp = datetime.timestamp(datetime.now())
        output = TransactionOutput(public_key_hash=owner.public_key_hash, amount=amount)
        outputs.append(output)
    transaction = Transaction(inputs=[input_], outputs=outputs)
    distributions.append(transaction) 

    block_header = BlockHeader(previous_block_hash=block_0.block_header.hash,
                                timestamp=timestamp,
                                noonce=0,
                                merkle_root=get_merkle_root([t for t in distributions]))
    block = Block(
        transactions=distributions,
        block_header=block_header,
    )
    
    return block


def initialize_default_blockchain(blockchain_memory: BlockchainMemory):
    albert_wallet = Owner(private_key=albert_private_key)
    bertrand_wallet = Owner(private_key=bertrand_private_key)
    camille_wallet = Owner(private_key=camille_private_key)
    # Albert starts with 40 coins
    timestamp_0 = datetime.timestamp(datetime.fromisoformat('2011-11-04 00:05:23.111'))
    input_0 = TransactionInput(transaction_hash="abcd1234",
                               output_index=0)
    output_0 = TransactionOutput(public_key_hash=b"Albert",
                                 amount=40)
    transaction_0 = Transaction([input_0], [output_0])
    block_header_0 = BlockHeader(previous_block_hash="1111",
                                 timestamp=timestamp_0,
                                 noonce=2,
                                 merkle_root=get_merkle_root([transaction_0]))
    block_0 = Block(
        transactions=[transaction_0],
        block_header=block_header_0
    )

    # Albert sends 30 coins to Bertrand
    timestamp_1 = datetime.timestamp(datetime.fromisoformat('2011-11-04 00:05:23.111'))
    input_0 = TransactionInput(transaction_hash=block_0.transactions[0]["transaction_hash"], output_index=0)
    output_0 = TransactionOutput(public_key_hash=bertrand_wallet.public_key_hash, amount=30)
    output_1 = TransactionOutput(public_key_hash=albert_wallet.public_key_hash, amount=10)
    transaction_1 = Transaction([input_0], [output_0, output_1])
    block_header_1 = BlockHeader(
        previous_block_hash=block_0.block_header.hash,
        timestamp=timestamp_1,
        noonce=3,
        merkle_root=get_merkle_root([transaction_1])
    )
    block_1 = Block(
        transactions=[transaction_1],
        block_header=block_header_1,
        previous_block=block_0,
    )

    # Albert sends 10 coins to Camille
    timestamp_2 = datetime.timestamp(datetime.fromisoformat('2011-11-07 00:05:13.222'))
    input_0 = TransactionInput(transaction_hash=block_1.transactions[0]["transaction_hash"], output_index=1)
    output_0 = TransactionOutput(public_key_hash=camille_wallet.public_key_hash, amount=10)
    transaction_2 = Transaction([input_0], [output_0])
    block_header_2 = BlockHeader(
        previous_block_hash=block_1.block_header.hash,
        timestamp=timestamp_2,
        noonce=4,
        merkle_root=get_merkle_root([transaction_2])
    )
    block_2 = Block(
        transactions=[transaction_2],
        block_header=block_header_2,
        previous_block=block_1,
    )

    # Bertrand sends 5 coins to Camille
    timestamp_3 = datetime.timestamp(datetime.fromisoformat('2011-11-09 00:11:13.333'))
    input_0 = TransactionInput(transaction_hash=block_1.transactions[0]["transaction_hash"], output_index=0)
    output_0 = TransactionOutput(public_key_hash=camille_wallet.public_key_hash, amount=5)
    output_1 = TransactionOutput(public_key_hash=bertrand_wallet.public_key_hash, amount=25)
    transaction_3 = Transaction([input_0], [output_0, output_1])
    block_header_3 = BlockHeader(
        previous_block_hash=block_2.block_header.hash,
        timestamp=timestamp_3,
        noonce=5,
        merkle_root=get_merkle_root([transaction_3])
    )
    block_3 = Block(
        transactions=[transaction_3],
        block_header=block_header_3,
        previous_block=block_2,
    )
    blockchain_memory.store_blockchain_in_memory(block_3)
