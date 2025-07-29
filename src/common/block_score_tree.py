import copy
import json
from collections import namedtuple

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
BlockNode = namedtuple("BlockNode", ["hash","prev_hash","block_score","total_score", "block_number", "block_height"])

class BlockScoreTree:

    """ Class for tracking structure and score of a blockchain. Each block is represented by a 4-tuple
    (CAUTION: not members of the Block class, don't confuse them) formatted as

    (block_hash, previous_block_hash, block_score, total_score)

    where total_score is the total score of the chain that ends with that block. With the previous_block_hash
    references defining edges connecting one block to another, the chain will take the form of a directed tree
    (in the graph-theory sense) and under typical usage will have a single very long path starting at a leaf and
    extending back to the root, with a number of much shorter branches joining this path at various points. Building
    from this assumption, the main data structure is referred to as the "trunk" and stored in the "self.trunk" list. A 
    large part of the design and usage is build around the centrality of the trunk.

    In blockchain terms, the trunk represents the canonical chain: the chain that the owner of the object considers
    to be the authoritative one, containing valid blocks and transactions.

    Branches are stored in separate lists, each of which only includes the blocks which diverge from the trunk 
    (or from a lower-level branch). The location of a block in the tree structure can be found with the 
    self.block_loc_dict dictionary, whose entries are formatted as follows:
    
    block_hash: (branch, block_index)

    where branch is the list object that contains the block and block_index is its position in the list.
    Finally the class maintains a record of the strongest block currently in the list. In the default
    usage this should simply be the tip of the trunk, but different use cases may break that assumption.
	"""

	
    def __init__(self):
		
        self.trunk = []
        self.block_loc_dict = {} #Format block_hash: (branch, block_index)
        self.branches = [self.trunk]
        self.high_score = -9999999 #Should be replaced by something the moment a block is added.
        self.strongest_block_hash = None
        self.short_hash_len = 3 #property because it's primarily used in __str__ which shouldn't take input paramters.
                                #should set to desired value before __str__ is called

    def __str__(self):

        """ Represents the chain as lists of tuples, usually with hashes substantially truncated 
            (see short_block_rep() method). Each branch is written as its own line, with the trunk
            as the first line."""

        trunk_str = 'Trunk: [' 
        for block in self.trunk:
            trunk_str += self.short_block_rep(block)

        for i in range(1,len(self.branches)):
            trunk_str += ']\n' + "Branch " + str(i) + ": ["
            for block in self.branches[i]:
                trunk_str += self.short_block_rep(block) 
        trunk_str += ']'
        return trunk_str

    def short_block_rep(self, block: BlockNode) -> str:

        """ Helper function for __str___ Returns a string that's a representation of an entry in the chain, with both 
            of the hashes truncated for space and readability. This is very useful when you want a human-readable
            output, but dangerous to use in cases where you need to match the short representation to full blocks.

            Args:
                block: a tuple representing a block
        
            Returns:
                String: a string representing that block entry, with the hashes cut down to a length determined by 
                self.short_hash_len for brevity and readability"""

        short_hash = block.hash[:self.short_hash_len]
        if block.prev_hash:
            short_prev = block.prev_hash[:self.short_hash_len]
        else:
            short_prev = ''
        return f"({short_hash},{short_prev},{block.block_score},{block.total_score}, {block.block_number}, {block.block_height})"


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Block I/O Operations                                          |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


    def add_block(self, block_hash: str, prev_block_hash: str, block_score: float, canonical = True, block_number: int = -1):

        """ Adds an entry for a block based on its hash, its previous block hash and its score.
            The function determines the proper place in the overall sturcture to insert the block
            creating a new branch if necessary. It also checks if the block's total score is greater
            than the currently standing high score, and updates the score and strongest block reference
            if so.
            
            If the previous block hash is None the block will be either added to the trunk (if its empty)
            or as the start of a new branch that doesn't actually join the trunk (i.e. its previous block
            is None rather than a hash of the trunk or some lower level branch). This is somewhat 
            pathological and should be avoided completely as long asminers simply agree on an initial block rather
            than mining it. But I didn't want to force a guarantee of that at this low level.

            Args:
                block_hash: the hash of the new block to be added
                prev_block_hash: the hash of the previous block in the chain
                block_score: the score of the block to be added
                canonical: set to False to indicate a block that should not be added to the trunk even if it otherwise
                             would be. Important to allow miners to accept negative score blocks without putting them
                             in their trunks.
        """

        if block_hash in self.block_loc_dict: 
            raise Exception("Duplicate Block!")
        
        #By default, block number is one more than the number of blocks already in the tree. However, when re-arranging
        #the tree it's necessary to pass in the existing block number instead.
        if block_number < 0:
            block_number = len(self.block_loc_dict) + 1 

        #A block whose predecessor isn't in the tree is added at the root
        if prev_block_hash not in self.block_loc_dict:
            new_block = BlockNode(hash=block_hash, prev_hash=prev_block_hash, block_score=block_score, 
                                  total_score=block_score, block_number=block_number, block_height=0)

            #If trunk is empty, new block the first of the trunk
            if canonical and not self.trunk:
                self.trunk.append(new_block)
                self.block_loc_dict.update({block_hash:(self.trunk,0)})

            #Otherwise it forms a disconnected branch (technically a new tree)
            else:
                new_branch = [new_block]
                self.branches.append(new_branch)
                self.block_loc_dict.update({block_hash:(new_branch,0)})

        #A block whose predecessor is found is added to the tree in the proper spot
        else:          
            prev_block_branch,prev_block_loc = self.block_loc_dict[prev_block_hash]
            prev_block = self.get_block(prev_block_hash)
            new_block = BlockNode(hash=block_hash, prev_hash=prev_block_hash, block_score=block_score, total_score=block_score + prev_block.total_score, 
                                  block_number=block_number, block_height=prev_block.block_height+1)

            if prev_block_loc == len(prev_block_branch) - 1 and canonical: #Block goes on branch tip
                prev_block_branch.append(new_block)
                self.block_loc_dict.update({block_hash:(prev_block_branch, prev_block_loc+1)})
            else: #Block goes in new branch
                new_branch = [new_block] 
                self.branches.append(new_branch)
                self.block_loc_dict.update({block_hash:(self.branches[-1],0)})
            

        if new_block.total_score > self.high_score:
            self.high_score = new_block.total_score
            self.strongest_block_hash = new_block.hash 
     

    def pop_block(self, branch: list[BlockNode]) -> int:

        """ Removes a single block from the end of the passed branch, 
            removing its reference from block_loc_dict. If the resulting
            branch is empty, removes the branch from branch list.

            Currently does not check or change high score info because it
            is only called as part of promoting branches, which won't change
            the high score or its hash. If this is ever used to remove strong
            blocks (unlikely use case), it will need to be modified to update
            scores appropriately.
            
            Args:
                branch: list. One of the branches of this BlockScoreTree object
                
            Returns:
                the block_number attribute of the popped block. Necessary to keep track of
                absolute order when rearranging the tree."""

        block = branch[-1]
        self.block_loc_dict.pop(block.hash)
        branch.pop()
        if len(branch) == 0 and branch != self.trunk:
            self.branches.remove(branch)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Tree Restructuring                                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



    def promote_to_trunk(self, better_branch: list[BlockNode]) -> list[str]:
        """ Promotes a branch repeatedly until it is the trunk. Necessary because branches may be 
            arbitrarily deep, but can only be promoted one level at a time.
            
            Args:
                better_branch: the branch of the tree being promoted to the trunk

            Returns:
                block_hash_list: a list of the hashes of every block that is newly part of
                the trunk. Important for maintaining the mempool.
        """
        
        trunk_join_index = self.get_trunk_join_index(better_branch)

        if trunk_join_index is None: #If branch is the trunk, do nothing
            block_hash_list = []
        else:
            while(better_branch != self.trunk): #Otherwise, keep promoting until we get there
                better_branch = self.promote_branch(better_branch)
            block_hash_list = [block[0] for block in self.trunk[trunk_join_index + 1:]]    

        return block_hash_list


    def promote_branch(self, better_branch: list[BlockNode]) -> list[BlockNode]:
        """ Promotes a branch to be one level closer to the trunk: the blocks in the branch become
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

        parent_hash = better_branch[0].prev_hash

        if parent_hash not in self.block_loc_dict: #make sure the reference exists before we try to follow it

            if better_branch == self.trunk: #oops, tried to promote the trunk. Do nothing
                return better_branch
            else:
                base_branch = self.trunk
                join_loc = -1 #not an error, this ensures slice in next step takes whole trunk

        else:
            base_branch, join_loc = self.block_loc_dict[parent_hash]

        #deep copy all list sections that will move
        base_branch_tip = base_branch[join_loc+1:] #string slicing is supposed to deep copy, but make sure that's true
        better_branch_copy = copy.deepcopy(better_branch)

        #Remove the ends of both branches
        for i in range(len(base_branch) - join_loc - 1):
            self.pop_block(base_branch)

        while(better_branch):
            self.pop_block(better_branch)

        #Don't add the score totals: they should be recomputed for new location
        for block in better_branch_copy:
            self.add_block(block_hash=block.hash,prev_block_hash=block.prev_hash,
                           block_score=block.block_score, block_number=block.block_number)

        for block in base_branch_tip:
            self.add_block(block_hash=block.hash,prev_block_hash=block.prev_hash,
                           block_score=block.block_score, block_number=block.block_number)

        return base_branch

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Getters and Data Access                                       |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_block(self, block_hash: str) -> BlockNode:
        if block_hash in self.block_loc_dict:
            branch, index = self.block_loc_dict[block_hash]
            block = branch[index]
        else:
            block = None
        return block

    def get_tip(self, branch: list[BlockNode]) -> BlockNode:
        """ Returns the block representation for the last block in a branch.
            Added solely for code readability elsewhere, plus some minor
            input handling.
            
            Args:
                branch: list. One of this BlockScoreTree object's branch lists.
            Returns:
                tuple: The last block representation in that branch, if the branch exists. 
                        Returns None otherwise."""
        if branch in self.branches:
            return branch[-1]
        else:
            return None

    def get_branch(self, block_hash: str) -> list[BlockNode]:
        if block_hash in self.block_loc_dict:
            return self.block_loc_dict[block_hash][0]
        else:
            return None

    def get_index(self, block_hash:str) -> int:
        if block_hash in self.block_loc_dict:
            return self.block_loc_dict[block_hash][0]
        else:
            return None
        

    def get_trunk_join_index(self,branch: list[BlockNode]) -> int:
        """ Finds the index where a branch or one of its parent branches joins the trunk, or
            determines that the branch is disconnected. 
            
            Args:
                branch: a branch

            Returns:
                index: the index of the block in the trunk where the branch or a parent branch
                        joins the trunk. Returns None if the branch is the trunk or -1 if the
                        branch is disconnected."""

        if branch == self.trunk:
            index = None
        else:
            current_branch = branch
            parent_hash = current_branch[0].prev_hash

            while(parent_hash in self.block_loc_dict):  #keep going down levels until we bottom out
                parent_branch, index = self.block_loc_dict[parent_hash]
                current_branch = parent_branch
                parent_hash = current_branch[0].prev_hash

            if(current_branch != self.trunk): #Did we bottom out at the trunk? If not, we're on a disconnected branch
                index = -1

        return index
    

				
    def is_in_trunk(self, block_hash: str) -> bool:
        """ Returns true if the block hash corresponds to an entry in the
            trunk. Returns false otherwise."""
        if block_hash in self.block_loc_dict:
            block_branch = self.get_branch(block_hash)
            if block_branch == self.trunk:
                return True

        return False

    def get_path_to_trunk(self, block_hash: str):
        """ Takes a block hash and returns a list of the hash of every block between that block and the trunk.
            If the block is in the trunk it will return an empty list.
        
            Args:
                block_hash: the hash of a block
            Returns:
                path_hash_list: a list containing all the hashes between the identified block and the trunk"""

        #TODO think carefully about desired behavior in this case
        if self.get_trunk_join_index(self.block_loc_dict[block_hash][0]) == -1:
            return None 

        path_hash_list = []
        current_block_hash = block_hash

        while (not self.is_in_trunk(current_block_hash)):
            path_hash_list.append(current_block_hash)
            current_block_hash = self.get_block(current_block_hash).prev_hash

        return path_hash_list     

    def write_to_file(self,filename: str, truncate: bool = True):
        short_hash_len = self.short_hash_len
        if not truncate:
            self.short_hash_len = len(self.trunk[-1].hash)
        with open(filename, "w") as file_obj:
            file_obj.write(str(self))

        if not truncate:
            self.short_hash_len = short_hash_len

    def write_to_file_json(self,filename: str):
        with open(filename, "w") as f:
            json.dump(self.branches, f)

    @staticmethod
    def load_from_json_file(filename):
        new_tree = BlockScoreTree()
        with open(filename, 'r') as f:
            tree_data = json.load(f)
        for branch in tree_data:
            for element in branch:
                new_tree.add_block(block_hash=element[0], prev_block_hash=element[1], block_score=float(element[2]), 
                                   canonical=bool(float(element[2])>0), block_number=element[4])

        return new_tree

	
