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

from src.utilities import crypto_utils


def test_hash_functions():
    """Tests that the core hash function, SHA256, is working as it should. Specifically, this
    test iterates twice over all sequential slices of a regular string, hashing the iteration and
    testing that the outputs have the correct length, and match one another if and only if the
    inputs used are identical."""

    input_string = "abc123abc123abc"
    for i_2 in range(len(input_string) - 1):
        for i_1 in range(i_2, len(input_string)):
            msg_1 = input_string[i_1:i_2]
            hash_1 = crypto_utils.calculate_hash(msg_1)
            assert len(hash_1) == 64, f"Received {hash_1}, hex length 64, received {len(hash_1)}"

            for j_2 in range(len(input_string) - 1):
                for j_1 in range(j_2, len(input_string)):
                    msg_2 = input_string[j_1:j_2]
                    hash_2 = crypto_utils.calculate_hash(msg_2)
                    if msg_1 == msg_2:
                        assert hash_1 == hash_2, f"Expected equal hashes {hash_1} and {hash_2} \
                                                                     for {msg_1} and {msg_1}"
                    else:
                        assert hash_1 != hash_2, f"Expected unequal hashes {hash_1} and {hash_2} \
                                                                       for {msg_1} and {msg_1}."


def test_validate_zeroes():
    """Tests the validate zeroes function over several bit strings with varying numbers of
    leading zeroes, ensuring both that they validate for values less than or equal to the
    number of leading zeroes in the string and that they fail to validate for the next
    higher value."""

    val_1 = int.to_bytes(int("0000011101101011", 2), 2)  # Five zeroes
    val_2 = int.to_bytes(int("0000000010101110", 2), 2)  # Eight zeroes
    val_3 = int.to_bytes(int("0000000000011010", 2), 2)  # Eleven zeroes
    str_1 = binascii.hexlify(val_1).decode(encoding="utf-8")
    str_2 = binascii.hexlify(val_2).decode(encoding="utf-8")
    str_3 = binascii.hexlify(val_3).decode(encoding="utf-8")

    for i in range(6):
        assert crypto_utils.validate_zeroes(
            str_1, i
        ), f"Failed to validate with values {str_1} for {i} zeroes"

    for i in range(9):
        assert crypto_utils.validate_zeroes(
            str_2, i
        ), f"Failed to validate with values {str_2} for {i} zeroes"

    for i in range(12):
        assert crypto_utils.validate_zeroes(
            str_3, i
        ), f"Failed to validate with values {str_3} for {i} zeroes"

    assert not crypto_utils.validate_zeroes(
        str_1, 6
    ), f"Erroneously validated for values {str_1} and 6 zeroes."
    assert not crypto_utils.validate_zeroes(
        str_1, 9
    ), f"Erroneously validated for values {str_2} and 9 zeroes."
    assert not crypto_utils.validate_zeroes(
        str_1, 12
    ), f"Erroneously validated for values {str_3} and 12 zeroes."


def test_compare_hashes():
    """Tests the compare hashes function, to ensure that it correctly identifies the matching and non-matching
    bits between a pair of similar bitstrings."""

    bytes_1 = int.to_bytes(int("000000000000111111111111", 2), length=3)  # 12 0s followed by 12 1s.
    bytes_2 = int.to_bytes(
        int("001001001001110110110110", 2), length=3
    )  # Every 3rd digit should be different
    hash_1 = binascii.hexlify(bytes_1).decode(encoding="utf-8")
    hash_2 = binascii.hexlify(bytes_2).decode(encoding="utf-8")
    assert len(hash_1) == 6, print(
        f"Test hash had length {len(hash_1)}, expected 6"
    )  # Make sure our encoding worked as expected, otherwise
    assert len(hash_2) == 6, print(
        f"Test hash had length {len(hash_2)}, expected 6"
    )  # nothing else will work
    for i in range(6, 1, -2):
        bit_comparison = crypto_utils.compare_hashes(hash_1[:i], hash_2[:i])
        for j in range(3, 4 * i, 3):
            assert bit_comparison[j - 1] == 0
            assert bit_comparison[j - 2] == 1
            assert bit_comparison[j - 3] == 1
