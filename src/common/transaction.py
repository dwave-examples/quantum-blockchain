import json
from src.common.utils import calculate_hash

class TransactionInput:
    def __init__(self, transaction_hash: str, output_index: int, unlocking_script: str = ""):
        """Initializes a new TransactionInput object.

        Args:
            transaction_hash (str): The hash of the Transaction that this
                TransactionInput is spending
            output_index (int): The index of the TransactionOutput in the prior
                Transaction that this TransactionInput is spending
            unlocking_script (str, optional): The script that unlocks the
                TransactionOutput that this TransactionInput is spending.
        """
        self.transaction_hash = transaction_hash
        self.output_index = output_index
        self.unlocking_script = unlocking_script

    def to_json(self, with_unlocking_script: bool = True) -> str:
        return json.dumps(self.to_dict(with_unlocking_script))
    
    def __eq__(self,other):
        try:
            assert isinstance(other, TransactionInput)
            assert self.transaction_hash == other.transaction_hash
            assert self.output_index == other.output_index
            assert self.unlocking_script == other.unlocking_script
            return True
        except AssertionError:
            return False

    def to_dict(self, with_unlocking_script: bool = True):
        if with_unlocking_script:
            return {
                "transaction_hash": self.transaction_hash,
                "output_index": self.output_index,
                "unlocking_script": self.unlocking_script
            }
        else:
            return {
                "transaction_hash": self.transaction_hash,
                "output_index": self.output_index
            }
        
    @staticmethod 
    def from_dict(input_dict):
        transaction_hash = input_dict['transaction_hash']
        output_index = int(input_dict['output_index'])
        unlocking_script = input_dict['unlocking_script']

        return TransactionInput(transaction_hash=transaction_hash, output_index=output_index, unlocking_script=unlocking_script)   
        

class TransactionOutput:
    def __init__(self, public_key_hash: str, amount: float):
        """Represents the output of a transaction. It must be paired with one or more
        TransactionInput to be spent.

        Args:
            public_key_hash (str): The hash of the public key of the recipient
            amount (float): The amount of money to be sent
        """
        self.amount = amount
        self.locking_script = f"OP_DUP OP_HASH160 {public_key_hash} OP_EQUAL_VERIFY OP_CHECKSIG"

    def to_json(self) -> str:#sys.path.append(os.path.join(CUR_DIR, "..",".."))
        return json.dumps(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "amount": self.amount,
            "locking_script": self.locking_script
        }
    
    def __eq__(self,other):
        try:
            assert isinstance(other, TransactionOutput)
            assert self.amount == other.amount
            assert self.locking_script == other.locking_script
            return True
        except AssertionError:
            return False
        
    @staticmethod 
    def from_dict(input_dict):
        amount = float(input_dict['amount'])
        for ele in input_dict['locking_script'].split(' '):
            if not ele.startswith('OP'):
                pub_key_hash = ele

        return TransactionOutput(public_key_hash=pub_key_hash, amount=amount)
        


class Transaction:
    def __init__(self, inputs: list[TransactionInput], outputs: list[TransactionOutput]):
        """ Input lists can currently be formatted either as TransactionInput and TransationOutput
            objects or as their corresponding dictionary representations. Conditional blocks allow
            either format to be processed into the corresponding Transaction object. Ideally this should only
            be able to take objects not dicts, but the origianl codebase sometimes failed to de-serialize objects,
            making this a necessary workaround.
            
            TODO: hunt down any places that still don't deserialize properly and fix them, then remove the
            conditional type handling."""


        if len(inputs) == 0 or type(inputs[0]) == TransactionInput:
            self.inputs = inputs
        else:
            inputs_cleaned = []
            
            for inpt in inputs:
                t_hash = inpt["transaction_hash"]
                out_idx = int(inpt["output_index"])
                if "unlocking_script" in inpt:
                    u_script = inpt["unlocking_script"]
                else:
                    u_script = ""

                new_input = TransactionInput(t_hash, out_idx, u_script)
                inputs_cleaned.append(new_input)

            self.inputs = inputs_cleaned
            
        if type(outputs[0]) == TransactionOutput:
            self.outputs = outputs
        else:
            outputs_cleaned = []

            for output in outputs:
                for elem in output["locking_script"].split(" "):
                    if not elem.startswith("OP"):
                        pk_hash = elem
                new_output = TransactionOutput(public_key_hash=pk_hash, amount=float(output["amount"]))
                outputs_cleaned.append(new_output)
            
            self.outputs = outputs_cleaned
            

        self.transaction_hash = self.get_transaction_hash()

    def __eq__(self,other):
        try:
            assert isinstance(other, Transaction)
            assert self.inputs == other.inputs
            assert self.outputs == other.outputs
            assert self.transaction_hash == other.transaction_hash
            return True
        except AssertionError:
            return False

    def get_transaction_hash(self) -> str:
        transaction_data = {
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [i.to_dict() for i in self.outputs]
        }
        transaction_bytes = json.dumps(transaction_data, indent=2)
        return calculate_hash(transaction_bytes)

    @property
    def transaction_data(self) -> dict:
        transaction_data = {
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [i.to_dict() for i in self.outputs],
            "transaction_hash": self.transaction_hash
        }
        return transaction_data

    @property
    def to_json(self) -> str:
        return json.dumps(self.transaction_data)
