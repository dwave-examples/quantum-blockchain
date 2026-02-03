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

import json

from src.structures.score_tree_branch import BlockNode, ScoreTreeBranch

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# =====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
# =====================================================================================================
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TRUNCATED_HASH_LEN = 5

class BlockScoreTree:
    """Class for tracking structure and score of a blockchain. Each block is represented by a 6-element
    named BlockNode tuple (see score_tree_branch.py for definition) formatted as

    (block_hash, previous_block_hash, block_score, total_score, block_height, block_number)

    where total_score is the total score of the chain that ends with that block, block_height is the total length of
    the chain extending from the genesis block to this block and block_number is the ordinal number in which the block
    was added to the chain.

    With the previous_block_hash references defining edges connecting one block to another, the chain will take the
    form of a directed tree (in the graph-theory sense) and under typical usage will have a single very long path starting
    at a leaf and extending back to the root, with a number of much shorter branches joining this path at various points. Built
    from this assumption, the main data structure is referred to as the "trunk" and stored in the "self.trunk" list. A
    large part of the design and usage is build around the centrality of the trunk.

    In blockchain terms, the trunk represents the canonical chain: the chain that the owner of the object considers
    to be the authoritative one, containing valid blocks and transactions.

    Branches are instantiated as members of the ScoreTreeBranch class, with each maintained as a
    single, linear list of blocks. Each list will contain only the blocks that diverge from its
    predecessor, thus only the trunk will form a 'complete' chain while every non-trunk chain
    will consist of multiple branch-sections terminating in a trunk section.

    The trunk is specifically intended to represent the main or "canonical" chain in this blockchain:
    those blocks which are considered valid and whose transactions can be expected to be honored by
    other blockchain users. Which blocks will be in the trunk is determined at a high-level, based
    on what scores the user assigns to the blocks before passing them into the BlockScoreTree. The only
    scoring assumptions encoded into the structure of this class is that 1. higher scores are preferred
    to lower scores, 2. total scores are determined additively (that is, the total score of a block is the sum
    of its block_score and the block_score of all its predecessors) and that 3. blocks with negative-scores are
    by-default not considered part of the main chain. Logic to alter these assumptions may be added later if it
    becomes useful.

    Outside of the trunk, the choice of which section of blocks belong to a parent branch and which belong to a child
    is largely arbitrary: both chains extending from the fork point must be tracked, but neither has inherently special
    status compared to the other. Parent-child relationships between the post-fork sections can be modified with the
    self.promote_branch() method, exchanging the last section of the parent branch (everything after the fork point) with
    the child branch.
    """

    def __init__(self, genesis_block: BlockNode|None=None, score_predicate: 'function|None'=None):

        self.trunk = ScoreTreeBranch()
        self.hash_to_branch_lookup = {}
        self.branches = [self.trunk]
        self.short_hash_len = TRUNCATED_HASH_LEN
        if score_predicate is None:
            default_predicate = lambda x: bool(x > 0)
            self.score_predicate = default_predicate
        else:
            if callable(score_predicate):
                self.score_predicate = score_predicate
            else:
                raise Exception(f"BlockScoreTree was passed non-callable score predicate {score_predicate}.")
            
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
        """Helper function for __str___ Returns a string that's a representation of an entry in the chain, with both
        of the hashes truncated for space and readability. This is very useful when you want a human-readable
        output, but dangerous to use in cases where you need to match the short representation to full blocks.

        Args:
            block: a tuple representing a block

        Returns:
            String: a string representing that block entry, with the hashes cut down to a length determined by
            self.short_hash_len for brevity and readability"""

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
    
    def add_block_to_branch(self, block: BlockNode, branch: ScoreTreeBranch):
        branch.append_block(block)
        self.hash_to_branch_lookup.update({block.hash: branch})

    def add_block(
        self, block_hash: str, prev_block_hash: str, block_score: float, block_number: int = -1
    ) -> None:
        """Adds an entry for a block based on its hash, its previous block hash and its score.
        The function determines the proper place in the overall structure to insert the block
        creating a new branch if necessary. It also checks if the block's total score is greater
        than the currently standing high score, and updates the score and strongest block reference
        if so.

        If the previous block hash is None the block will be either added to the trunk (if its empty)
        or as the start of a new branch that doesn't actually join the trunk (i.e. its previous block
        is None rather than a hash of the trunk or some lower level branch). This is somewhat
        pathological and should be avoided completely as long as miners simply agree on an initial block rather
        than mining it. But I didn't want to force a guarantee of that at this low level.

        Args:
            block_hash: the hash of the new block to be added
            prev_block_hash: the hash of the previous block in the chain
            block_score: the score of the block to be added
            block_number: int (optional). This should not be used except by the internal functions that rearrange
                         the tree. When adding blocks normally, block number is assigned automatically. It is only
                         necessary to set manually when moving existing parts of the tree around.
        """

        # By default, block number is one more than the number of blocks already in the tree. However, when re-arranging
        # the tree it's necessary to pass in the existing block number instead.
        if block_number < 0:
            block_number = len(self.hash_to_branch_lookup) + 1

        if (
            len(self.trunk) == 0
        ):  # If the trunk is empty, initialize the tree with this as the first block
            new_block = BlockNode(
                hash=block_hash,
                prev_hash=prev_block_hash,
                block_score=round(block_score, 3),
                total_score=round(block_score, 3),
                block_number=block_number,
                block_height=0,
            )
            self.add_block_to_branch(new_block, self.trunk)
        elif block_hash in self.hash_to_branch_lookup:  # otherwise, check for duplicates...
            raise Exception(f"Attempted to add duplicate block with hash {block_hash} to tree.")
        elif (
            prev_block_hash not in self.hash_to_branch_lookup
        ):  # and make sure block predecessor exists...
            raise Exception(
                f"Block {block_hash} has predecessor {prev_block_hash} which is not found in the tree."
            )
        else:  # and if it does, add it to the tree in the proper spot.
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

            #Before block can go in the trunk, it must be checked against score criterion
            canonical = (parent_branch != self.trunk) or self.score_predicate(block_score) 
            if prev_block == parent_branch.tip and canonical:  # Block goes on branch tip
                self.add_block_to_branch(new_block, parent_branch)
            else:  # Block goes in new branch
                new_branch = ScoreTreeBranch()
                self.branches.append(new_branch)
                self.add_block_to_branch(new_block, new_branch)
                parent_branch.link_child_branch(new_branch)

    def add_block_as_node(self, block: BlockNode, force_trunk: bool = False) -> None:
        """Counterpart to add_block for data already formatted as BlockNode named tuple.

        The key difference is that BlockNode objects already contain the computed attributes
        "total_score", "block_number" and "block_height", which cannot be modified without
        declaring a new BlockNode. This function simply keeps those values, assuming they are
        correct for the tree (which will be the case e.g. when reconstructing the tree from a file).
        If those attributes aren't... this function should not be used: instead extract the "hash",
        "prev_hash" and "score" attributes and use them to call add_block instead.

        Args:
            BlockNode: a BlockNode named tuple containing the block data
        """

        if (
            len(self.trunk) == 0
        ):  # If the trunk is empty, initialize the tree with this as the first block
            self.add_block_to_branch(block, self.trunk)
        elif block.hash in self.hash_to_branch_lookup:  # otherwise, check for duplicates...
            raise Exception(f"Attempted to add duplicate block with hash {block.hash} to tree.")
        elif (
            block.prev_hash not in self.hash_to_branch_lookup
        ):  # and make sure block predecessor exists...
            raise Exception(
                f"Block {block.hash} has predecessor {block.prev_hash} which is not found in the tree."
            )
        else:  # and if it does, add it to the tree in the proper spot.
            parent_branch = self.hash_to_branch_lookup[block.prev_hash]
            prev_block = parent_branch.get_block(block.prev_hash)

            #Before block can go in the trunk, it must be checked against score criterion
            canonical = (parent_branch != self.trunk) or \
                (force_trunk or self.score_predicate(block.block_score))  

            if prev_block == parent_branch.tip and canonical:  # Block goes on branch tip
                self.add_block_to_branch(block, parent_branch)
            else:  # Block goes in new branch
                new_branch = ScoreTreeBranch()
                self.branches.append(new_branch)
                self.add_block_to_branch(block, new_branch)
                parent_branch.link_child_branch(new_branch)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Tree Restructuring                                            |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def promote_to_trunk(self, branch_to_promote: ScoreTreeBranch) -> list[str]:
        """Promotes a branch repeatedly until it is the trunk. Necessary because branches may be
        arbitrarily deep, but can only be promoted one level at a time.

        Args:
            better_branch: the branch of the tree being promoted to the trunk

        Returns:
            block_hash_list: a list of the hashes of every block that is newly part of
            the trunk. Important for maintaining the mempool.
        """

        trunk_join_index = self.get_trunk_join_index(branch_to_promote)

        if trunk_join_index is None:  # If branch is the trunk, do nothing
            block_hash_list = []
        else:
            while branch_to_promote != self.trunk:  # Otherwise, keep promoting to reach trunk
                branch_to_promote = self.promote_branch(branch_to_promote)
            block_hash_list = [block.hash for block in self.trunk[trunk_join_index + 1 :]]

        for branch in self.branches:
            if branch != self.trunk:
                try:
                    assert branch.root_hash in branch.parent
                except:
                    self.to_text_file(f"error_tree\
                                    {self.trunk.tip.hash[:TRUNCATED_HASH_LEN]}.txt")
                    branch_txt = [(br.hash[:TRUNCATED_HASH_LEN], br.prev_hash[:TRUNCATED_HASH_LEN])
                                                                        for br in branch.node_list]
                    parent_txt = [(br.hash[:TRUNCATED_HASH_LEN],br.prev_hash[:TRUNCATED_HASH_LEN]) 
                                                                for br in branch.parent.node_list]
                    raise Exception(f"Triggering branch: {branch_txt} with parent: {parent_txt}. Root hash is {branch.root_hash} ")

        self.branches.sort(key=lambda x: x.depth)

        return block_hash_list

    def promote_branch(self, branch_to_promote: ScoreTreeBranch) -> ScoreTreeBranch:
        """Promotes a branch to be one level closer to the trunk: the blocks in the branch become
        the tip of its parent branch, replacing all blocks after the point where they joined. The
        tip of the parent is demoted to become a branch, replacing the promoted branch. Any branches
        from either of the sections that are moved should be unaffected: their references will still
        point to the same hashes as before, meaning they will branch off of the same blocks as always,
        even if those blocks are now elsewhere in the tree structure. More generally, no data should
        be added, removed or altered by the swap, only the structure of the tree should change.

        Args:
            better_branch: the branch of the chain you're promoting. Intended use is to call this only
                         as part of a promote_to_trunk call, which a miner will call on a branch that has
                         achieved a higher score than their trunk. However this is not enforced, so as to allow
                         more future flexibility in Miner strategy.

        Returns:
            the parent branch, which should now be updated by the promotion
        """

        # Can't promote the trunk. No other branches without no parents: if there are
        #final 'else' clause will raise an exception
        if branch_to_promote.parent is not None:
            assert branch_to_promote.depth > 0, \
            (
                f"Branch {[(bn.hash[:TRUNCATED_HASH_LEN], bn.prev_hash[:TRUNCATED_HASH_LEN]) \
                for bn in branch_to_promote]} had depth {branch_to_promote.depth}, parent \
                {[(bn.hash[:TRUNCATED_HASH_LEN], bn.prev_hash[:TRUNCATED_HASH_LEN]) 
                for bn in branch_to_promote.parent]}"
            )
            base_branch = branch_to_promote.parent

            # This chunk and the assert at the end of the 'if' are validation to give visibility 
            # in case of a logic error in the code. If it's working properly, they won't be relevant.
            orig_len = len(base_branch)  
            promoted_len = len(branch_to_promote)  
            total_len = orig_len + promoted_len
            demoted_len = 0 #Default value: overwritten if part of the base branch is demoted
            # Leave the root block in place, remove the next block
            join_loc = base_branch.hash_to_index_lookup[branch_to_promote.root_hash] + 1

            for block in branch_to_promote:
                self.hash_to_branch_lookup.update({block.hash: base_branch})
            base_branch.children.remove(branch_to_promote)
            self.branches.remove(branch_to_promote)

            # If the base branch extends beyond the join location, the remainder must be cut
            if join_loc < base_branch.tip_idx + 1: 
                demoted_section = base_branch.cut_branch_section(join_loc)  
                self.branches.append(demoted_section) # Cut section is added as its own branch.
                for child in demoted_section.children:
                    assert child.parent == demoted_section, f"Child-parent mismatch. Child had \
                                                parent {child.parent}, expected {demoted_section}"
                for block in demoted_section:
                    self.hash_to_branch_lookup.update({block.hash: demoted_section})
                base_branch.link_child_branch(demoted_section)
                demoted_len = len(demoted_section)
                assert demoted_section.parent == base_branch, f"Branch with root \
                                                        {demoted_section.root} had parent \
                                                        with root {demoted_section.parent.root}.\
                                                        Expected {base_branch.root}"
                

            base_branch.concatenate_branch(branch_to_promote)
            assert len(base_branch) + demoted_len == total_len, f"Missing blocks. Demoted: \
                                                        {demoted_len}, promoted: {promoted_len},\
                                                         Orig: {orig_len}, Final {len(base_branch)}"
            return base_branch

        elif branch_to_promote == self.trunk:  # Trying to promote trunk does nothing
            return branch_to_promote

        else:
            raise Exception("Branch has depth 0 but is not the trunk!")

    def refactor_branches(self) -> None:
        """This function rearranges the branches of the tree to put branches with the highest final block number
        at the lowest level. In this structure, trunk has special importance, but outside of that, which branch
        is a parent and which is a child is arbitrary: promote_branch lets us swap between them at will. For graphing
        it is useful to have the branches that will appear longest on the trunk (those that end with the highest block number)
        to have the lowest depth. This function rearranges the branches to meet that criterion.

        """

        base_branches = []
        for branch in self.branches:
            if branch.depth == 1:
                base_branches.append(branch)

        for base_branch in base_branches:
            branch_descendants = base_branch.get_descendants_by_depth()

            #Working from the highest to the lowest depth allows this to be done in one pass.
            for layer in reversed(branch_descendants[:-1]): #Create longest possible branch in...
                layer_remaining = {branch.base.hash for branch in layer}  #... each layer
                for branch in layer:  # Which will ensure that one pass over the next lowest layer is also optimal
                    if branch.depth <= 1:  # Want to stop just short of the bottom branch.
                        break
                    
                    longest_child_branch = branch.get_longest_child()
                    layer_remaining.remove(branch.base.hash)
                    if longest_child_branch is not None:
                        self.promote_branch(longest_child_branch)

                    if len(layer_remaining) == 0:
                        break

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # =====================================================================================================
    #                             SECTION: Getters and Data Access                                       |
    # =====================================================================================================
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_block(self, block_hash: str) -> BlockNode:
        if block_hash in self.hash_to_branch_lookup:
            return self.hash_to_branch_lookup[block_hash].get_block(block_hash)
        else:
            raise Exception(f"Block with hash {block_hash} not found in tree.")

    def get_predecessor_list(
        self, block_hash: str, stopping_hash: str = None, stopping_height: int = 0
    ) -> list[BlockNode]:
        """Returns a list of all the blocknodes in the tree that are predecessors of the block with the passed hash. List
        is populated starting from the passed block and walking backwards through the chain, so the list will be in
        reverse order of chain height. Can be passed a termination condition, either in the form of a block hash or
        a chain height: if so, will only find blocks up until the termination condition (if both conditions are passed
        it will terminate as soon as at least one is met). If no condition is passed, will terminate at the root node
        for the entire tree.

        Args:
            block_hash (str): the hash of the block whose predecessors are to be found
            stopping_hash (str, optional): Defaults to None. Termination condition. Will stop the search as soon as a node
                with matching hash is found.
            stopping_height (int, optional). Defaults to 0. Termination condition. Will stop the search as soon as a node
                with matching height is found. Guaranteed to terminate at the default value of 0 if no other termination
                condition is found, as the root of the tree has height 0 and is a predecessor of every node.

        Returns:
            node_list (str): list of all the nodes in the tree that are predecessors of the block with the passed hash, up
                to the termination condition, in reverse order of block height."""

        if stopping_hash is None:
            stopping_hash = self.trunk.base.hash

        current_block = self.get_block(block_hash)
        node_list = [current_block]
        while current_block.hash != stopping_hash and current_block.block_height > stopping_height:
            current_block = self.get_block(current_block.prev_hash)
            if current_block is not None:
                node_list.append(current_block)
            else:
                raise Exception(f"Reached a dead end in the tree before reaching a termination \
                                condition. Last node accessed was {node_list[-1].hash}")

        return node_list

    def get_trunk_join_index(self, branch: ScoreTreeBranch) -> int|None:
        """Finds the index where a branch or one of its parent branches joins the trunk.

        Args:
            branch: a branch

        Returns:
            index: the index of the block in the trunk where the branch or a parent branch
                    joins the trunk. Returns None if the branch is the trunk."""

        current_branch = branch
        root_hash = None
        while current_branch.parent is not None:
            root_hash = current_branch.root_hash
            current_branch = current_branch.parent

        assert current_branch == self.trunk, "No path found from branch to trunk."

        if root_hash is None:  # Only way root hash remains unset is if starting branch was trunk
            index = None
        else:
            index = self.trunk.hash_to_index_lookup[root_hash]

        return index

    def to_text_file(self, filename: str, truncate: bool = True) -> None:
        """Writes a string representation of the BlockScoreTree object to file.

        Args:
            filename (str): name of the file to write
            truncate (bool): whether to shorten to hashes in the string representations
                            of the BlockNodes for easy human-readability or to leave them
                            at full length for accuracy."""

        short_hash_len = self.short_hash_len
        if not truncate:
            self.short_hash_len = len(self.trunk.tip.hash)
        with open(filename, "w") as file_obj:
            file_obj.write(str(self))

        if not truncate:
            self.short_hash_len = short_hash_len

    def to_json_file(self, filename: str) -> None:
        with open(filename, "w") as f:
            branches = [b.node_list for b in self.branches]
            json.dump(branches, f)

    def to_json(self) -> str:
        branches = [b.node_list for b in self.branches]
        return json.dumps(branches)

    @staticmethod
    def from_node_and_score_list(
        node_list: list[tuple[str, str]], score_list: list[float]
    ) -> "BlockScoreTree":
        assert len(node_list) == len(
            score_list
        ), f"Passed lists of incompatible sizes {len(node_list)} and {len(score_list)} respectively."
        new_tree = BlockScoreTree()
        for hash_pair, score in zip(node_list, score_list):
            new_tree.add_block(
                block_hash=hash_pair[0], prev_block_hash=hash_pair[1], block_score=score
            )
        return new_tree

    @staticmethod
    def from_json_file(filename: str, cutoff: int|None = None) -> "BlockScoreTree":
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
