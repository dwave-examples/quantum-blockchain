import binascii
import json

from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from Crypto.Signature import pkcs1_15

from src.common.utils import calculate_hash
from src.common.block import Block
from src.common.blockchain_memory import BlockchainMemory
from src.common.transaction import Transaction, TransactionInput, TransactionOutput


class Owner:
    def __init__(self, private_key: str=None):
        if private_key:
            self.private_key = RSA.importKey(private_key)
        else:
            self.private_key = RSA.generate(2048)
        public_key = self.private_key.publickey().export_key("DER")
        self.public_key_hex = binascii.hexlify(public_key).decode("utf-8")
        self.public_key_hash = calculate_hash(calculate_hash(self.public_key_hex, hash_function="sha256"),
                                              hash_function="ripemd160")
    

    def sign_transaction(self, transaction: Transaction) -> None:
        """This function signs a transaction with the user's private key.

        Args:
            transaction (Transaction): The transaction to sign

        Returns:
            bytes: The signature of the transaction
        """
        transaction_dict = {"inputs": [tx_input.to_dict(with_unlocking_script=False) \
                                       for tx_input in transaction.inputs],
                            "outputs": [tx_output.to_dict() for tx_output \
                                        in transaction.outputs]}
        transaction_bytes = json.dumps(transaction_dict, indent=2).encode('utf-8')
        hash_object = SHA256.new(transaction_bytes)
        signature = pkcs1_15.new(self.private_key).sign(hash_object)
        signature_hex = binascii.hexlify(signature).decode("utf-8")
        for transaction_input in transaction.inputs:
            transaction_input.unlocking_script = f"{signature_hex} {self.public_key_hex}"
        
        #TODO implement this in transaction class instead
        transaction.transaction_hash = transaction.get_transaction_hash()


    def is_output_owner(self, transaction_output: dict) -> bool:
        """This function checks if the output is owned by the user.

        Args:
            transaction_output (dict): The data representation of the 
                transaction output

        Returns:
            bool: True if the user owns the output, False otherwise
        """
        locking_script = transaction_output.locking_script
        for element in locking_script.split(" "):
            if not element.startswith("OP") and element == self.public_key_hash:
                return True
        return False
    
    #Question: shouldn't this also include an amount for a transaction fee?
    #Updated to make this clearer, cleaner and more efficient. No longer adds
    #extra, unncessary utxos past the required amount, no longer potentially produces
    #multiple transactions
    def create_transaction_to(self,
                              receiver: 'Owner',
                              amount: float,
                              blockchain: BlockchainMemory, #Do not like this, consider revising
                              fee_fraction = 0.1, #Doing it this way works, isn't ideal. Change later.
                              ) -> Transaction:
        """This function creates a transaction to send money to another user. It will create
        one or more transactions to send the input amount of coin to the receiver. The 
        function will iterate through this user's unspent transactions in the order returned by
        the get_unspent_transactions function and create transactions until the amount is
        reached. In the likely event that the amount is not exactly met, the function will split
        the last transaction to send the remaining amount back to the sender.

        Args:
            receiver (Owner): The owner object of the receiver
            amount (float): The amount of coin to send
            blockchain (Block): The current blockchain object that this transaction will be 
                added to
            fee_fraction (float): The fraction of the transaction set aside as transaction fees.
                                  Defaults to 0.1 (10% of total)

        Raises:
            Exception: If the user does not have enough funds to send the amount or
                if the amount is less than or equal to 0.

        Returns:
            list: A transaction that can be added to the blockchain.
        """
  

        if amount <= 0:
            raise Exception("Amount must be greater than 0")

        funds, utxos_info = blockchain.get_user_utxos(user_key_hash = self.public_key_hash, amt_requested = amount)
        if funds < amount:
            raise Exception("Not enough funds")


        outputs = []
        inputs = []
        funds_needed =  amount
        for utxo_dict in utxos_info:
            
            new_input = TransactionInput(utxo_dict["hash"],utxo_dict["index"])
            inputs.append(new_input)
            utxo = utxo_dict["utxo"]

            if utxo.amount > funds_needed:
                change = utxo.amount - funds_needed
                output_to_receiver = TransactionOutput(public_key_hash=receiver.public_key_hash, amount=funds_needed*(1-fee_fraction))
                output_to_self = TransactionOutput(public_key_hash=self.public_key_hash, amount=change)
                outputs.append(output_to_receiver)
                outputs.append(output_to_self)
                funds_needed = 0   #Payed the remainder, so nothing more needed.
            else:
                output_to_receiver = TransactionOutput(public_key_hash=receiver.public_key_hash, amount=utxo.amount*(1 - fee_fraction))
                outputs.append(output_to_receiver)
                funds_needed -= utxo.amount  #Reduced what we still need by the amount in utxo

            if funds_needed == 0:
                break
            elif funds_needed < 0: #This definitely shouldn't happen, so throw exception if it does
                raise Exception("Error: overpayment!")

        new_transaction = Transaction(inputs, outputs)
        self.sign_transaction(new_transaction)

        return new_transaction






