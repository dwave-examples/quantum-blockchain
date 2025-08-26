
import math
import os
import json

from src.common.block_score_tree import BlockScoreTree

def load_dags(dag_directory: str, dag_file_prefix: str, cutoff: int = None):
    """ This function loads the node data from a collection of BlockScoreTree files and
        re-instantiates them into objects. Intended use is to processes input from multiple
        miners into an overall Directed Acyclic Digraph (dag) representing the state of the
        blockchain. Most of that functionality is handled in combine_dags, this just prepares
        the data."""
    
    #TODO consider making this a class method, either of BlockScoreTree or of new class (if/when it's written)

    loaded = 0
    dag_list = []
    if os.path.exists(dag_directory):
        while(True):
            current_file = dag_file_prefix + str(loaded) + '.json'
            filepath = os.path.join(dag_directory, current_file)
            if os.path.exists(filepath):
                if cutoff:
                    new_dag = BlockScoreTree.load_from_json_file(filepath, cutoff)
                else:
                    new_dag = BlockScoreTree.load_from_json_file(filepath)
                dag_list.append(new_dag)
                loaded += 1
            else:
                if loaded == 0:
                    Exception("Directory Contains no DAG files!")
                else:
                    break
    else:
        Exception("Directory Not Found!")

    return dag_list

def combine_dags(dag_list: list[BlockScoreTree]):
    """ This function takes a list of BlockScoreTree objects--assumed to represent the same blockchain
        at the same time--and processes them to created a composite Directed Acyclic Digraph (dag) representing
        the modal beliefs contained in those tree. It does not examine or interact with the assigned scores in any
        way, it only considers how many of the graphs have the block in their trunk.
        
        Args:
            dag_list: list of BlockScoreTree objects from whose digraph structure will be examined
            
        returns:
            composite_dag: A BlockScoreTree object with graph structure matching the composite of all input graphs
            mining_nodes: A list of nodes that are currently at the tip of at least one tree's trunk"""
    
    reference_dag = dag_list[0]
    composite_dag = BlockScoreTree()
    mining_nodes = set()
    for branch in reference_dag.branches:
        for block in branch:
            times_in_trunk = 0 
            for i in range(len(dag_list)):
                dag = dag_list[i]
                times_in_trunk += int(dag.is_in_trunk(block.hash))
                if dag.trunk[-1].hash == block.hash: 
                    mining_nodes.add(block.hash)

            composite_dag.add_block(block_hash=block.hash, prev_block_hash=block.prev_hash, 
                                    block_score=times_in_trunk, canonical=bool(times_in_trunk > 0), block_number=block.block_number)

    for branch in composite_dag.branches:
        if branch[-1].total_score > composite_dag.trunk[-1].total_score:
            composite_dag.promote_to_trunk(branch)
                     
    return composite_dag, mining_nodes

def assign_branch(branch_dict, branch_arrangement, max_depth, root_depth, errors_filename, parent_root_depth = 0):
    """ 
    Arg requirements:
        Needs a correctly formatted dict. In particular, must have:
    """
    #check if branch arrangment is the correct shape

    lower = branch_dict["root"]
    upper = branch_dict["map"][-1] + 1

    if root_depth == 0: #if we start from the trunk, we just alternate on either side. Only trick is determining starting direction.
        upper_weight = sum([2 in row[lower:upper] for row in branch_arrangement[1:max_depth+1] ]) #Check which direction has the least stuff in the way...
        lower_weight = sum([2 in row[lower:upper] for row in branch_arrangement[max_depth+1:] ]) #...and go in that direction...
        direction = 2*int(upper_weight < lower_weight) - 1                                       #...breaking ties towards the inside.
        depths = [-direction*i//2 if i%2 else direction*(i+1)//2 for i in range(1, 2*max_depth+1)] #Counts up depths with alternating sign

    else: #starting from a branch is more complicated than starting from the trunk
        direction = 2*int(root_depth>0)-1
        out_lim = direction*(max_depth+1)
        depths = [i for i in range(root_depth, out_lim, direction)] #if we only go outward, it's easy

        if len(branch_dict["children"])==0: #but if we go inward, we have different amounts of space in different directions
            in_step = -direction
            inner_depths = [i for i in range(root_depth + in_step, parent_root_depth, in_step)] #available depths in the inward direction: can't cross parent branch.
            new_depths = [] #yes, we have sunk that low
            for items in zip(inner_depths, depths):
                new_depths.extend(items)
            if len(depths) > len(inner_depths):
                new_depths.extend(depths[len(inner_depths)+1:])
            elif len(inner_depths) > len(depths):
                new_depths.extend(inner_depths[len(depths)+1:])
            depths = new_depths   

    assigned = False
    last_depth = None

    for depth in depths: 
        last_depth = depth
        if 1 not in branch_arrangement[depth][lower:upper] and 2 not in branch_arrangement[depth][lower:upper]:
            assigned = True
            for i in range(lower+1,upper): 
                branch_arrangement[depth][i] = 1 #Mark spaces containing a branch with a "1"
            for i in range(root_depth, depth, 2*int(depth < root_depth)-1): 
                branch_arrangement[i][lower] = 2 #And connections from branch-to-trunk with a 2
            branch_dict.update({"depth": depth})
            branch_dict.update({"root_depth": root_depth})
            break

    if not assigned:
        with open(errors_filename, 'w') as f:
            f.write(f"Map: {branch_dict["map"]}...Root {branch_dict["root"]}...Root Depth: {root_depth}...Start Dir {direction}...Max Depth {max_depth}...Cur Depth {last_depth}")
            children = [child for child in branch_dict["children"]]
            chln = 0
            while True:
                if len(children) > 0 and chln < 99: #should not have too many children. Limit loop just in case.
                    n_child = children.pop(0)
                    chln += 1
                    f.write(f"Child {chln} ...Map: {n_child["map"]}...Root {n_child["root"]}")
                    for child in n_child["children"]:
                        children.append(child)
                else:
                    break
        return direction

    for child in branch_dict["children"]:
        assign_branch(branch_dict=child, branch_arrangement=branch_arrangement, max_depth=max_depth, 
                      root_depth=branch_dict["depth"], errors_filename=errors_filename, parent_root_depth=root_depth)


def generate_graph_data(tree: BlockScoreTree, errors_filename, data_filename=None, map_filename=None):
    """ dfd
        Returns: 
            branch_maps[dict] a list of dict objects, one for each branch
            in the BlockScoreTree. The dict objects will contain the 
            following entries
            {
            root: block_number of the branch point (in the branch's parent branch)
            map: a list of the block_number of each block in the branch, in order
            depth: signed integer ..
            slant: boolean indicating whether the conncetion from the branch to its parent
            }

    """

    num_nodes = len(tree.hash_to_branch_lookup)
    trunk_map = [node.block_number for node in tree.trunk]
    branches = [branch for branch in tree.branches if branch.root is not None]
    branches.sort(key= lambda x: num_nodes - x.root.block_number)
    branch_data = []
    trunk_dict = {"map": trunk_map, "depth": 0, "root": 0, "root_depth": 0, "soundness": tree.trunk.get_soundness_map(tree.high_score, trunk=True)}

    for branch in branches:
        branch_dict = {"root": branch.root.block_number}
        branch_map = [node.block_number for node in branch]
        branch_dict.update({"map": branch_map})
        branch_dict.update({"children": []})
        branch_dict.update({"soundness": branch.get_soundness_map(tree.high_score)})
        branch_data.append(branch_dict)

    primary_branches = []
    current_level_branches = []
    remaining_branches = []

    for branch_dict in branch_data:
        if branch_dict["root"] in trunk_map:
            primary_branches.append(branch_dict)
            current_level_branches.append(branch_dict)
        else:
            remaining_branches.append(branch_dict)

    for i in range(len(remaining_branches)):
        placed = []
        unplaced = []
        while remaining_branches:
            child = remaining_branches.pop(0)
            unplaced.append(child)
            for parent in current_level_branches:
                if child["root"] in parent["map"]:
                    parent["children"].append(child)
                    placed.append(child)
                    unplaced.remove(child)
                    break
        if len(unplaced) > 0:
            current_level_branches = placed
            remaining_branches = unplaced
        else:
            break


    num_branches = len(branch_data)
    max_depth = math.ceil(num_branches/2)

    branch_arrangement = [[int(j==0) for i in range(num_nodes+1)] for j in range(2*max_depth + 1)]
    
    for branch in primary_branches:
        assign_branch(branch_dict=branch, branch_arrangement=branch_arrangement,
                                max_depth=max_depth, root_depth=0, errors_filename=errors_filename)

    if data_filename:
        with open(data_filename, 'w') as f:
            out_data = json.dumps(trunk_dict) + "\n"
            for datum in branch_data:
                out_data += json.dumps(datum) + "\n"
            f.write(out_data)
    
    if map_filename:   
        with open(map_filename, 'w') as f:
            for i in range(2*max_depth+1):
                if 1 in branch_arrangement[max_depth - i]:
                    f.write(f"{max_depth-i}: {branch_arrangement[max_depth - i]} \n")
        
    for branch_dict in branch_data:
        assert -max_depth <= branch_dict["depth"] <= max_depth, f"Branch with root {branch_dict["root"]} improperly assigned depth {branch_dict["depth"]}"
        branch_dict.pop("children")

    return trunk_dict, branch_data



    