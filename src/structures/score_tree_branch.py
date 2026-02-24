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

from collections import namedtuple

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
BlockNode = namedtuple(
    "BlockNode", ["hash", "prev_hash", "block_score", "total_score", "block_number", "block_height"]
)


class ScoreTreeBranch:
    """This class serves to encapsulate the fundamental structural units of the BlockScoreTree class, namely branches. The
    structure of a typical probabilistic blockchain - and thus of a BlockScoreTree object - will be a series of linear
    chains of blocks with occasional forks in which a second chain diverges from the first. A ScoreTreeBranch is intended
    to represent and store the data for a single such linear section, while tracking useful metadata such as the locations
    of other chains that fork off this one, a score summary for the section and a reference for the branch's parent (the branch
    it forked off of). This also provides a convenient platform for lower-level manipulations of the chain state - those that
    involve one block or a small, contiguous series of blocks - rather than having them as BlockScoreTree methods.

    For a better understanding of the logic of the global tree structure, refer to the documentation for the BlockScoreTree
    class."""

    def __init__(self, base_block: BlockNode = None):
        """
        Args:
            base_block (BlockNode): the BlockNode object that will serve as the first node of this branch. Once
                                    added, it should never be removed or modified. It's self.hash attribute can
                                    effectively serve as a unique identifier for this branch, as no other block
                                    in any branch should share it. If no base_block is passed in the constructor,
                                    the first block added with self.append_block will be used instead.

        Attributes:
            self.node_list: this is the central data structure of the class. A list of BlockNode objects corresponding to a
                            single, linear section of the blockchain.
            self.hash_to_index_lookup: dict that allows quickly finding the location of any BlockNode in this ScoreTreeBranch
                                        based on its hash value.
            self.children: list of ScoreTreeBranches whose roots are BlockNodes in self.node_list
            self.parent: ScoreTreeBranch containing the predecessor to the first node in self.NodeList
            self.depth: number of ScoreTreeBranch objects that are parents or further ancestors of this one. The trunk
                        of a given BlockScoreTree should always have depth 0, and any other branches should have depth 1 or
                        greater.
        """
        self.node_list = []
        self.hash_to_index_lookup = {}
        self.children = []  # Children and parent will be dynamically linked for easy access
        self.parent = None
        self.depth = 0
        if base_block is not None:
            self._initialize_first_block(base_block)

    def _initialize_first_block(self, base_block: BlockNode):
        if not isinstance(base_block, BlockNode):
            raise Exception(
                f"Expected input argument to have type BlockNode. Received type {type(base_block)} instead."
            )
        elif len(self.node_list) > 0:
            raise Exception("Attempted to initialize non-empty branch.")

        self.node_list.append(base_block)
        self.hash_to_index_lookup.update({base_block.hash: 0})
        self.root_hash = base_block.prev_hash

    @property
    def tip(self) -> BlockNode:
        """Returns the last entry in the node list (i.e. the 'tip' of the branch)."""
        return self.node_list[-1]

    @property
    def tip_idx(self) -> int:
        """Returns the index of the last entry in self.node_list (i.e. the 'tip' of the branch)."""
        return len(self.node_list) - 1

    @property
    def base(self) -> BlockNode:
        """Returns the BlockNode object that is the first entry in the self.node_list."""
        return self.node_list[0]

    @property
    def root(self) -> BlockNode:
        """Returns the BlockNode object that is the immediate predecessor to self.base
        (that is, the predecessor the first block in the branch). Only a branch of depth 0
        (one with no predecessor) should return None; the only branch
        this should be true of is the trunk."""
        if self.parent is not None:
            return self.parent.get_block(self.root_hash)
        elif self.depth != 0:
            raise Exception("Branch has no root but depth is greater than 0.")

        return None

    @property
    def high_score(self) -> float:
        """Returns the highest total_score of any block currently stored in this branch"""
        return max([node.total_score for node in self.node_list])

    @property
    def high_score_hash(self) -> float:
        """Returns the hash of the block with the highest total score in this branch"""
        max_block = max(self.node_list, key=lambda x: x.total_score)
        return max_block.hash

    def __getitem__(self, index: int) -> BlockNode:
        return self.node_list[index]

    def __iter__(self):
        return iter(self.node_list)

    def __len__(self) -> int:
        return len(self.node_list)

    def __contains__(self, item) -> bool:
        # Supporting membership checking by both hash and object, as hashes should be unique identifiers
        if isinstance(item, str):
            return item in self.hash_to_index_lookup

        elif isinstance(item, BlockNode):
            return item.hash in self.hash_to_index_lookup

        return False

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Branch Construction                                          |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def append_block(self, new_block_node: BlockNode):
        """Appends a new block to the end of the branch. This will raise an exception unless
        the branch is empty or .prev_hash attribute of the added block matches the hash of the block
        at the branch tip. Determining where a new block should be added and whether it should form
        a new branch or extend an existing branch needs to be handled at the tree level. This validation
        is important to ensure the correctness of the branch, so this method is the only way blocks
        should be added to the branch: other methods that manipulate the branch should call this one
        as necessary.

        Args:
            new_block (BlockNode): a BlockNode object, which must be a valid choice to add to the branch (see above)
        """

        if not isinstance(new_block_node, BlockNode):
            raise Exception(
                f"Invalid input. Expected type BlockNode, received type {type(new_block_node)}."
            )

        if len(self.node_list) == 0:
            self._initialize_first_block(new_block_node)
        elif new_block_node.prev_hash == self.tip.hash:
            self.node_list.append(new_block_node)
            self.hash_to_index_lookup.update({new_block_node.hash: self.tip_idx})
        else:
            raise Exception(
                f"Invalid block. Root hash {new_block_node.prev_hash} cannot connect to tip hash {self.tip.hash}"
            )

    def update_depth(self):
        """Updates the branch depth to one more than that of its parent. Called recursively on all
        children to ensure the update propagates properly."""

        if self.parent is not None:
            self.depth = self.parent.depth + 1
        else:
            self.depth = 0
        for child in self.children:
            child.update_depth()

    def set_parent(self, parent_branch: "ScoreTreeBranch"):
        """Sets the passed branch as the parent of the current branch
        (provided that is a legal assignment). Will not set the other end
        of the relationship (this is intended to be called by link_child_branch,
        rather than on its own).

        Args:
            parent_branch: a branch that is the parent of the current branch (that is,
                it contains a block whose hash matches the branch's root hash)."""

        if self.root_hash in parent_branch:
            self.parent = parent_branch
            self.update_depth()
        else:
            raise Exception(
                f"Attempted to set branch {self.node_list} as child of branch {parent_branch.node_list}"
            )

    def link_child_branch(self, child_branch: "ScoreTreeBranch"):
        """Links a ScoreTreeBranch to this branch as a child. The child then calls set_parent on
        this branch to complete the linkage.

        Args:
            child_branch (ScoreTreeBranch): the branch that this branch will add to self.children"""

        if child_branch.root_hash in self:
            self.children.append(child_branch)
            child_branch.set_parent(self)
        else:
            raise Exception("Attempted to link branch that was not a child.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Getters and Data Access                                       |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_block(self, block_hash: str) -> BlockNode:
        if block_hash in self.hash_to_index_lookup:
            return self.node_list[self.hash_to_index_lookup[block_hash]]

        return None

    def get_score_map(self):
        score_map = [node.total_score for node in self.node_list]
        return score_map

    def get_longest_child(self):
        """Returns the child of the current branch with the highest-numbered tip block,
        if it is higher than the block number of this branch's tip. This is a helper
        function for BlockScoreTree.refactor_branches, used to find the branches that
        will extend the farthest (when drawn with the graphing logic in SpiralPlotter),
        so they can be positioned to avoid overlaps.

        Returns:
            longest_child (ScoreTreeBranch): child branch of this branch whose
                tip has the highest block_number"""

        highest_block_num = self.tip.block_number
        longest_child = None
        for child in self.children:
            if child.tip.block_number > highest_block_num:
                highest_block_num = child.tip.block_number
                longest_child = child

        return longest_child

    def get_descendants_by_depth(self) -> list[list["ScoreTreeBranch"]]:
        """Compiles a list of all the descendants (children and their children and so on)
        of a branch, sorted into sub-lists by depth. The branch itself will always be the
        first and only item in the first list. Used when restructuring the whole tree,
        as it allows branches to be queried and moved in optimal order."""

        descendants = [[self]]
        for child in self.children:
            if len(descendants) == 1:
                descendants.append([])
            descendants[1].append(child)
            later_descendants = child.get_descendants_by_depth()
            while len(descendants) < len(later_descendants) + 1:
                descendants.append([])  # Add enough entries in descendants to hold all the output

            for i in range(1, len(later_descendants)):  # 0th entry will be the child again
                descendants[i + 1] += later_descendants[i]

        return descendants

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Branch Restructuring                                          |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def pop(self) -> tuple[BlockNode, list["ScoreTreeBranch"]]:
        """Removes a single block from the tip of the branch, updating all data and properties as necessary.
        Blocks should never be altered or removed by any means other than the pop function (if a more
        extensive change is necessary, it should be done by means of repeated calls of pop() and
        append_block(), as in is done in the other methods in this section).

        Returns:
            removed_block (BlockNode): block removed from branch tip
            removed_children: list of all child branches with root at the
                            removed block (there will usually be zero or one
                            but in theory could be arbitrarily many)"""

        if len(self) < 1:
            raise Exception("Cannot pop last block in branch")

        removed_block = self.node_list.pop()
        self.hash_to_index_lookup.pop(removed_block.hash)
        removed_children = []

        for child in self.children:
            if child.root_hash == removed_block.hash:
                removed_children.append(child)

        for child in removed_children:
            self.children.remove(child)

        return removed_block, removed_children

    def concatenate_branch(self, new_branch_section: "ScoreTreeBranch"):
        """Concatenates a new branch section to the tip of the current branch.

        Args:
            new_branch_section (ScoreTreeBranch): a ScoreTreeBranch object. The
                root hash of the object must match this branch's tip hash or the operation
                will fail and throw an exception."""

        if new_branch_section.root_hash == self.tip.hash:
            for block in new_branch_section:
                self.append_block(block)
            for child in new_branch_section.children:
                self.link_child_branch(child)
        else:
            raise Exception(
                "Cannot concatenate a branch whose root doesn't match this branches tip."
            )

    def cut_branch_section(self, cut_idx: int) -> "ScoreTreeBranch":
        """Removes all blocks from a specified index or hash forward (including the block with the matching hash or index).
        Returns a branch containing the removed blocks, with any child branches that belong to it already linked.

        Args:
            cut_idx (int): index of the first block in the cut. Will be ignored in favor of cut_hash if a non-default value of cut-hash is passed.
                In keeping with Python convention for lists, this index can be negative (negative indices will be counted backwards from the end
                of the list, starting with the last element at index -1).

        Returns:
            new_branch (ScoreTreeBranch): a branch containing all the blocks from the cut index
                forward, linked to any children rooted in those blocks."""

        if cut_idx < 0:
            # Convert negative indices to positive so they don't mess up other calculations.
            cut_idx = len(self) + cut_idx

        if cut_idx > self.tip_idx or cut_idx < 1:
            raise Exception(
                f"Error, invalid cut index of {cut_idx} provided. Cut index cannot be 0 and must be within branch bounds."
            )

        moving_blocks = []
        moving_children = []
        num_removals = len(self) - cut_idx
        assert (
            num_removals > 0
        ), f"Attempted to cut at index {cut_idx} from branch with base {self.base.hash}, but branch was length {len(self)}"

        for i in range(num_removals):
            block, children = self.pop()
            # Block appended to moving_blocks in reversed order, newest blocks first, oldest blocks last
            moving_blocks.append(block)
            moving_children += children

        new_branch = ScoreTreeBranch()
        for i in range(num_removals):
            next_block = moving_blocks.pop()
            # Thus when we pop them off of moving_blocks, we get them in the correct order to add them to the new branch.
            new_branch.append_block(next_block)

        assert (
            len(moving_blocks) == 0
        ), f"Some blocks didn't get removed from staging. Blocks with hashes {[b.hash for b in moving_blocks]} remain in staging list."
        assert (
            len(new_branch) == num_removals
        ), f"Some blocks didn't get added to new branch. Missing {num_removals - len(new_branch)} blocks."

        moved_children = []
        for child in moving_children:
            moved_children.append(child)
            new_branch.link_child_branch(child)

        assert len(moving_children) == len(
            moved_children
        ), f"{len(moved_children)} reported moved but {len(moving_children)} were staged to move."

        for child in moved_children:
            assert (
                child.parent == new_branch
            ), f"Child branch with base hash {child.base.hash} has parent root {child.parent}. Should have {new_branch}"

        return new_branch
