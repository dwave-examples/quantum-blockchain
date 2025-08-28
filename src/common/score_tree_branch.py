from collections import namedtuple

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
BlockNode = namedtuple("BlockNode", ["hash","prev_hash","block_score","total_score", "block_number", "block_height"])

class ScoreTreeBranch:

    def __init__(self, base_block: BlockNode = None):
        self.node_list = []
        self.hash_to_index_lookup = {}
        self.children = [] #Children and predecessor will be dynamically linked for easy access
        self.predecessor = None
        self.depth = 0
        self.back_scores = []
        if base_block is not None:
            self.initialize_first_block(base_block)

    def initialize_first_block(self, base_block):
        if not isinstance(base_block, BlockNode):
            raise Exception("Attempted to add something other than a BlockNode")
        elif len(self.node_list) > 0:
            raise Exception("Attempted to initialize non-empty branch.")
        
        self.node_list.append(base_block)
        self.hash_to_index_lookup.update({base_block.hash:0})
        self.root_hash = base_block.prev_hash
        self.back_scores.append((base_block.total_score,0)) #These are important for calculating block soundess. See docstring of update_back_scores for more detail.

    @property
    def tip(self):
        return self.node_list[-1]
    
    @property
    def tip_idx(self):
        return len(self.node_list) - 1
    
    @property
    def base(self):
        return self.node_list[0]
    
    @property
    def root(self):
        if self.predecessor is not None:
            return self.predecessor.get_block(self.root_hash)
        else:
            return None
        
    @property
    def best_score(self):
        return self.back_scores[0][0]
        
    def __getitem__(self,index):
        return self.node_list[index]
    
    def __iter__(self):
        return iter(self.node_list)
    
    def __len__(self):
        return len(self.node_list)
    

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Branch Construction                                          |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def append_block(self, new_block: BlockNode):
        """ Appends a new block to the end of the branch. This will fail (raising an exception) unless
            the branch is empty or .prev_hash attribute of the added block matches the hash of the block
            at the branch tip. Determining where a new block should be added and whether it should form
            a new branch or extend an existing branch needs to be handled at the tree level. This validation
            is important to ensure the correctness of the branch, so this method is the only way blocks
            should be added to the branch: other methods that manipulate the branch should call this one
            as necessary.
            
            Args:
                new_block (BlockNode): a blocknode object, which must be a valid choice to add to the branch (see above)"""

        if not isinstance(new_block, BlockNode):
            raise Exception("Attempted to add something other than a BlockNode")
 
        if len(self.node_list) == 0:
            self.initialize_first_block(new_block)
        elif new_block.prev_hash == self.tip.hash:
            self.node_list.append(new_block)
            self.hash_to_index_lookup.update({new_block.hash:self.tip_idx})
            self.update_back_scores(new_block.total_score, self.tip_idx)              
        else:
            raise Exception(f"Invalid block. Root hash {new_block.prev_hash} cannot connect to tip hash {self.tip.hash}")
        
    def update_depth(self):
        """ Updates the branch depth to one more than that of its predecessor. Called recursively on all 
            children to ensure the update propogates properly."""
        
        if self.predecessor is not None:
            self.depth = self.predecessor.depth + 1
        else:
            self.depth = 0
        for child in self.children:
            child.update_depth()

    def set_predecessor(self, pred_branch: 'ScoreTreeBranch'):

        """ Sets the passed branch as the predecessor of the current branch
            (provided that is a legal assignment). Will not set the other end 
             of the relationship: this is intended to be called by link-to-child,
             rather than on its own. 
             
             Args:
                pred_branch: a branch that is the predecessor of the current branch (that is
                it contains a block whose hash matches the branch's root hash)."""
        
        if self.root_hash in pred_branch.hash_to_index_lookup:
            self.predecessor = pred_branch
            self.update_depth()

            
    def link_child_branch(self, child_branch: 'ScoreTreeBranch'): 
        """ Links a ScoreTreeBranch to this branch as a child. The child then calls set_predecessor on
            this branch to complete the linkage. """
        if child_branch.root_hash in self.hash_to_index_lookup:
            self.children.append(child_branch)
            child_branch.set_predecessor(self)
            self.update_back_scores(child_branch.best_score, self.hash_to_index_lookup[child_branch.root_hash])
        else:
            raise Exception("Attempted to link branch that was not a child.")

    def update_back_scores(self, new_score, new_index):
        """ This function manages the self.back_scores list maintained by each branch. These scores
            are the key component of calculating the soundess of each block (how "stable" its place in
            the blockchain is). For its soundness, each block will use the better of its own total score,
            and that of any successor block in the tree--that is, any block later in its branch, or in
            any children higher on its branch. Thus high scores propagate backwards through branches:
            in the common case where the tip holds the highest score, all blocks in its branch will
            use its total score as their back score (as will any preceding block in parent branches).
            
            Back data is maintained as a list of tuples of the form (back_score, index), indicating that the 
            block at self.node_list[index] and every block prior to are assigned back_score. This means that
            for branches where the tip has the highest score (the most common case), only one entry will need
            to be maintained. The list is always mainained in strictly decreasing score order and strictly
            increasing index order, so when an existing entry has lower index and lower score than an new
            entry, it will be removed."""

        if len(self.back_scores) == 0:
            self.back_scores.append((new_score, new_index))
            if self.predecessor is not None:
                root_idx = self.predecessor.hash_to_index_lookup[self.root_hash]
                self.predecessor.update_back_scores(self.best_score, root_idx)
                

        insert = False
        if new_index > self.back_scores[-1][1]:
            insertion_point = len(self.back_scores)
            insert = True
        else:
            for idx, entry in enumerate(self.back_scores):
                if new_index <= entry[1]:
                    insertion_point = idx
                    if new_score > entry[0]:
                        insert = True
                        if new_index == entry[1]:
                            insertion_point += 1 #Inserting ahead of same-indexed entries ensures they get removed in the next step
                    break
        
        if insert:
            assert insertion_point >= 0, "Invalid insertion point."
            self.back_scores.insert(insertion_point, (new_score, new_index))
            current_idx = insertion_point
            while current_idx > 0:
                if self.back_scores[current_idx-1][0] <= new_score:
                    self.back_scores.pop(current_idx-1)
                    current_idx -= 1
                else:
                    break

            if self.predecessor is not None:
                root_idx = self.predecessor.hash_to_index_lookup[self.root_hash]
                self.predecessor.update_back_scores(self.best_score, root_idx)
        

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Getters and Data Access                                       |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_block(self, block_hash: str) -> BlockNode:
        if block_hash in self.hash_to_index_lookup:
            return self.node_list[self.hash_to_index_lookup[block_hash]]
        else:
            return None
        
    def get_soundness_map(self, high_score, trunk = False):
        """ Block soundness measures how secure a block's place in the blockchain is:
            specifically, what is the minimum number of blocks that would be needed to move
            that block into or out of the trunk. For a block at the tip of a branch (including the trunk),
            this is simply the difference in scores between the tip of that branch and the highest-scoring block in any
            other branch. That is, for a branch it will always be branch_tip_score - trunk_high_score. For the
            trunk it will be trunk_high_score - max_branch_score where the latter is the best score of any block not in
            the trunk. 
            
            For blocks that are not in a branch tip, the situation is more complicated. Trunk blocks can only be displaced
            by branches rooted in blocks lower in the trunk. Non-trunk blocks can only be joined to the trunk by the extension
            of their own branch, or the extension of successor branches rooted higher in their branch than they are. For branch
            blocks this means that they "inherit" the best soundness of any successor blocks, while trunk blocks inherit the worst
            soundness of predecessor blocks"""
        
        map= []
        if trunk:
            branch_join_indices = {}
            for child in self.children: #Easier to list which blocks have children once than check the whole list each time
                if child.root_hash in branch_join_indices:
                    branch_join_indices[child.root_hash].append(child)
                else:
                    branch_join_indices.update({child.root_hash:[child]})
            previous_worst = high_score #Start with the highest possible score: we can only go down from there
            for block in self.node_list:
                soundness = high_score - block.total_score
                if block.hash in branch_join_indices: #Only need to check branches starting from this block--earlier branches will
                    for child in branch_join_indices[block.hash]: #already be covered by previous_worst
                        soundness = min(soundness, high_score - child.best_score)
                if previous_worst < soundness:
                    soundness = previous_worst
                else:
                    previous_worst = soundness

                map.append(soundness)

        else:
            for idx in range(len(self.node_list)):
                block_score = None 
                for score, score_idx in reversed(self.back_scores):
                    if idx <= score_idx:
                        block_score = score
                assert block_score is not None, f"No back score found in branch {self.base.block_number} at index {idx}. Scores are {self.back_scores}"
                map.append(block_score - high_score)

        assert len(map) == len(self.node_list), f"Branch {self.base.block_number} missing {len(self.node_list) - len(map)} scores!"
        return map

        
    def get_leaves(self) -> list['ScoreTreeBranch']: #TODO consider removing
        """ Returns a list of all leaves (branches with no children) that are
            successor branches of self. Will recursively traverse linked branch 
            structure until all leaves are found. If called by a branch with no 
            children, will return self, thus every call returns a list of at least
            one leaf."""
        
        leaves = []
        if len(self.children) == 0:
            leaves.append(self)
        else:
            for child in self.children:
                child_leaves = child.get_leaves()
                leaves += child_leaves

        return leaves
    
    def get_descendants_by_depth(self) -> list[list['ScoreTreeBranch']]:
        """ """
        
        descendants = [[self]]
        for child in self.children:
            if len(descendants) == 1:
                descendants.append([])
            descendants[1].append(child)
            later_descendants = child.get_descendants_by_depth()
            while len(descendants) < len(later_descendants)+1:
                descendants.append([]) #Add enough entries in desendants to hold all the output
            for i in range(1, len(later_descendants)): #0th entry will just be child again, so ignore it
                descendants[i+1] += later_descendants[i]

        return descendants
    
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Branch Restructuring                                          |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def pop(self) -> tuple[BlockNode, list['ScoreTreeBranch']]:
        """ Removes a single block from the tip of the branch, updating all data and properties as necessary.
            Blocks should never be altered or removed by any means other than the pop function: if a more
            extensive change is necessary, it should be done by means of repeated calls of pop() and
            append_block(), as in is done in the other methods in this section.
            
            Args:
                None
            Returns:
                removed_block (BlockNode): block removed from branch tip
                removed_children: list of all child branches with root at the
                                removed block (there will usually be zero or one
                                but in theory could be arbitrarily many)"""
        
        if len(self) < 1:
            raise Exception("Cannot pop last block in branch")
        else:
            removed_block = self.node_list.pop()
            self.back_scores.pop() #last node always has an entry in back_scores()
            self.hash_to_index_lookup.pop(removed_block.hash)
            removed_children = []
            for child in self.children:
                if child.root_hash == removed_block.hash:
                    removed_children.append(child)
                    self.children.remove(child)
            self.update_back_scores(self.tip.total_score, len(self.node_list)-1)
                
            return removed_block, removed_children

        
    def concatenate_branch(self, new_branch_section: 'ScoreTreeBranch'): 
        """ Concatenates a new branch section to the tip of the current branch.
        
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
            raise Exception("Cannot concatenate a branch whose root doesn't match this branches tip.")


    def cut_branch_section(self, cut_idx: int) -> 'ScoreTreeBranch':
        """ Removes all blocks from a specified index or hash forward (including the block with the matching hash or index). 
            Returns a branch containing the removed blocks, with any child branches that belong to it already linked.   
            
            Args:
                cut_idx (int): index of the first block in the cut. Will be ignored in favor of cut_hash if a non-default value of cut-hash is passed.
                cut_hash (str): hash value of the first block in the cut. Will take precedence over cut_index if it is passed
                
            Returns:
                new_branch (ScoreTreeBranch): a branch containing all the blocks from the cut index forward, linked to any children rooted
                            in those blocks."""
        
        if cut_idx < 0:
            cut_idx = len(self) + cut_idx #Convert negative indices to positive so they don't mess up other calculations.

        if cut_idx > self.tip_idx or cut_idx < 1:
            raise Exception(f"Error, invalid cut index of {f} provided. Cut index cannot be 0 and must be within branch bounds.")
        
        moving_blocks = []
        moving_children = []
        num_removals = len(self) - cut_idx
        for i in range(num_removals):
            block, children = self.pop()
            moving_blocks.append(block) #Block appended to moving_blocks in reversed order, newest blocks first, oldest blocks last
            moving_children += children
        
        new_branch = ScoreTreeBranch()
        for i in range(num_removals):
            next_block = moving_blocks.pop() 
            new_branch.append_block(next_block) #Thus when we pop them off of moving_blocks, we get them in the correct order to add them to the new branch.

        assert len(moving_blocks) == 0, "Some blocks didn't get removed."
        assert len(new_branch) == num_removals, "Some blocks didn't get added to new branch"

        for i in range(len(moving_children)):
            next_child = moving_children.pop()
            new_branch.link_child_branch(next_child)

        assert len(moving_children) == 0, "Some children didn't get properly moved"

        return new_branch
    
