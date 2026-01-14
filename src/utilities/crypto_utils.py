import binascii
import sys
import numpy as np

from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import RIPEMD160, SHA256


def calculate_hash(data_in: str, hash_function: str = "sha256") -> str:
    """Basic function for calculating the two types of hash functions currently
    used in the blockchain. Validates both data type and hash function name.

    Args:
        data_in (str): the data to be hashed, formatted as a hexidecimal string
        hash_function (str): name of the hash function to use #TODO replace with enum

    Returns:
        output_hash (str): the hash of the passed data, formatted as a hex string.
    """
    if type(data_in) != str:
        raise Exception(f"Passed non-string data {data_in} of type {type(data_in)}")
    data = bytearray(data_in, "utf-8")
    if hash_function == "sha256":
        h = SHA256.new()
        h.update(data)
        output = h.hexdigest()
    elif hash_function == "ripemd160":
        h = RIPEMD160.new()
        h.update(data)
        output = h.hexdigest()
    else:
        raise Exception(f"Invalid hash function argument {hash_function} passed!")

    return output


def validate_zeroes(hash: str, num_zeroes: int = 0) -> bool:
    """Validates that a hash value (formatted as a hex string) meets the criterion of having
    a certain number of leading zeroes. This function handles reformatting the hex string
    into a byte array so that the number of zeroes can be checked directly.

    Args:
        hash (str): the hash to be validated
        num_zeroes (int): the number of leading zeroes required to pass validation

    Returns:
        passes_validation (bool): True if the hash passes, false otherwise."""

    q_hash_bytes = binascii.unhexlify(hash.encode(encoding="utf-8"))
    numpy_bytes = np.frombuffer(np.array(q_hash_bytes), dtype="B")
    numpy_bits = np.unpackbits(numpy_bytes)

    if np.any(numpy_bits[:num_zeroes]):  # TODO consider validating length of hash_bytes
        return False
    else:
        return True


def basic_compound_hash(hash_seed: str, quantum_hash: str, quantum_signature: str = "") -> str:
    """Concatenates two or three strings and hashes the result. Intended use is to combine the basic header data
    and the quantum hash into a single hash value. This could be done with the existing functions,
    this is mostly a placeholder for something that we may want to replace with a more complicated
    hash calculation procedure later.

    Args:
        hash_seed (str): the hash seed of the original block header. See block.py for full definition
        quantum_hash (str): the quantum hash of the block
        quantum_signature (str, optional): Defaults to the empty string. Digital signature over the quantum
            hash of the block.

    Returns:
        compound_hash (str): the hash of the concatenation of the strings"""
    return calculate_hash(hash_seed + quantum_hash + quantum_signature)


def get_key_set(private_key_string: str = None, hexlify_private=False) -> tuple[str, str, str]:
    """Takes a hex-string formatted RSA private key and uses it to create the corresponding
    public key and blockchain address (which is just the public key hashed twice). If no
    private key is provided, it will generate a new one and work from that instead.

    Args:
        private_key_string: (str) an RSA private key, formatted as a hexidecimal string.
        If "None" is passed, will generate a new RSA private key and pass that.
        hexlify_private: (book) flag to determine whether to return the private key as
            an RSA private key object (default) or as a hexidecimal string.

    Returns:
        private_key: either an RSA private key object imported from the passed string, or the same
            passed private key string.
        public_key_hex: the public key corresponding to the private key, formatted as a hexidecimal string.
        public_key_hash: the blockchain address corresponding to the public key, which is just the public key
                            hashed sequentially with ripemd160 and SHA256"""

    if private_key_string is None:
        private_key = RSA.generate(2048)
    else:
        private_key = RSA.importKey(private_key_string)

    public_key = private_key.publickey().export_key("DER")
    public_key_hex = binascii.hexlify(public_key).decode("utf-8")
    public_key_hash = calculate_hash(
        calculate_hash(public_key_hex, hash_function="sha256"), hash_function="ripemd160"
    )

    if hexlify_private:
        private_key = private_key.export_key().decode("utf-8")

    return private_key, public_key_hex, public_key_hash


def sign_message(message: str, private_key: str) -> str:
    """Implements an pkcs1_15 digital signature algorithm to sign the message passed as a string.
    This function simply handles the formatting in order to smoothly use the functions included
    in the pkcs1_15 module of the Crypto.Signature package so that data typing can be kept consistent
    in the rest of the codebase.

    Args:
        message: (str) The message to be signed, formatted as a Python string
        private_key: (str) the private key of the party wishing to sign the message.
                         This should never be bound to any non-instance variable, as it
                         must stay private to the agent that owns it in order to be secure.

    Returns:
        signature_hex (str): the digital signature, formatted as a hex string"""

    message_bytes = bytearray(message, "utf-8")
    hash_object = SHA256.new(message_bytes)
    signature = pkcs1_15.new(private_key).sign(hash_object)
    signature_hex = binascii.hexlify(signature).decode("utf-8")
    return signature_hex


def validate_signature(message: str, signature: str, pub_key: str) -> bool:
    """Counterpart to the sign_message function above, uses the pkcs1_15 to validate a signature
        generated by that function.

    Args:
        message (str): The message to be validated, formatted as a hex string.
        signature (str):  The signature to be validated, formatted as a hex string.
        pub_key (str): The public key of the signer, formatted as a hex string.

    Returns:
        is_valid (bool): True if the signature is valid, False otherwise"""
    signature_decoded = binascii.unhexlify(signature.encode("utf-8"))
    message_bytes = bytearray(message, "utf-8")
    message_hash = SHA256.new(message_bytes)
    public_key_bytes = pub_key.encode("utf-8")
    public_key_object = RSA.import_key(binascii.unhexlify(public_key_bytes))
    try:
        pkcs1_15.new(public_key_object).verify(message_hash, signature_decoded)
        return True
    except:
        return False


def compare_hashes(first_hash: str, second_hash: str) -> np.ndarray:
    """Performs a bitwise comparison of two hashes, applying the XNOR logical operation to each pair of bits, yielding
    a 1 if the bits are the same and a 0 if they differ. Expects both hashes to be formatted as hexidecimal strings,
    and returns the resulting bitstring in the same format.

    Args:
        first_hash (str): a hash formatted as a hexidecimal string
        second_hash (str): a second hash, with the same length and format as the first

    Returns:
        hash_comparison (str): a hexidecimal string encoding the bits where the two hashes match and those where they don't.
    """
    print(first_hash)
    print(second_hash)
    hash_bytes = [
        binascii.unhexlify(hash_bits)#.encode(encoding="utf-8"))
        for hash_bits in (first_hash, second_hash)
    ]
    numpy_bytes = [np.frombuffer(np.array(q_hash_bytes), dtype="B") for q_hash_bytes in hash_bytes]
    numpy_bits1 = np.unpackbits(numpy_bytes[0])
    numpy_bits2 = np.unpackbits(numpy_bytes[1])
    assert len(numpy_bits1) == len(
        numpy_bits2
    ), f"Attempted to compare hashes of different lengths, {len(numpy_bits1)} vs {len(numpy_bits2)}"
    comparison_vector = np.zeros(shape=(len(numpy_bits1)), dtype=np.int8)
    for i in range(len(numpy_bits1)):
        if numpy_bits1[i] == numpy_bits2[i]:
            comparison_vector[i] = 1
    print(numpy_bits1)
    print(numpy_bits2)
    print(comparison_vector)
    return comparison_vector
