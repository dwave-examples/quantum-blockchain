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

import random
from logging import warning
import numpy as np
from scipy.special import erf

from src.protocols.hash_calculator import HashSolver
from src.structures.block import Block
from src.utilities.crypto_utils import basic_compound_hash, compare_hashes, validate_zeroes
from src.values import DELTA_W_0_ALPHA, MIN_SCORE, W_0_ALPHA

class ProofOfWorkProtocol:
    """This class implements the Proof of Work Protocol for a node on the blockchain. In practice, that means the
    class manages mining, scoring and those aspects of Block assembly that require resources outside the scope
    of the Block class, such as anything needing QPU access.
    """

    def __init__(
        self,
        hash_solvers: list[HashSolver],
        quantum_hash_length: int,
        n_zeroes: int,
        allowable_err: int,
    ) -> None:
        """Initializes a ProofOfWorkProtocol object. Intended usage is for a single Miner to initialize one of these objects on startup and
            keep it initialized for the duration of a trial.

        Args:
            protocol_params: set of parameters defining the ProofOfWorkProtocol being implemented. See definition in trial_params.py for details
            hash_solvers: list of HashSolver objects that this object can use to call the .calculate_quantum_hash() method. In general, if a trial
                does not call for solvers to be randomized, this list should only have one element.
            scoring_function (Scoring): scoring function used to assign scores to blocks. See scoring.py for details.
            miner_private_key (RSA.RsaKey): miner's RSA private key.
            miner_public_key (str): the miner's public key, formatted as a hexidecimal string
        """  # TODO replace with Enum

        self.quantum_hash_length = quantum_hash_length
        self.n_zeroes = n_zeroes
        self.allowable_err = allowable_err
        self.solver_list = hash_solvers
        self.set_random_solver()
        self.compound_hashing_function = basic_compound_hash  # TODO design more flexibility

    def validate_block(self, block: Block) -> tuple[bool, float, str]:
        """Validates a block according to the stored protocol parameters and scoring function.

        If self.quantum_hash_length > 0 this should involve either making a call to a D-Wave QPU (using
        the stored solver info and connection) or whatever equivalent is specified by the protocol. Convention
        is that fully valid blocks have positive scores and fully invalid blocks have negative scores, with some
        scoring functions allowing for variation in both how positive and how negative they might be.

        To save QPU cycles, all the classical checks are done before any QPU call is made, with each done in
        increasing order of computational cost. First the block is checked for passing the easily verified
        n_zeroes requirement (which allows efficient filtering of no-work blocks). Then the Merkle
        root is validated, requiring several rounds of repeated SHA256 hashes, at moderate cost.
        Then the digital signature of the block is checked against the miner's provided signature, expected
        to be the most computationally expensive process for blocks with reasonable numbers of transactions.
        If all of these checks pass, then the QPU is called to validate the quantum hash and check it against the
        scoring requirement. Doing it in this order prevents attackers from DDoSing the network with garbage blocks
        that are cheap to produce but expensive to detect: passing each step requires (at a minimum) computational
        work proportional to the work required to validate it.

        Blocks which fail a classical check return default values indicating an invalid block with a very low score.

        Args:
            block: Block. The Block object to be validated

        Returns:
            valid: a bool indicating whether the block passed all classical validation checks and achieved a positive score.
            block_score: the score assigned to the block by the stored scoring function.
            validation_bits: the bitwise report of whether each bit in the quantum hash passed or failed debugging. May not
                            need to be returned in the final implementation, but useful for now.
            sample_time: the time required by the QPU sampling step."""

        valid = False
        block_score = MIN_SCORE

        # If any other validation fails, no reason to waste a QPU call
        if not validate_zeroes(block.hash):
            warning(
                f"N_zeroes validation failed, expected {'0'*self.n_zeroes} got {int(block.hash[self.n_zeroes//2], 16)}"
            )

        elif not block.validate_hash():
            warning(f"Failed hash check for block with hash {block.hash}")

        else:
            valid = True
            block_score, _ = self.score_block(block)

        return valid, block_score, self.current_solver.solver_name

    def mine_block(self, block: Block) -> tuple[Block, float, str]:
        """Makes a single attempt to mine a block based on the stored Proof Of Work requirements. Returns
        the block itself (with a current quantum and classical hash, and possibly a digital signature) as
        well as a summary of whether the block passes the stored requirements and the sample time.

        Args:
            block: Block. A block that is finalized except for the quantum hash, quantum signature (if applicable) and
                   the classical hash. This method will not alter the nonce value: miners should do that on their own.

        Returns:
            MinedBlock: the block with quantum hash, quantum signature (if applicable) and classical hash added
            score: the score assessed for the block. This will be 0 if the block fails the N_zeroes check, otherwise
                it will be defined by the miner's protocol. Since the miner presumes all of their bits to be correct,
                for any scheme other than 'confidence' this will return the maximum possible score. However, when
                using confidence_based scoring, the miner might score their block low enough to no longer consider
                it good, requiring another mining attempt.
            sample_time: the sampling time for the QPU call."""

        new_quantum_hash, dot_vector, _ = self.calculate_quantum_hash(block)
        block.set_quantum_hash(new_quantum_hash)
        validation_bits = [1 for _ in range(self.quantum_hash_length)]
        block.set_hash()
        assert block.validate_hash(), f"Block {block.hash} had invalid hash root after mining."

        if validate_zeroes(block.hash, self.n_zeroes):
            block_score = self.calculate_confidence_score(
                validation_bits, self.allowable_err, dot_vector
            )
        else:
            block_score = MIN_SCORE

        return block, block_score, self.current_solver.solver_name

    def score_block(self, block: Block):
        """Calls the stored scoring function to calculate a score for the block. Checks to make sure the block has a matching
        quantum hash length to what is stored in the protocol data, but does not perform any other data integrity checks.
        For details of the individual scoring function options, see scoring.py

        Args:
            block (Block): the Block object to be scored

        Returns:
            block_score: the score of the block assigned by the stored scoring function.
            validation_bits: whether each bit of the quantum hash passed of failed validation. If self.quantum_hash_length == 0
                            this will just be an empty list.
            sample_time: the time required for the D Wave sampler call"""
        received_hash = block.quantum_hash

        if self.quantum_hash_length > 0:
            calculated_hash, dot_vector, sample_time = self.calculate_quantum_hash(block)
            assert len(received_hash) == len(
                calculated_hash
            ), f"Expected quantum hash of length {len(calculated_hash)}, received hash of length {len(received_hash)}"
            validation_bits = compare_hashes(received_hash, calculated_hash)

        else:
            validation_bits = [1]
            dot_vector = []
            sample_time = 0

        block_score = self.calculate_confidence_score(validation_bits, self.allowable_err, dot_vector)
        return block_score, sample_time

    def calculate_confidence_score(
        self, valid_bits: np.ndarray, allowable_err: int|float, dot_vector: np.ndarray
    ) -> float:
        """Confidence-based scoring, as defined in the quantum blockchain paper (see README for details). In practice 
        this is quite sensitive to quantum_hash_length, allowable_err, solver schemas and num_reads. Some trial and 
        error is required to find sets of values that allow for reasonable validation rates.
        
        Args:
            valid_bits (np.ndarray): a vector of binary values representing which bits of the original hash appeared
                to be valid (i.e matched the validator's calculated hash). Will hold 1 if the corresponding hash bit
                is valid, or a 0 otherwise.
            allowable_err (int or float): the error tolerance of the scoring procedure. Roughly speaking, increasing
                this by 1 compensates for one extra maximum-uncertainty bit (i.e. a bit in which the confidence is 50%).
                A low value means only an extremely high-confidence hash vector will earn a positive score. A low value
                means a hash vector with many highly-uncertain bits can still earn a positive score. However, bit
                errors high-confidence bits will reduce the confidence by far more than 1, so even a few serious 
                errors can overwhelm this threshold at any reasonable value.
            dot_vector (np.ndarray): Vector that contains the dot products of the hash vector with the normal vectors
                of hyperplanes chosen by the random projection operation. This vector is used to calculate the bitwise
                confidence scores: if the value in some coordinate is very far from the mean (W_0_ALPHA), it will have
                very high confidence (close to 1). If it is near the mean, it will have low confidence (close to 0.5). 
            
        Returns:
            confidence_score (float): the validator's overall log confidence that the hash is correct to within
                the error threshold defined by allowable_err"""
        min_confidence = MIN_SCORE
        mean = W_0_ALPHA
        std_dev = DELTA_W_0_ALPHA

        norm_dist = np.abs((dot_vector - mean) / std_dev)
        bitwise_confidence = 0.5 * (1 + erf(norm_dist))
        validation_confidence = [
            a * b + (1 - a) * (1 - b) for a, b in zip(valid_bits, bitwise_confidence)
        ]  # If a validation bit is 1, we use the confidence. If it's 0, we use 1 - the confidence
        log_confidence = np.float64(allowable_err)
        for idx, confidence in enumerate(validation_confidence):
            if confidence == 0:
                return min_confidence
            elif confidence < 0:
                raise ValueError(
                    f"Invalid confidence value {confidence} at index {idx} from bit {valid_bits[idx]} and confidence value {bitwise_confidence[idx]}"
                )
            else:
                log_confidence += np.log2(confidence)

        return round(log_confidence.item(), 2)

    def calculate_quantum_hash(self, block: Block) -> tuple[str, np.ndarray, float]:
        """Calculates the quantum hash for the block provided. This is the centerpiece of the whole
        codebase and the one place where QPU calls are actually made. Produces a hash of length
        defined by self.quantum_hash_length (in turn determined by protocol settings)

        #TODO there is a known issue wherein sample data is not getting deleted as promptly as it should.
        Given how large the sampler output is and the fact that each miner now has their own sampler, this
        can cause memory issues and crashes. Radomir is looking into a fix, but best to keep num_reads low
        and num_miners moderate until it is fixed.

        Args:
            block: (Block) the block whose quantum hash you wish to calculate.

        Returns:
            vector_output: a np vector whose values should be exclusively 0s and 1s, defining the quantum hash.
                    Note that this will be processed into a hex string and stored as such by the Block class: it's
                    more convenient to leave it as raw bits here.
            dot_vector: a np vector encoding the hyperplane distance for each bit (that is, the dot product of the
                        hash vector and the hyperplane's normal vector)
            sample_time: the time required by the sampler to generate the sampler_output"""

        random_seed = int(block.hash_seed, 16)
        self.set_random_solver()

        quantum_hash = self.current_solver.calculate_quantum_hash(
            hash_length=self.quantum_hash_length, rng_seed=random_seed
        )

        return quantum_hash

    def set_random_solver(self):
        """Returns a random solver and its corresponding DWaveSampler. If the self.require_all_solvers flag is set, and one or more
            solvers is a solver is unavailable, the method will check their availability again and again at at successively longer
            intervals until they become available or the number of allowed attempts is exceeded.

        Modifies
            self.current_solver: changes the current solver to one chose randomly from the list of those available.
        """
        solver_choice = random.choice(self.solver_list)
        self.current_solver = solver_choice
