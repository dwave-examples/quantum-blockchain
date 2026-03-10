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

import os
from pathlib import Path

import pytest

from src.structures.block_score_tree import BlockScoreTree

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
test_dir = os.path.join(CUR_DIR, "score_tree_test")
if not os.path.exists(test_dir):
    os.mkdir(test_dir)
else:
    p = Path(test_dir)
    for file in p.iterdir():
        if not os.path.isdir(file):
            os.remove(file)

trees = []


def test_tree_write(tree_from_dicts, random_tree, bin_layered_dicts, simple_dicts, add_scores):
    """Procedurally defines a variety of trees according the the functions in data_generation.tree_generation.py
    Testing on a variety of different tree structures is more likely to expose situational issues with the code logic.
    Writes a json-formatted copy of each try to the dedicated test directory--if tests fail it is often useful to examine
    the structure of the tree responsible, as it can help pinpoint the issue."""

    simple_trees = [
        tree_from_dicts(add_scores(simple_dicts())),
        tree_from_dicts(simple_dicts(128, 16, 2)),
    ]
    bin_layered_trees = [
        tree_from_dicts(add_scores(bin_layered_dicts())),
        tree_from_dicts(bin_layered_dicts(2, 6)),
        tree_from_dicts(add_scores(bin_layered_dicts(8, 3))),
    ]
    random_trees = [random_tree(50), random_tree(100), random_tree(200), random_tree(400)]

    for tree in simple_trees:
        trees.append(tree)

    for tree in bin_layered_trees:
        trees.append(tree)

    for tree in random_trees:
        trees.append(tree)

    for idx, tree in enumerate(trees):
        tree_path = os.path.join(test_dir, f"test_tree{idx}.json")
        tree.to_json_file(tree_path)
        assert os.path.exists(tree_path), f"Tree file for tree {idx} wrote improperly"


def test_tree_structure():
    for idx, tree in enumerate(trees):
        for branch in tree.branches:
            if branch == tree.trunk:
                assert branch.depth == 0, f"Trunk of tree {idx} depth is not 0"

            else:
                assert (
                    branch.root.hash == branch.root_hash
                ), "Root hash {branch.root_hash} doesn't match root block for tree {idx}."
                depth_diff = branch.depth - branch.parent.depth
                assert (
                    depth_diff == 1
                ), f"Branch rooted at {branch.root_hash} depth differs from parent by {depth_diff} for tree {idx}"
                for child in branch.children:
                    depth_diff = branch.depth - child.depth
                    assert (
                        depth_diff == -1
                    ), f"Branch rooted at {branch.root_hash} depth differs from child by {depth_diff} for tree {idx}"
                    assert (
                        child.root.hash in branch.hash_to_index_lookup
                    ), "Child rooted at {child.root_hash} of branch rooted at {branch.root_hash} not rooted in branch for tree {idx}."


def test_tree_io():
    for idx, tree in enumerate(trees):
        original_tree = tree
        original_tree.to_json_file(os.path.join(test_dir, f"orig_tree{idx}.txt"))
        reconstructed_tree = BlockScoreTree.from_json_file(
            os.path.join(test_dir, f"test_tree{idx}.json")
        )
        reconstructed_tree.to_text_file(os.path.join(test_dir, f"recon_tree{idx}.txt"))
        assert (
            original_tree.high_score == reconstructed_tree.high_score
        ), f"High scores don't match for tree {idx}."
        assert len(original_tree.branches) == len(
            reconstructed_tree.branches
        ), f"Different numbers of branches for tree {idx}."
        assert len(original_tree.trunk) == len(
            reconstructed_tree.trunk
        ), f"Trunks are different lengths for tree {idx}."
        assert (
            original_tree.trunk.tip.hash == reconstructed_tree.trunk.tip.hash
        ), "Trunks hold different values."
