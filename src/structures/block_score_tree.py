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

import json

from src.structures.score_tree_branch import BlockNode, ScoreTreeBranch

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SHORT_HASH_LEN = 5


class BlockScoreTree:
    """Class for tracking structure and score of a blockchain. Each block is represented by a
    6-element named BlockNode tuple (see score_tree_branch.py for definition) formatted as

    (block_hash, previous_block_hash, block_score, total_score, block_height, block_number)

    where total_score is the total score of the chain that ends with that block, block_height
    is the total length of the chain extending from the genesis block to this block and
    block_number is the ordinal number in which the block was added to the chain.

    With the previous_block_hash references defining edges connecting one block to another,
    the chain will take the form of a directed tree (in the graph-theory sense) and under
    typical usage will have a single very long path starting at a leaf and extending back to
    the root, with a number of much shorter branches joining this path at various points. Built
    from this assumption, the main data structure is referred to as the "trunk" and stored in
    the "self.trunk" list. A large part of the design and usage is build around the centrality
    of the trunk.

    In blockchain terms, the trunk represents the canonical chain: the chain that the owner of
    the object considers to be the authoritative one, containing valid blocks and transactions.
    The decision on which blocks should end up in the trunk should thus be determined at a high
    level, by the scores the user assigns the blocks before they are passed into BlockScoreTree.
    This class is designed to depend as little as possible on the details of the users scoring
    schema; the only assumptions encoded into the structure of the class are  1. higher scores
    are preferred to lower scores, 2. total scores are determined additively (that is, the total
    score of a block is the sum of its block_score and the block_score of all its predecessors)
    and that 3. blocks with negative-scores default to being put in secondary branches rather
    than in the trunk.

    Branches are instantiated as members of the ScoreTreeBranch class, with each maintained as
    a single, linear list of blocks. Each list will contain only the blocks that diverge from
    its predecessor, thus only the trunk will form a 'complete' chain while every non-trunk
    chain will consist of multiple branch-sections terminating in a trunk section.

    Outside of the trunk, the choice of which section of blocks belong to a parent branch and
    which belong to a child is largely arbitrary: both chains extending from the fork point
    must be tracked, but neither has inherently special status compared to the other.
    Parent-child relationships between the post-fork sections can be modified with the
    self.promote_branch() method, exchanging the last section of the parent branch (everything
    after the fork point) with the child branch."""

    def __init__(
        self, genesis_block: BlockNode | None = None, score_predicate: "function | None" = None
    ):

        self.trunk = ScoreTreeBranch()
        self.hash_to_branch_lookup = {}
        self.branches = [self.trunk]
        self.short_hash_len = SHORT_HASH_LEN
        if score_predicate is None:
            default_predicate = lambda x: bool(x > 0)
            self.score_predicate = default_predicate
        else:
            if callable(score_predicate):
                self.score_predicate = score_predicate
            else:
                raise Exception(
                    f"BlockScoreTree was passed non-callable score predicate {score_predicate}."
                )

        if genesis_block is not None:
            self.add_block_as_node(genesis_block)

    def __str__(self):
        """Represents the chain as lists of tuples, usually with hashes substantially truncated
        (see short_block_rep() method). Each branch is written as its own line, with the trunk
        as the first line."""

        trunk_str = "Trunk: ["
        for block in self.trunk:
            trunk_str += self.short_block_rep(block)

        for idx, branch in enumerate(self.branches[1:]):
            parent_idx = self.branches.index(branch.parent)
            trunk_str += f"]\n + Branch {idx+1}({parent_idx})  ["
            for block in branch:
                trunk_str += self.short_block_rep(block)
        trunk_str += "]"
        return trunk_str

    def short_block_rep(self, block: BlockNode) -> str:
        """Helper function for __str___ Returns a string that's a representation of an entry in
        the chain, with both of the hashes truncated for space and readability. This is very
        useful when you want a human-readable output, but dangerous to use in cases where you
        need to match the short representation to full blocks.

        Args:
            block: a tuple representing a block

        Returns:
            String: a string representing that block entry, with the hashes cut down to a
                length determined by self.short_hash_len for brevity and readability"""

        short_hash = block.hash[: self.short_hash_len]
        if block.prev_hash:
            short_prev = block.prev_hash[: self.short_hash_len]
        else:
            short_prev = ""
        return f"({short_hash},{short_prev},{block.block_score},{block.total_score},{block.block_number},{block.block_height})"

    @property
    def tip_hash(self):
        return self.trunk.tip.hash

    @property
    def high_score(self):
        return max([branch.high_score for branch in self.branches])

    @property
    def strongest_block_hash(self):
        strongest_branch = max(self.branches, key=lambda x: x.high_score)
        return strongest_branch.high_score_hash

    @property
    def num_nodes(self):
        return sum([len(branch) for branch in self.branches])

    @property
    def most_recent_block(self):
        all_blocks = [block for branch in self.branches for block in branch]
        most_recent_block = max(all_blocks, key=lambda node: node.block_number)
        return most_recent_block

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Block I/O Operations                                          |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def add_block(
        self, block_hash: str, prev_block_hash: str, block_score: float, block_number: int = -1
    ) -> BlockNode:
        """Adds an entry for a block based on its hash, its previous block hash and its score.
        The function determines the proper place in the overall structure to insert the block
        creating a new branch if necessary. It also checks if the block's total score is
        greater than the currently standing high score, and updates the score and strongest
        block reference if so.

        If the previous block hash is None the block will be either added to the trunk (if its
        empty) or raise an Exception.

        Args:
            block_hash: the hash of the new block to be added
            prev_block_hash: the hash of the previous block in the chain
            block_score: the score of the block to be added
            block_number: int (optional). This should not be used except by the internal
                functions that rearrange the tree. When adding blocks normally, block number
                is assigned automatically. It is only necessary to set manually when moving
                existing parts of the tree around."""

        # By default, block number is one more than the number of blocks already in the tree. However, when re-arranging
        # the tree it's necessary to pass in the existing block number instead.
        if block_number < 0:
            block_number = len(self.hash_to_branch_lookup)

        if len(self.trunk) == 0:  # If trunk is empty, initialize tree with this as first block
            new_block = BlockNode(
                hash=block_hash,
                prev_hash=prev_block_hash,
                block_score=round(block_score, 3),
                total_score=round(block_score, 3),
                block_number=block_number,
                block_height=0,
            )
            self.trunk.append_block(new_block)
            self.hash_to_branch_lookup.update({block_hash: self.trunk})
        elif block_hash in self.hash_to_branch_lookup:  # otherwise, check for duplicates
            raise Exception(f"Attempted to add duplicate block with hash {block_hash} to tree.")
        # make sure block predecessor exists
        elif prev_block_hash not in self.hash_to_branch_lookup:
            raise Exception(
                f"Block {block_hash} has predecessor {prev_block_hash} which is not found in the tree."
            )
        else:  # if it does, add it to the tree in the proper spot.
            parent_branch = self.hash_to_branch_lookup[prev_block_hash]
            prev_block = parent_branch.get_block(prev_block_hash)
            new_block = BlockNode(
                hash=block_hash,
                prev_hash=prev_block_hash,
                block_score=round(block_score, 3),
                total_score=round(block_score + prev_block.total_score, 3),
                block_number=block_number,
                block_height=prev_block.block_height + 1,
            )
            new_branch = ScoreTreeBranch(new_block)
            canonical = self.score_predicate(block_score) and parent_branch == self.trunk
            self._append_branch(new_branch, force_child=not canonical)

        return new_block

    def add_block_as_node(self, block: BlockNode, force_trunk: bool = False):
        """Counterpart to add_block for data already formatted as BlockNode named tuple.

        The key difference is that BlockNode objects already contain the computed attributes
        "total_score", "block_number" and "block_height", which cannot be modified without
        declaring a new BlockNode. This function simply keeps those values, assuming they are
        correct for the tree (which will be the case e.g. when reconstructing the tree from
        a file).

        Args:
            BlockNode: a BlockNode named tuple containing the block data"""

        # If the trunk is empty, initialize the tree with this as the first block
        if len(self.trunk) == 0:
            self.trunk.append_block(block)
            self.hash_to_branch_lookup.update({block.hash: self.trunk})
        elif block.hash in self.hash_to_branch_lookup:  # otherwise, check for duplicates
            raise Exception(f"Attempted to add duplicate block with hash {block.hash} to tree.")
        # make sure block predecessor exists
        elif block.prev_hash not in self.hash_to_branch_lookup:
            raise Exception(f"Block {block.hash} has predecessor {block.prev_hash} \
                            which is not found in the tree.")
        else:  # if it does, add it to the tree in the proper spot.
            parent_branch = self.hash_to_branch_lookup[block.prev_hash]
            new_branch = ScoreTreeBranch(block)
            canonical = self.score_predicate(block.block_score) and parent_branch == self.trunk
            self._append_branch(new_branch, force_child=not canonical)

    def _append_branch(self, new_branch: ScoreTreeBranch, force_child: bool = True):
        """Adds a new branch to the tree, joining it to the block referenced by the branch's root
        hash and updating self.hash_to_branch_lookup as necessary. If the root block is in the
        middle of an existing branch, the new_branch will simply be designated as a child of that
        branch and added to self.branches as is. However, if the root of the new branch is the tip
        of an existing branch, then the new branch will be appended to the end of the existing
        branch which will extend it instead of creating a distinct branch.
        The force_child argument can be used to override this behavior, guaranteeing that the new
        branch will always create a distinct branch, and never extend an existing one. Used both
        when adding new blocks to the tree with self.add_block and when restructuring the tree
        with self.promote_branch and various related methods.

        Args:
            new_branch (ScoreTreeBranch): a branch to add to the tree. Can consist of entirely new
                blocks or can be a cut section of a branch that was already in the tree.
            force_child (bool). Defaults to True. When this parameter is True, the new branch will
                always be kept distinct, added as a child of the branch containing the root block.
                If it is set to False, the new branch will be used to extend the branch with the
                root block, if possible (i.e. if the root is also the branch tip)."""

        if new_branch.root_hash not in self.hash_to_branch_lookup:
            raise Exception(f"Root {new_branch.root_hash} of new branch isn't in the tree")

        parent_branch = self.hash_to_branch_lookup[new_branch.root_hash]
        hashes_to_update = list(new_branch.hash_to_index_lookup.keys())
        if new_branch.root_hash != parent_branch.tip.hash or force_child:
            parent_branch.link_child_branch(new_branch)
            self.branches.append(new_branch)
            target_branch = new_branch
        else:
            parent_branch.concatenate_branch(new_branch)  # Automatically updates child references
            target_branch = parent_branch

        for block_hash in hashes_to_update:
            self.hash_to_branch_lookup.update({block_hash: target_branch})

        if not set(hashes_to_update).issubset(set(self.hash_to_branch_lookup.keys())):
            raise Exception(f"Failed updating refs when adding branch {new_branch.base.hash}")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Tree Restructuring                                            |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def promote_to_trunk(self, branch_to_promote: ScoreTreeBranch, cutoff_hash: str | None = None):
        """Promotes a branch repeatedly until it is the trunk. Necessary because branches may be
        arbitrarily deep, but can only be promoted one level at a time. If a value is passed
        for the cutoff_hash argument, only the portion of the trunk up to the block with that
        hash will be promoted (if the passed hash is the tip hash, behavior is identical to
        passing no value).

        Args:
            better_branch: the branch of the tree being promoted to the trunk
            cutoff_hash: the hash of the last block to be included in the
                promoted trunk. Used when it's necessary to only promote part of the trunk. The
                block with the passed hash and every preceding block will be promoted. Later
                blocks will be moved to a new branch which will extend from the new trunk tip."""

        if cutoff_hash is not None and cutoff_hash != branch_to_promote.tip.hash:
            if cutoff_hash not in branch_to_promote:
                raise Exception(f"Cutoff hash {cutoff_hash} not found in branch to promote")

            cutoff_idx = branch_to_promote.hash_to_index_lookup[cutoff_hash] + 1
            self.demote_branch_section(branch_to_promote, cutoff_idx)

        if branch_to_promote == self.trunk:  # If branch is the trunk, do nothing
            return

        for _ in range(branch_to_promote.depth):  # Otherwise, keep promoting to reach trunk
            branch_to_promote = self.promote_branch(branch_to_promote)

        for branch in self.branches:
            if branch != self.trunk:
                if branch.root_hash not in branch.parent:
                    self.to_text_file(f"error_tree {self.trunk.tip.hash[:SHORT_HASH_LEN]}.txt")
                    branch_txt = [
                        (branch.hash[:SHORT_HASH_LEN], branch.prev_hash[:SHORT_HASH_LEN])
                        for branch in branch.node_list
                    ]
                    parent_txt = [
                        (branch.hash[:SHORT_HASH_LEN], branch.prev_hash[:SHORT_HASH_LEN])
                        for branch in branch.parent.node_list
                    ]
                    raise Exception(f"Triggering branch: {branch_txt} with parent: {parent_txt}. \
                                    Root hash is {branch.root_hash} ")

        self.branches.sort(key=lambda x: x.depth)

    def promote_branch(self, branch_to_promote: ScoreTreeBranch) -> ScoreTreeBranch:
        """Promotes a branch to be one level closer to the trunk: the blocks in the branch become
        the tip of its parent branch, replacing all blocks after the point where they joined.
        The tip of the parent is demoted to become a branch, replacing the promoted branch. Any
        branches from either of the sections that are moved should be unaffected: their
        references will still point to the same hashes as before, meaning they will branch off
        of the same blocks as always, even if those blocks are now elsewhere in the tree
        structure. More generally, no data should be added, removed or altered by the swap,
        only the structure of the tree should change.

        Args:
            better_branch: the branch of the chain you're promoting. Intended use is to call
                this only as part of a promote_to_trunk call, which a miner will call on a
                branch that has achieved a higher score than their trunk. However this is not
                enforced, so as to allow more future flexibility in Miner strategy.

        Returns:
            the parent branch, which should now be updated by the promotion"""

        if branch_to_promote == self.trunk:
            return branch_to_promote
        elif branch_to_promote.parent is None:
            raise Exception(f"branch_to_promote {branch_to_promote.base.hash} has no parent.")

        base_branch = branch_to_promote.parent

        # Leave the root block in place, remove the next block
        cut_location = base_branch.hash_to_index_lookup[branch_to_promote.root_hash] + 1
        if cut_location < base_branch.tip_idx + 1:  # Cut base branch so it's tip matches new root
            self.demote_branch_section(base_branch, cut_location)

        if base_branch.tip.hash != branch_to_promote.root_hash:  # Prev step should make this False
            raise Exception(  # So if we're here, something went wrong.
                f"Mismatch between tip of parent branch {base_branch.tip.hash} and root of branch \
                being promoted {branch_to_promote.root_hash} which could not be reconciled."
            )

        self.branches.remove(branch_to_promote)
        self._append_branch(branch_to_promote, force_child=False)

        base_hashes = set(base_branch.hash_to_index_lookup.keys())
        if not base_hashes.issubset(set(self.hash_to_branch_lookup.keys())):
            raise Exception(
                f"When promoting branch {branch_to_promote.base.hash}, found missing \
                hashes: {base_hashes - set(self.hash_to_branch_lookup.keys())} after the promotion."
            )

        return base_branch

    def promote_by_hashes(self, hashes_to_promote: list[str]):
        """Given a list of hashes, promotes branches so that branches containing those hashes are
        as near to the trunk as possible. Will not change the trunk. The purpose of this
        method is to allow for a clean coloring of global-view graphs in certain corner cases.
        Branches that contain mining blocks are supposed to be colored with the 'undecided'
        coloring, while branches that do not are supposed to be colored with the 'abandoned'
        coloring. If an 'abandoned' branch has a child branch with a mining block, the color
        scheme will be ambiguous; this method ensures that when a mining branch and a non-mining
        branch are adjacent, the former will always have lower depth than the latter, ensuring
        a sensible coloration.

        Args:
            hashes_to_promote: a list of block hashes indicating blocks whose branches should be
                promoted to as low a depth as possible."""
        promoted_branch_tips = set()  # Promoting a branch will change its root but not its tip
        for mining_hash in hashes_to_promote:
            mining_branch = self.hash_to_branch_lookup[mining_hash]
            if mining_branch != self.trunk and mining_branch.tip.hash not in promoted_branch_tips:
                promoted_branch_tips.add(mining_branch.tip.hash)
                current_branch = mining_branch  # Object reference will change with promotion
                max_promotes = mining_branch.depth - 1  # End no later than one level above trunk
                for _ in range(max_promotes):
                    if current_branch.parent.has_blocks(hashes_to_promote):
                        break
                    current_branch = self.promote_branch(current_branch)

    def demote_branch_section(self, branch_to_truncate: ScoreTreeBranch, cut_idx: int):
        """Truncates a branch by removing all blocks from a specified index forward. The removed
        section will be linked to the original branch as a child and all the necessary references
        will be updated.

        Args:
            branch_to_truncate: the branch to be altered
            cut_idx: the index at which the branch is to be cut. The block at this index
                and all blocks at higher indices will become part of a new branch, which is
                linked as a child of the original branch."""

        demoted_section = branch_to_truncate.cut_branch_section(cut_idx)
        demoted_hashes = set(demoted_section.hash_to_index_lookup.keys())
        self._append_branch(demoted_section)
        if not demoted_hashes.issubset(set(self.hash_to_branch_lookup.keys())):
            raise Exception(
                f"When demoting branch {branch_to_truncate.base.hash}, found missing hashes:\
                 {demoted_hashes - set(self.hash_to_branch_lookup.keys())} after the demotion."
            )

    def refactor_branches(self):
        """This function rearranges the branches of the tree to put branches with the highest
        final block number at the lowest level. For most purposes, there is no special meaning
        accorded to the depth of a (non-trunk) branch: which branch out of a pair is a parent and
        which is a child is arbitrary and can be changed at will with the promote_branch method.
        However,  putting the branches with the highest terminal block number at the lowest depth
        is convenient when graphing, as it allows for more efficient use of space and a more
        visually clean graph. This function rearranges branches to meet that criterion."""

        base_branches = []
        for branch in self.branches:
            if branch.depth == 1:
                base_branches.append(branch)

        for base_branch in base_branches:
            branch_descendants = base_branch.get_descendants_by_depth()
            reordered_descendants = list(reversed(branch_descendants))[1:]

            # Working from the highest to the lowest depth allows this to be done in one pass.
            for layer in reordered_descendants:
                pruned_layer = [branch for branch in layer if len(branch.children) > 0]
                for branch in pruned_layer:
                    max_child = max(branch.children, key=lambda x: x.tip.block_number)
                    if max_child.tip.block_number > branch.tip.block_number:
                        self.promote_branch(self.hash_to_branch_lookup[max_child.base.hash])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Getters and Data Access                                        |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_block(self, block_hash: str) -> BlockNode:
        if block_hash in self.hash_to_branch_lookup:
            return self.hash_to_branch_lookup[block_hash].get_block(block_hash)
        else:
            raise Exception(f"Block with hash {block_hash} not found in tree.")

    def to_text_file(self, filename: str, truncate: bool = True):
        """Writes a string representation of the BlockScoreTree object to file.

        Args:
            filename: name of the file to write
            truncate: whether to shorten to hashes in the string representations
                      of the BlockNodes for easy human-readability or to leave them
                      at full length for accuracy."""

        short_hash_len = self.short_hash_len
        if not truncate:
            self.short_hash_len = len(self.trunk.tip.hash)
        with open(filename, "w") as file_obj:
            file_obj.write(str(self))

        if not truncate:
            self.short_hash_len = short_hash_len

    def to_json_file(self, filename: str):
        with open(filename, "w") as f:
            branches = [b.node_list for b in self.branches]
            json.dump(branches, f)

    def to_json(self) -> str:
        branches = [b.node_list for b in self.branches]
        return json.dumps(branches)

    @staticmethod
    def from_json_file(filename: str, cutoff: int | None = None) -> "BlockScoreTree":
        """Given an appropriately formatted file, loads a BlockScoreTree object.
        Ought to keep the same graph structure and scores under realistic circumstances
        (but this is difficult to guarantee in all cases). If provided a positive value for
        cutoff parameter, will reconstruct the graph block by block so that the scores and
        structure can be re-calculated to match the older graph state (rather than using)
        the structural info from the current version of the graph.

        Args:
            filename: the name of the file (including path) containing the graph info
            cutoff: how many blocks of the graph to reconstruct. If left at -1, will
            reconstruct the whole graph, and used the saved structural information to
            determine the new graph structure.

        Returns:
            BlockScoreTree object that is a reconstruction of the saved data
        """

        new_tree = BlockScoreTree()
        with open(filename, "r") as f:
            branch_list = json.load(f)

        node_list = []
        new_branch_list = []
        for branch in branch_list:
            branch_nodes = []
            for element in branch:
                new_node = BlockNode(*element)
                node_list.append(new_node)
                branch_nodes.append(new_node)
            new_branch_list.append(branch_nodes)

        for branch in new_branch_list:
            if branch == new_branch_list[0]:
                trunk = True
            else:
                trunk = False
            for element in branch:
                if cutoff is not None and element.block_number > cutoff:
                    pass
                else:
                    new_tree.add_block_as_node(element, force_trunk=trunk)

        return new_tree
