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

import os
import pytest

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

from src.utilities.crypto_utils import get_key_set
from tests.data_generation.block_generation import BlockGenerator
from tests.data_generation.tree_generation import (
    append_scores,
    generate_binary_layered_tree_dicts,
    generate_random_tree,
    generate_simple_tree_dicts,
    generate_tree_from_dicts,
)


@pytest.fixture(scope="module")
def block_gen(transaction_gen):
    return BlockGenerator()


@pytest.fixture(scope="module")
def tree_from_dicts():
    yield generate_tree_from_dicts


@pytest.fixture(scope="module")
def random_tree():
    yield generate_random_tree


@pytest.fixture(scope="module")
def bin_layered_dicts():
    yield generate_binary_layered_tree_dicts


@pytest.fixture(scope="module")
def simple_dicts():
    yield generate_simple_tree_dicts


@pytest.fixture(scope="module")
def add_scores():
    yield append_scores
