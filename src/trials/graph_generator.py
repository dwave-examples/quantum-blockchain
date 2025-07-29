import sys, os, argparse
from typing import Optional

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CUR_DIR, '..', '..'))

from src.common.block_score_tree import BlockScoreTree
from src.trials.dag_tools import load_dags, combine_dags

import src.plotting.plotting as plotting
import networkx as nx

def graph_gen_main(
    directory: str,
    edge_list: Optional[list] = None,
    node_list: Optional[list] = None,
    save_as: str =None,
    use_spiral: bool =True,
    miner: int = None
):
    """Wraps plotting.plot_graph for purposes of spiral plotting.

    Args:
        directory: directory from which to draw data.
        edge_list: edges defining the directed graph. The
            [(ancestor, descendant)]. This will be inferred
            from directory data when not provided.
        node_list: nodes defining the directed graph. The
            ordering determines placement on the spiral. This
            is inferred from edge_list when not provided.
        save_as: filename for saving the graph. If not provided
            the file is displayed.
        use_spiral: use_spiral rather than linear plotting format.

    """
    file_prefix = "dag_"

    if edge_list is None:
        dag_list = load_dags(directory, file_prefix)
        if miner and miner < len(dag_list):
            working_dag = dag_list[miner]
        else:
            composite_dag = combine_dags(dag_list)
            working_dag = composite_dag

        block_list =[]
        for branch in working_dag.branches:
            for block in branch:
                block_list.append(block)

        block_list.sort(key= lambda x: x.block_number)
        node_list = [node.hash for node in block_list]
        node_order = {block.hash:block.block_number for block in block_list if block.block_number % 10 == 0}

        edge_list = [(node.hash, node.prev_hash) for node in block_list if node.block_height > 0] 
    else:
        node_order = None

    if node_list is None:
        # Failed branches are plotted at the spiral center. By default
        # since the edge order determines the spiral order.
        # Visualization so far considered use temporal ordering (with
        # network synchronization.
        G = nx.from_edgelist(edge_list, nx.DiGraph)
    else:
        G = nx.Graph()
        G.add_nodes_from(
            node_list
        )  # Graph nodes are ordered, this determines placement in the spiral.
        G.add_edges_from(edge_list)
    # It's amazing plot_graph runs at all! I'll try to fix it later (once we want
    # to draw chains with multiple miners (later).
    
    plotting.plot_graph(G, save_as=save_as, show=(save_as is None), use_spiral=True, labels=node_order)
   


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-D", "--directory", type=str, help="Output directory", default=None
    )
    args = parser.parse_args()


    dags_directory = os.path.join(CUR_DIR, "output", args.directory, "miner_dags")

    graph_gen_main(dags_directory)