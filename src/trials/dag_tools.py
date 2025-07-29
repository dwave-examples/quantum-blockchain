import json
import os

from src.common.block_score_tree import BlockScoreTree

#TODO define a subclass of BlockScoreTree to use in cases like this where they're not integrated with
#active blockchains and the scoring functionality is not being used. This is a different use-case
#that happens to depend on (only certain parts of) the same structure, and should be clearly marked as such.
def load_dags(dag_directory: str, dag_file_prefix: str):
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
                new_dag = BlockScoreTree.load_from_json_file(filepath)
                dag_list.append(new_dag)
                loaded += 1
            else:
                break
    else:
        Exception("Directory Not Found!")

    return dag_list

def combine_dags(dag_list: list[BlockScoreTree]):
    """ This function takes a list of BlockScoreTree objects--assumed to represent the same blockchain
        at the same time--and processes them to created a composite Directed Acyclic Digraph (dag) representing
        the modal beliefs contained in those tree. It does not examine or interact with the assigned scores in any
        way, it only considers how many of the graphs have the block in their trunk."""
    reference_dag = dag_list[0]
    composite_dag = BlockScoreTree()
    for branch in reference_dag.branches:
        for block in branch:
            block_hash = block[0]
            times_in_trunk = int(reference_dag.is_in_trunk(block_hash))
            for dag in dag_list:
                if dag != reference_dag:
                    times_in_trunk += int(dag.is_in_trunk(block_hash))
            composite_dag.add_block(block_hash=block_hash, prev_block_hash=block[1], block_score=times_in_trunk, canonical=bool(times_in_trunk > 0))

    for branch in composite_dag.branches:
        if branch[-1][3] > composite_dag.trunk[-1][3]:
            composite_dag.promote_to_trunk(branch)
                     
    return composite_dag

