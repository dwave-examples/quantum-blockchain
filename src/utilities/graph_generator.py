import sys, os, argparse
from typing import Optional

CUR_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CUR_DIR, "..", ".."))

from src.structures.block_score_tree import BlockScoreTree
from src.utilities.dag_tools import load_dags, combine_dags

import src.utilities.plotting as plotting
import networkx as nx


def graph_gen_main(
    directory: str,
    edge_list: Optional[list] = None,
    node_list: Optional[list] = None,
    save_as: str = None,
    use_spiral: bool = True,
    miner_index: int = None,
    cutoff: int = None,
):
    """Wraps plotting.plot_graph for purposes of spiral plotting. Calls
        function from dag_tools.py to retrieve and (if necessary) combine
        data from miner's blockchian graphs, then rearranges and reformats
        it to match what plotting.py expects and adds node label info.
        Then calls plot_graph from plotting.py to generate graph.

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
        miner_index: Index of the miner whose chain is to be graphed.
                  Defaults to None, which will create a composite graph
                  of all miners instead.
        cutoff (int): only graph blocks up to this block number. If
        at default value of -1, will graph all blocks in the tree


    """
    file_prefix = "dag_"
    node_label_spacing = 10  # How often to label nodes. Every 10th node tends to look good.

    if edge_list is None:
        if cutoff:
            dag_list = load_dags(directory, file_prefix, cutoff)
        else:
            dag_list = load_dags(directory, file_prefix)
        if miner_index is not None:
            working_dag = dag_list[miner_index]
            active_blocks = {working_dag.trunk[-1].hash}
        else:
            composite_dag, active_blocks = combine_dags(dag_list)
            working_dag = composite_dag

        block_list = []
        for branch in working_dag.branches:
            for block in branch:
                block_list.append(block)

        block_list.sort(key=lambda x: x.block_number)

        edge_list = [
            (node.hash, node.prev_hash) for node in block_list if node.prev_hash is not None
        ]
        node_list = [edge_list[0][1]]
        for edge in edge_list:
            node_list.append(edge[0])

        node_labels = {}
        for block in block_list:
            if block.hash in node_list and (block.block_number % node_label_spacing == 0):
                node_labels.update({block.hash: block.block_number})

    else:
        node_labels = None
        active_blocks = None

    if node_list is None:
        # Failed branches are plotted at the spiral center by default,
        # since the edge order determines the spiral order.
        # Visualization so far considered use temporal ordering (with
        # network synchronization.)
        G = nx.from_edgelist(edge_list, nx.DiGraph)
    else:
        G = nx.Graph()
        G.add_nodes_from(
            node_list
        )  # Graph nodes are ordered, this determines placement in the spiral.
        G.add_edges_from(edge_list)
    # It's amazing plot_graph runs at all! I'll try to fix it later (once we want
    # to draw chains with multiple miners (later).

    plotting.plot_graph(G, save_as=save_as, labels=node_labels, active_blocks=active_blocks)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--directory", type=str, help="Output directory", default=None)
    parser.add_argument(
        "-C", "--cutoff", type=int, help="Latest block that will be used in the graph", default=None
    )

    args = parser.parse_args()

    dags_directory = os.path.join(CUR_DIR, "output", args.directory, "miner_dags")
    cutoff = args.cutoff

    graph_gen_main(dags_directory, cutoff=cutoff)
