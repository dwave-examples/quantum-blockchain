import pytest
import sys, os, json

from tests.data_generation.tree_generation import (generate_tree_from_dicts, 
                                                   generate_random_tree, 
                                                   generate_binary_layered_tree_dicts, 
                                                   generate_simple_tree_dicts, 
                                                   append_scores)

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