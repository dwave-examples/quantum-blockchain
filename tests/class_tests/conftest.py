import json
import os
import sys

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
