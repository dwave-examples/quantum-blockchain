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

import numpy as np


class RandomProjectionHasher:
    def __init__(
        self,
        *,
        random_seed: int = 0,
        num_bits_out: int = 32,
        input_dimension: int = 64,
        forced_orthogonal_vector: np.ndarray | None = None,
    ):
        """This is a class that implements a simple random projection hash function.

        Args:
            random_seed: The random seed to use for generating the plane norms.
            num_bits_out: The number of bits to output.
            input_dimension: The dimension of the input vector.
            forced_orthogonal_vector (np.ndarray or None): Defaults to None. If passed,
                forces all hyperplanes to be orthogonal to this vector."""

        prng = np.random.default_rng(random_seed)
        self.plane_norms = prng.normal(size=(num_bits_out, input_dimension))

        if forced_orthogonal_vector is not None:
            forced_orthogonal_vector /= np.sqrt(np.sum(forced_orthogonal_vector ** 2))
            coeffs = self.plane_norms @ forced_orthogonal_vector[:, np.newaxis]
            self.plane_norms = self.plane_norms - forced_orthogonal_vector[np.newaxis, :] * coeffs

    def hash_vector(self, input_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """This function hashes a vector using the random projection hash function.

        Args:
            input_vector (np.nd_array): An input vector of floats which will be hashed
                and reshaped via a locality-sensitive random projection hash.
        Returns:
            binary_vector (np.ndarray): The result of applying the random projection hashing,
                which should be a np.ndarray whose components are exclusively 1s and 0s. The
                length is defined by the num_bits_out parameter in the class constructor.
            dot_vector (np.ndarray): The dot product of the input vector with the plane norms. This
                should have the same length as the binary vector, but the outputs are signed floats
                indicating distance and direction from the hyperplanes of the random projection."""

        dot_vector = np.dot(input_vector, self.plane_norms.T)
        bool_vector = dot_vector > 0
        binary_vector = bool_vector.astype(int)
        return binary_vector, dot_vector
