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
        nbits: int = 32,
        input_dimension: int = 64,
        orthogonal_to: np.ndarray = None,
        dist: str = "Normal"
    ):
        """This is a class that implements a simple random projection hash function.

        Args:
            random_seed: The random seed to use for generating the plane norms.
            nbits: The number of bits to output.
            input_dimension: The dimension of the input vector.
        """
        prng = np.random.default_rng(random_seed)
        if dist == "Normal":
            self.plane_norms = prng.normal(size=(nbits, input_dimension))
        else:
            self.plane_norms = prng.random(size=(nbits, input_dimension))
        if orthogonal_to is not None:
            orthogonal_to /= np.sqrt(np.sum(orthogonal_to ** 2))
            coeffs = self.plane_norms @ orthogonal_to[:, np.newaxis]
            self.plane_norms = self.plane_norms - orthogonal_to[np.newaxis, :] * coeffs

    def hash_vector(self, input_vector: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """This function hashes a vector using the random projection hash function.

        Args:
            vv: The input vector to hash.

        Returns:
            np.ndarray: The hashed vector.
            np.ndarray: The dot product of the input vector with the plane norms.
        """
        dot = np.dot(input_vector, self.plane_norms.T)
        bool_vector = dot > 0
        binary_vector = bool_vector.astype(int)
        return binary_vector, dot

    def projected_vector(self, input_vector: np.ndarray) -> np.ndarray:
        """This function hashes a vector using the random projection hash function.

        Args:
            vv: The input vector to hash.

        Returns:
            np.ndarray: The hashed vector.
        """
        dot = np.dot(input_vector, self.plane_norms.T)

        return dot  # binary_vector
