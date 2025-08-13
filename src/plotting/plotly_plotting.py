from typing import Union
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import json, os
import plotly.express as px

def get_predecessors(directed_tree: nx.DiGraph, val, root=None):
    """Return all predecessors
    directed_Tree: blockdirected_tree
    v: node
    """
    #if root is None:
    #    root = list(directed_tree)[0]
    predecessors = [val]
    while val != root:
        try:
            val = next(directed_tree.predecessors(val))
        except StopIteration:
            if root is None:
                return predecessors
            else:
                raise ValueError('root is provided, but not reached - DiGraph is ill defined')
        predecessors.append(val)
    return predecessors


def common_predecessors(directed_tree: nx.DiGraph, *, nodes):
    """ Given a digraph and a set of graph nodes, constructs a set of predecessors for
    each node and returns the intersection and the union of those sets.

    Args:
        -directed_tree: an nx.DiGraph object
        -nodes: a set or list of digraph nodes

    Returns:
        -intersection_predecessors: the set of nodes that is a predecessor of every node in
        the input list
        -union_predecessors: the set of nodes that is a predecessor of any node in the input list
    """
    
    predecessor_sets = [set(get_predecessors(directed_tree, node)) for node in nodes]
    union_predecessors = set()
    intersection_predecessors = set(predecessor_sets[0])
    for item in predecessor_sets:
        union_predecessors = union_predecessors.union(item)
        intersection_predecessors = intersection_predecessors.intersection(item)

    return intersection_predecessors, union_predecessors

def to_directed(G: nx.Graph):
    DG = nx.DiGraph()
    DG.add_nodes_from(G.nodes())
    DG.add_edges_from(G.edges())
    return DG

def plot_graph(G: Union[nx.Graph,nx.DiGraph], save_as: str, labels = None, active_blocks: dict = None):
    """This function plots a graph with the given nodes and edges. It will plot
    the strongest path in a horizontal line and the branches in vertical lines.


    Args:
        G (nx.Graph): The graph to plot, with colored edges, weights, and node labels.
        strongest_edge_color (str, optional): The color of the strongest path edges. The
            input graph, G, should have the edge attribute 'color' set to this color. Every
            other edge will be drawn vertically in the plot and colored according to its
            color attribute
        show (bool, optional): Whether to show the plot. Defaults to True.
        active_blocks (dict, optional): A list of mined nodes, with number of miners.
    """

    if active_blocks is not None:
        nx.set_node_attributes(G, values={n: 'black' for n in active_blocks}, name='color')
    elif G.number_of_nodes()>0:
        G.nodes[list(G.nodes())[-1]]['color'] = 'black'
        active_blocks = {node for node in G.nodes if G.nodes[node]['color']=='black'}

    if len(active_blocks) >= 1:
        ns, ns2 = common_predecessors(to_directed(G), nodes=active_blocks)
    else:
        ns = set()
        ns2 = set()
    nx.set_node_attributes(G, name='color', values='#FF7006')
    nx.set_node_attributes(G, {n: {"color": "#888888"} for n in ns2})
    nx.set_node_attributes(G, {n: {"color": "#2a7de1"} for n in ns})
    nx.set_node_attributes(G, {n: {"color": "black"} for n in active_blocks})
    nx.set_edge_attributes(G, {e: {"color": G.nodes[e[1]]['color']} for e in G.edges()})
        
    node_colors = [G.nodes[node]['color'] for node in G.nodes]
    colors = nx.get_edge_attributes(G, 'color').values()
    fig, ax = plt.subplots()

    pos = nx.spiral_layout(G.nodes(), scale=1, center=(0.5,0.5), dim=2, resolution=np.pi/16, equidistant=False)
    if labels:
        nx.draw(G, pos, edge_color=colors, node_size=np.arange(1, G.number_of_nodes()+1)/G.number_of_nodes()*100, 
                    node_color=node_colors, ax=ax, with_labels=True, labels=labels)
    else:
        nx.draw(G, pos, edge_color=colors, node_size=np.arange(1, G.number_of_nodes()+1)/G.number_of_nodes()*100, 
                    node_color=node_colors, ax=ax)
  
        
    ax.set_aspect('auto')
    plt.tight_layout()
    return fig

    plt.savefig(save_as)
    plt.close()