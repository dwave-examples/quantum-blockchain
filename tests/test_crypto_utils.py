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

import binascii

from src.utilities import crypto_utils


def test_hash_functions():
    """Tests that the core hash functions, SHA256 and RIPEMD160 are working as they should. Specifically, this
    test iterates twice over all sequential slices of a regular string, hashing the iteration and testing
    that the outputs have the correct length, and match one another if and only if the inputs and hash functions
    used are identical.
    """
    input_string = "abc123abc123abc"
    for i_2 in range(len(input_string) - 1):
        for i_1 in range(i_2, len(input_string)):
            msg_1 = input_string[i_1:i_2]
            for hash_fn_1 in crypto_utils.HashFunction:
                hash_1 = crypto_utils.calculate_hash(msg_1, hash_fn_1)
                if hash_fn_1 == crypto_utils.HashFunction.SHA256:
                    assert (
                        len(hash_1) == 64
                    ), f"Received SHA256 hash {hash_1}, expected hex rep to have length 64, received {len(hash_1)}"
                elif hash_fn_1 == crypto_utils.HashFunction.RIPEMD160:
                    assert (
                        len(hash_1) == 40
                    ), f"Received RIPEMD160 hash {hash_1}, expected hex rep to have length 40, received {len(hash_1)}"

                for j_2 in range(len(input_string) - 1):
                    for j_1 in range(j_2, len(input_string)):
                        msg_2 = input_string[j_1:j_2]
                        for hash_fn_2 in crypto_utils.HashFunction:
                            hash_2 = crypto_utils.calculate_hash(msg_2, hash_fn_2)
                            if msg_1 == msg_2 and hash_fn_1 == hash_fn_2:
                                assert (
                                    hash_1 == hash_2
                                ), f"Expected hashes {hash_1} and {hash_2} to have equal values with inputs {msg_1} and {msg_1} and hash function {hash_fn_1} and {hash_fn_2}"
                            else:
                                assert (
                                    hash_1 != hash_2
                                ), f"Expected hashes {hash_1} and {hash_2} to have unequal values with inputs {msg_1} and {msg_1} and hash function {hash_fn_1} and {hash_fn_2}"


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


def test_signature_functions():
    """Tests the cryptographic signature functions by creating two key sets, and ensuring that validate_signature
    returns true if and only if it is passed a message that has been signed with a valid public-private key pair,
    along with the correct signature block and public key corresponding to that message and key pair.
    """

    message = "My hovercraft is full of eels!"
    wrong_message = "He's pining for the fjords."
    alice_priv, alice_pub, alice_address = crypto_utils.get_key_set()
    eve_priv, eve_pub, eve_address = crypto_utils.get_key_set()

    alice_signature = crypto_utils.sign_message(message=message, private_key=alice_priv)
    valid_sig = crypto_utils.validate_signature(
        message=message, signature=alice_signature, pub_key=alice_pub
    )
    assert (
        valid_sig
    ), f"Failed to validate signature over message {message} with public key {alice_pub}"
    bad_validation = crypto_utils.validate_signature(
        message=message, signature=alice_signature, pub_key=eve_pub
    )
    assert (
        not bad_validation
    ), f"Successfully validated message {message} with pub key {eve_pub}, which should have required pub key {alice_pub}"
    eve_spoofed_sig = crypto_utils.sign_message(
        message=message, private_key=eve_priv
    )
    attempted_spoof = crypto_utils.validate_signature(
        message=message, signature=eve_spoofed_sig, pub_key=alice_pub
    )
    assert (
        not attempted_spoof
    ), f"Spoofed signature of message {message} with private key {eve_priv} evaluated as valid. Should have required private key {alice_priv}"
    wrong_validation = crypto_utils.validate_signature(
        message=wrong_message, signature=alice_signature, pub_key=alice_pub
    )
    assert (
        not wrong_validation
    ), f"Successfully validated message {wrong_message} with signature which should have been over {message}"


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
