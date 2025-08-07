import json
import os

from src.common.block_score_tree import BlockScoreTree

#TODO define a subclass of BlockScoreTree to use in cases like this where they're not integrated with
#active blockchains and the scoring functionality is not being used. This is a different use-case
#that happens to depend on (only certain parts of) the same structure, and should be clearly marked as such.
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

