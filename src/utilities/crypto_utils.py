# Copyright 2026 D-Wave
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

import binascii
from hashlib import sha256

import numpy as np


def calculate_hash(data_in: str) -> str:
    """Basic function SHA256 hashes. A wrapper handling
        formatting data to and from strings to call hashlib's sha256.

    Args:
        data_in (str): the data to be hashed, formatted as a hexadecimal string

    Returns:
        output_hash (str): the hash of the passed data, formatted as a hex string."""

    if type(data_in) != str:
        raise Exception(f"Passed non-string data {data_in} of type {type(data_in)}")

    byte_data = bytearray(data_in, "utf-8")
    hash_data = sha256(byte_data)
    return hash_data.hexdigest()


def validate_zeroes(hash: str, num_zeroes: int = 0) -> bool:
    """Validates that a hash value (formatted as a hex string) meets the criterion of having
    a certain number of leading zeroes. This function handles reformatting the hex string
    into a byte array so that the number of zeroes can be checked directly.

    Args:
        hash (str): the hash to be validated
        num_zeroes (int): the number of leading zeroes required to pass validation

    Returns:
        passes_validation (bool): True if the hash passes, False otherwise."""

    if 4 * len(hash) < num_zeroes:
        raise Exception(
            f"Passed {num_zeroes} 0s, but hash {hash} with length {len(hash)} \
                        represents only {4*len(hash)} binary digits."
        )

    q_hash_bytes = binascii.unhexlify(hash.encode(encoding="utf-8"))
    numpy_bytes = np.frombuffer(np.array(q_hash_bytes), dtype="B")
    numpy_bits = np.unpackbits(numpy_bytes)

    return not np.any(numpy_bits[:num_zeroes])


def compare_hashes(first_hash: str, second_hash: str) -> np.ndarray:
    """Performs a bitwise comparison of two hashes, applying the XNOR logical operation to each pair of bits, yielding
    a 1 if the bits are the same and a 0 if they differ. Expects both hashes to be formatted as hexadecimal strings,
    and returns the resulting bitstring in the same format.

    Args:
        first_hash (str): a hash formatted as a hexadecimal string
        second_hash (str): a second hash, with the same length and format as the first

    Returns:
        hash_comparison (str): a hexadecimal string encoding the bits where the two hashes match and those where they don't.
    """

    hash_bytes = [binascii.unhexlify(hash_bits) for hash_bits in (first_hash, second_hash)]
    numpy_bytes = [np.frombuffer(np.array(q_hash_bytes), dtype="B") for q_hash_bytes in hash_bytes]
    numpy_bits1 = np.unpackbits(numpy_bytes[0])
    numpy_bits2 = np.unpackbits(numpy_bytes[1])
    if len(numpy_bits1) != len(numpy_bits2):
        raise Exception(
            f"Attempted to compare hashes of different \
                        lengths, {len(numpy_bits1)} vs {len(numpy_bits2)}"
        )
    comparison_vector = np.zeros(shape=(len(numpy_bits1)), dtype=np.int8)

    for i in range(len(numpy_bits1)):
        if numpy_bits1[i] == numpy_bits2[i]:
            comparison_vector[i] = 1

    return comparison_vector
