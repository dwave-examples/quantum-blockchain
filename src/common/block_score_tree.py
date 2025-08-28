import json

from src.common.score_tree_branch import ScoreTreeBranch, BlockNode

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Initialization and Special Methods                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
		
        self.trunk = ScoreTreeBranch()
        self.hash_to_branch_lookup = {}
        self.branches = [self.trunk]
        self.high_score = -9999999 #Should be replaced by something the moment a block is added.
        self.strongest_block_hash = None
        self.short_hash_len = 3 #property because it's primarily used in __str__ which shouldn't take input paramters.
                                #should set to desired value before __str__ is called

    def __str__(self): #TODO consider moving into ScoreTreeBranch

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

    def score_predicate(self, block_score): #TODO add argument to constructor allowing this to be changed
        return bool (block_score > 0)


    def add_block(self, block_hash: str, prev_block_hash: str, block_score: float, block_number: int = -1):

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

        if block_hash in self.hash_to_branch_lookup: 
            raise Exception("Duplicate Block!")
        
        #By default, block number is one more than the number of blocks already in the tree. However, when re-arranging
        #the tree it's necessary to pass in the existing block number instead.
        if block_number < 0:
            block_number = len(self.hash_to_branch_lookup) + 1 

        #A block whose predecessor isn't in the tree is added as the first block of the trunk, if the trunk is empty
        if prev_block_hash not in self.hash_to_branch_lookup:
            if len(self.trunk)==0:
                new_block = BlockNode(hash=block_hash, prev_hash=prev_block_hash, block_score=block_score, 
                                  total_score=block_score, block_number=block_number, block_height=0) #TODO check if height should start at 0
                self.trunk.append_block(new_block)
                self.hash_to_branch_lookup.update({block_hash:self.trunk})
            else:
                raise Exception("Block has no predecessor in the tree!")

        #A block whose predecessor is found is added to the tree in the proper spot
        else:          
            pred_branch = self.hash_to_branch_lookup[prev_block_hash]
            prev_block = pred_branch.get_block(prev_block_hash)
            new_block = BlockNode(hash=block_hash, prev_hash=prev_block_hash, block_score=block_score, total_score=block_score + prev_block.total_score, 
                                  block_number=block_number, block_height=prev_block.block_height+1)
            
            canonical = (pred_branch != self.trunk) or self.score_predicate(block_score) #If the block isn't going in the trunk, score is unimportant.
                                                                                        #If it is, we need to check that its score meets our criterion
            
            if prev_block == pred_branch.tip and canonical: #Block goes on branch tip
                pred_branch.append_block(new_block)
                self.hash_to_branch_lookup.update({block_hash: pred_branch})
            else: #Block goes in new branch
                new_branch = ScoreTreeBranch(new_block)
                self.branches.append(new_branch)
                self.hash_to_branch_lookup.update({block_hash:new_branch})
                pred_branch.link_child_branch(new_branch)
            

        if new_block.total_score > self.high_score:
            self.high_score = new_block.total_score
            self.strongest_block_hash = new_block.hash 

    def add_block_as_node(self, block: BlockNode):

        if block.hash in self.hash_to_branch_lookup: 
            raise Exception("Duplicate Block!")

        #A block whose predecessor isn't in the tree is added as the first block of the trunk if the trunk is empty
        if block.prev_hash not in self.hash_to_branch_lookup:
            if len(self.trunk) == 0:
                self.trunk.append_block(block)
                self.hash_to_branch_lookup.update({block.hash:self.trunk})
            else:
                raise Exception("Block has no predecessor in the tree!")

        #A block whose predecessor is found is added to the tree in the proper spot
        else:          
            pred_branch = self.hash_to_branch_lookup[block.prev_hash]
            prev_block = pred_branch.get_block(block.prev_hash)

            canonical = (pred_branch != self.trunk) or self.score_predicate(block.block_score) #If the block isn't going in the trunk, score is unimportant.
                                                                                        #If it is, we need to check that its score meets our criterion

            if prev_block == pred_branch.tip and canonical: #Block goes on branch tip
                pred_branch.append_block(block)
                self.hash_to_branch_lookup.update({block.hash:pred_branch})
            else: #Block goes in new branch
                new_branch = ScoreTreeBranch(block)
                self.branches.append(new_branch)
                self.hash_to_branch_lookup.update({block.hash: new_branch})
                pred_branch.link_child_branch(new_branch) 
            

        if block.total_score > self.high_score:
            self.high_score = block.total_score
            self.strongest_block_hash = block.hash 

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Tree Restructuring                                            |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



    def promote_to_trunk(self, better_branch: ScoreTreeBranch) -> list[str]:
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
            block_hash_list = [block.hash for block in self.trunk[trunk_join_index + 1:]]    

        return block_hash_list


    def promote_branch(self, better_branch: ScoreTreeBranch) -> ScoreTreeBranch:
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


        if better_branch.depth > 0 and better_branch.predecessor is not None:
            base_branch = better_branch.predecessor
            orig_len = len(base_branch)
            prom_len = len(better_branch)
            total_len = orig_len + prom_len
            join_loc = base_branch.hash_to_index_lookup[better_branch.root_hash] + 1 #Leave the root block in place, remove the next block
            for block in better_branch:
                self.hash_to_branch_lookup.update({block.hash:base_branch})
            base_branch.children.remove(better_branch)
            self.branches.remove(better_branch)   
            if join_loc < base_branch.tip_idx+1:
                demoted_section = base_branch.cut_branch_section(join_loc)
                self.branches.append(demoted_section) 
                for block in demoted_section:
                    self.hash_to_branch_lookup.update({block.hash: demoted_section})
                base_branch.link_child_branch(demoted_section)
                dem_len = len(demoted_section)
            else:
                dem_len = 0
            base_branch.concatenate_branch(better_branch)
            assert len(base_branch) + dem_len == total_len, f"Lost some blocks! Demoted: {dem_len}, promoted: {prom_len}, Orig: {orig_len}, Final {len(base_branch)}"
            return base_branch
        elif better_branch == self.trunk: #If we try to promote the trunk, nothing happens
            return better_branch
        else: 
            raise Exception("Branch has depth 0 but is not the trunk!")

    
    def refactor_branches(self):
        """ This function rearranges the branches of the tree to put branches with the highest final block number
            at the lowest level. In this structure, trunk has special importance, but outside of that, which branch
            is a parent and which is a child is arbitrary: promote_branch lets us swap between them at will. For graphing
            it is useful to have the branches that will appear longest on the trunk (those that end with the highest block number)
            to have the lowest depth. This function rearranges the branches to meet that criterion.
            
            #TODO extend this function to allow refactoring by total score or block height instead, or by arbitrary
            functions of the same, each of which could be useful in different applications. (doing this cleanly likely needs
            higher-order-functions)"""
        base_branches = []
        for branch in self.branches:
            if branch.depth == 1:
                base_branches.append(branch)
        
        for base_branch in base_branches:
            branch_descendants = base_branch.get_descendants_by_depth()
            
            for i in range(len(branch_descendants)-1, 0, -1): #Working from the highest depth to the lowest lets us make only one pass
                layer = branch_descendants[i]
                layer_remaining = {bch.base.hash for bch in layer} #We'll create the longet (by last block number) branch at that layer we can
                for branch in layer:                              #Which will ensure that one pass over the next lowest layer is also optimal
                    if branch.depth <= 1: #Want to stop just short of the bottom branch.
                        break
                    if branch.base.hash in layer_remaining:
                        parent = branch.predecessor
                        best_child = branch
                        best_block_num = branch.tip.block_number
                        for child in parent.children: 
                            layer_remaining.remove(child.base.hash) #Remove each child as we check it
                            if child.tip.block_number > best_block_num:
                                best_child = child 
                                best_block_num = child.tip.block_number 
                        if best_block_num > parent.tip.block_number: #If any children have a higher block number than the parent
                            self.promote_branch(best_child) #Promote the 
                    if len(layer_remaining) == 0:
                        break


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#=====================================================================================================
#                             SECTION: Getters and Data Access                                       |
#=====================================================================================================
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def get_block(self, block_hash: str) -> BlockNode:
        if block_hash in self.hash_to_branch_lookup:
            return self.hash_to_branch_lookup[block_hash].get_block(block_hash)
        else:
            return None


    def get_trunk_join_index(self,branch: ScoreTreeBranch) -> int:
        """ Finds the index where a branch or one of its parent branches joins the trunk.
            
            Args:
                branch: a branch

            Returns:
                index: the index of the block in the trunk where the branch or a parent branch
                        joins the trunk. Returns None if the branch is the trunk."""

        current_branch = branch
        root_hash = None
        while(current_branch.predecessor is not None):
            root_hash = current_branch.root_hash 
            current_branch = current_branch.predecessor

        assert current_branch == self.trunk, "No path found from branch to trunk."
        ""          
        if root_hash is None: #If we never set our root hash, we must have started at the trunk
            index = None
        else:
            index = self.trunk.hash_to_index_lookup[root_hash]

        return index
    

	#TODO revise or replace (miner, dag_tools, graph_processor)		
    def is_in_trunk(self, block_hash: str) -> bool:
        """ Returns true if the block hash corresponds to an entry in the
            trunk. Returns false otherwise."""

        return (self.hash_to_branch_lookup[block_hash] == self.trunk)

    #TODO Doesn't seem to get used anywhere? Check other repo.
    def get_path_to_trunk(self, block_hash: str):
        """ Takes a block hash and returns a list of the hash of every block between that block and the trunk.
            If the block is in the trunk it will return an empty list.
        
            Args:
                block_hash: the hash of a block
            Returns:
                path_hash_list: a list containing all the hashes between the identified block and the trunk"""

        #TODO think carefully about desired behavior in this case
        if self.get_trunk_join_index(self.hash_to_branch_lookup[block_hash][0]) == -1:
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
            self.short_hash_len = len(self.trunk.tip.hash)
        with open(filename, "w") as file_obj:
            file_obj.write(str(self))

        if not truncate:
            self.short_hash_len = short_hash_len

    def write_to_file_json(self,filename: str):
        with open(filename, "w") as f:
            branches = [b.node_list for b in self.branches]
            json.dump(branches, f)

    @staticmethod
    def json_to_blocknode(node_as_list) -> BlockNode:
        block_hash = node_as_list[0]
        prev_hash = node_as_list[1]
        score = node_as_list[2]
        tot_score = node_as_list[3]
        number = node_as_list[4]
        height = node_as_list[5]
        return BlockNode(block_hash, prev_hash, score, tot_score, number, height)

    @staticmethod
    def load_from_json_file(filename: str, cutoff: int=-1):
        """ Given an appropriately formatted file, loads a BlockScoreTree object.
            Ought to keep the same graph structure and scores under realistic circumstances
            (but this is diffuclt to guarantee in all cases). If provided a positive value for 
            cutoff parameter, will reconstruct the graph block by block so that the scores and 
            structure can be re-calculated to match the older graph state (rather than using)
            the structural info from the current version of the graph.

            Args:
                filename: the name of the file (including path) containing the graph info
                cutoff: how many blocks of the graph to reconstruct. If left at -1, will
                reconstruct the whole graph, and used the saved structural information to
                determine the new graph structure.
        """ 
    
        new_tree = BlockScoreTree()
        with open(filename, 'r') as f:
            branch_list = json.load(f)

        node_list = []
        new_branch_list = []
        for branch in branch_list:
            branch_nodes = []
            for element in branch:
                new_node = BlockScoreTree.json_to_blocknode(element)
                node_list.append(new_node)
                branch_nodes.append(new_node)
            new_branch_list.append(branch_nodes)

        if cutoff > 0:
            node_list.sort(key= lambda x: x.block_number)
            for i in range(cutoff):
                node = node_list[i]
                if node.block_number <= cutoff:
                    new_tree.add_block(node.hash, node.prev_hash, node.block_score)
                    if new_tree.high_score > new_tree.trunk.tip.total_score:
                        new_tree.promote_to_trunk(new_tree.hash_to_branch_lookup[node.hash])
        else:
            for branch in new_branch_list: #TODO double-check
                for element in branch:
                    if element == branch[0] and branch != new_branch_list[0]:
                        new_tree.add_block_as_node(element)
                    else:
                        new_tree.add_block_as_node(element)
            for branch in new_tree.branches:  #TODO check if this is disarable and necessary
                if branch.tip.total_score > new_tree.high_score:
                    new_tree.promote_to_trunk(branch)

        return new_tree


	
