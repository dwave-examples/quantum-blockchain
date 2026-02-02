# Copyright 2024 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from datetime import datetime

from src.utilities.crypto_utils import basic_compound_hash, calculate_hash
from src.values import EMPTY_QUANTUM_HASH

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class Block:
    """Class representing a block, the fundamental unit of the quantum blockchian. Most of the logic in this class deals
    with block creation which is a complicated process with multiple steps that must be completed in the right order,
    some of which require QPU access and must be handled external to the Block class. Once a valid block has been created
    it should be locked with the Block.lock() method, ensuring that all its data is now treated as immutable. Once a block
    is locked in can be summarized as a dict with the Block.to_dict method, or serialized into a JSON object with the
    Block.to_json method. A serialized block can be recovered with the static Block.from_json method, which will return a
    locked Block object (as not unlocked block should ever be serialized). The serialized block data will include a hash value,
    but the deserialization process will allow the hash value to be recalculated: the calculated and transmitted values are
    compared as a checksum to guard against data corruption: this is important in real network conditions as even a single
    bit-error in a block will render the entire Block invalid and incompatible with the wider blockchian.

    The steps to Block creation are as follows:

    1. The block can be instantiated with a list of transactions to include, the hash of a previous block, and optionally the
        miner's public key, a timestamp and a nonce value. Everything except the previous block hash may be amended or altered
        later (though the timestamp will never be modified directly)
    2. If new transactions are added after the block is first instantiated, they can be added with the Block.add_transactions()
        method. This will automatically update the timestamp (which should always post-date the most ,recent transaction), and
        invalidate any other hash or signature fields, which will need to be recalculated or re-added. The Merkle Root will be
        automatically recomputed and updated.
    3. Once all the transactions are finalized, the only thing that can be easily altered is the nonce. A miner can then iterate
        through nonce values, calculating quantum hashes with their external ProofOfWorkProtocol and adding them with the
        set_quantum_hash() setter.
    4. Once a quantum hash is added, the miner can then call the Block.set_hash() function to add the final classical hash value.
    5. Once the miner has found a classical hash value that passes the n_zeroes requirement for this proof of work protocol, they
       can call Block.lock() to finalize the block. At this point no other changes may be made to the block. It is considered
       immutable. If they need to add or alter data, they will need to declare a new Block object and start the process of finding
       a valid hash over from step 1.

    Note that any alteration made to transactions or nonce after step 4 will cause the currently-stored quantum hash to be removed:
    this is important as any such alterations will render the quantum hash invalid and prevent the block from passing validation.
    Likewise any alterations made after step 5 will remove both the classical and quantum hashes to be removed, as none of them are
    valid if the internal data is altered.
    """

    def __init__(
        self,
        miner_id: str,
        previous_block_hash: str,
        timestamp: float = None,  # User can pass in timestamp, but adding any further transactions after the block is declared will overwrite it.
        nonce: int = 0,
    ):
        """Initializes a new Block object with the data provided. Intent is to allow user to either add all the block data immediately, or
        declare the block with no data or partial data and add to it later. Either way, once all transactions have been added and a valid
        nonce is found, the block should be locked to prevent further alteration."""

        if timestamp is None:  # If value is still at default, replace with current timestamp.
            timestamp = datetime.timestamp(
                datetime.now()
            )  # TODO consider adding an "elif" clause to make sure a valid timestamp has been passed
        self._locked = False  # Used to indicate a finalized block that should not be altered.
        self._transactions = []

        self._header = {
            "previous_block_hash": previous_block_hash,
            "merkle_root": calculate_hash(""),
            "miner_id": miner_id,
            "timestamp": timestamp,
            "nonce": nonce,
        }

    def __eq__(self, other):
        try:
            assert isinstance(other, Block)
            assert (
                self.hash == other.hash
            )  # Block hashes uniquely encode all block data: no need to compare anything but the hashes.
            return True
        except AssertionError:
            return False

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Core Property Definitions                                     |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    @property
    def hash(self) -> str:
        return self._header["hash"]

    @property
    def current_block_hash(self) -> bool:
        if "hash" in self._header:
            return True
        else:
            return False

    @property
    def header(self) -> dict:
        return self._header

    @property
    def previous_hash(self):
        return self._header["previous_block_hash"]

    @property
    def merkle_root(self):
        return self._header["merkle_root"]

    @property
    def timestamp(self):
        return self._header["timestamp"]

    @property
    def nonce(self) -> int:
        return self._header["nonce"]

    @property
    def miner_id(self) -> str:
        return self._header["miner_id"]

    @property
    def hash_seed(self):
        """This property defines the data fields and ordering used to calculate both quantum and classical
        hashes. Important that this be consistent across all users or they will not calculate
        comparable hash values."""
        seed_string = f"{self.previous_hash}{self.merkle_root}{self.timestamp}{self.merkle_root}{self.miner_id}{self.nonce}"
        return calculate_hash(seed_string)

    @property
    def transactions(self):
        return self._transactions

    @property
    def quantum_hash(self) -> str:
        """Returns the current value of the quantum hash as a hex-formatted string."""
        if self.current_quantum_hash:
            return self._header["quantum_hash"]
        else:
            raise Exception("No quantum hash has been added.")

    @property
    def current_quantum_hash(self) -> bool:
        if "quantum_hash" in self._header:
            return True
        else:
            return False

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Public Mutators                                               |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @nonce.setter
    def nonce(self, value: int):
        """Sets the nonce to the passed value, provided it is an integer and the block is not locked. Raises an
            exception otherwise.

        Args:
            value (int): value to set the nonce to.

        Modifies:
                self._header["hash"]: removes the block hash and the quantum hash and the signature as they will no longer be valid
                self._header["quantum_hash"]: (see above)
        """

        if isinstance(value, int):
            if not self._locked:
                self._header["nonce"] = value
                self._reset_hashes()
            else:
                raise Exception("Attempted to alter the nonce of a locked block.")
        else:
            raise Exception(
                f"Expected type int for nonce value, received type {type(value)} instead."
            )

    def set_quantum_hash(self, quantum_hash: str = EMPTY_QUANTUM_HASH):
        """Sets the passed value for the block's quantum hash, which must be a hex-formatted string.

        Args:
            quantum_hash: the quantum hash formatted as a hexidecimal string

        Modifies:
            self._header["quantum_hash"]: stores the value in this field as a hexidecimal string
        """

        if not self._locked:
            self._reset_hashes()
            self._header["quantum_hash"] = quantum_hash
        else:
            raise Exception("Attempted to set the quantum hash of a locked block.")

    def set_hash(self):
        """Calculates the block hash, storing the result in the 'hash' entry of self._header. This will overwrite
            any existing hash, though the result will be identical if the data has not been altered since the last
            time this function was called.

        Args:
            None

        Modifies:
            self._header["hash:]: sets the hash value
        """
        if self._locked:
            raise Exception("Attempted to set the hash of a locked block.")
        elif not self.current_quantum_hash:
            raise Exception(
                "Block must have a current quantum hash before the block hash can be calculated."
            )

        block_hash = basic_compound_hash(self.hash_seed, self.quantum_hash)
        self._header["hash"] = block_hash

    def lock(self):
        """Checks to make sure the self.current_quantum_hash and self.current_block_hash flag are True, and if so sets
        the block status to locked. All setters should check the self._locked flag before making any alterations,
        so locking a block should prevent any accidental alterations to any of the block data.

        A locked block should be treated as completely final. A single-bit alteration to any transaction or any of the
        header fields will invalidate the whole block and cause any future check of the block's quantum or classical
        hashes to fail."""

        if self.current_quantum_hash and self.current_block_hash:
            self._locked = True
        else:
            raise Exception(
                f"Attempted to lock a block without current hashes. Current States are Quantum Hash: {self.current_quantum_hash}  Block Hash: {self.current_block_hash}"
            )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Private Mutators and Utilities                                |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _reset_hashes(self):
        """Removes both the block hash and the quantum hash. This method is called internally when any operation
        is performed that alters block data and would invalidate the hashes."""

        if self.current_quantum_hash:
            self._header.pop("quantum_hash")
        if self.current_block_hash:
            self._header.pop("hash")

    def _set_timestamp(self):
        """Sets the timestamp of the block to the current time, resetting all the block hashes in the process. Private
        class method that should only be used by the constructor or the add_transactions method."""
        if self._locked:
            raise Exception("Attempted to alter the timestamp of a locked block.")
        else:
            self._header["timestamp"] = datetime.timestamp(datetime.now())
            self._reset_hashes()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Public Data Access and I/O                                    |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @property
    def locked(self):
        """Users should freely be able to check (but not alter) whether a block is locked."""
        return self._locked

    def validate_hash(self) -> bool:
        """Recalculates the block hash and checks it against the stored value. Will automatically
        return False if the block is not locked, as an unlocked block is not considered to have
        a finalized hash value."""

        block_hash = basic_compound_hash(self.hash_seed, self.quantum_hash)
        if block_hash == self.hash:
            return True
        else:
            return False

    @property
    def to_dict(self):
        block_data = {
            "header": self.header,
            "transactions": [t for t in self._transactions],
        }

        return block_data

    @property
    def to_json(
        self,
    ) -> (
        str
    ):  # TODO consider check whether the block is locked and raising an exception otherwise. Non-locked blocks generally shouldn't be serialized.
        return json.dumps(self.to_dict)

    @staticmethod
    def from_dict(block_dict: dict) -> "Block":
        """Reconstitutes a (locked) Block object from a dictionary of its data, such as that created
        by the to_dict method. Will raise an exception if the block hash calculated from
        the stored data does not match the stored hash value--this ensures the integrity
        of the stored data, so that invalid blocks are never treated as valid."""

        header_dict = block_dict.pop("header")
        block_hash = header_dict["hash"]
        miner_id = header_dict["miner_id"]
        quantum_hash = header_dict["quantum_hash"]
        prev_hash = header_dict["previous_block_hash"]
        nonce = int(header_dict["nonce"])
        timestamp = float(header_dict["timestamp"])

        new_block = Block(
            miner_id=miner_id,
            previous_block_hash=prev_hash,
            timestamp=timestamp,
            nonce=nonce,
        )
        new_block.set_quantum_hash(quantum_hash)
        new_block.set_hash()
        new_block.lock()
        if block_hash != new_block.hash:
            raise Exception(
                f"When deserializing block, expected hash {block_hash} but calculated hash {new_block.hash}"
            )

        return new_block

    @staticmethod
    def from_json(json_block: str) -> "Block":  # TODO update for optional hash checking
        """Deserializes a blocked stored as json into a locked Block object. Calls from_dict,
        which performs a check on the hash of the reconstructed Block to ensure integrity."""

        block_dict = json.loads(json_block)
        new_block = Block.from_dict(block_dict)
        return new_block
