from typing import Union
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

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
    """Two validators determine strongest chains. Find their last common predecessor

    If with high probability any two independent validators agree at depth D,
    then transactions at depth D or more can be considered secure. It is essential
    that D is finite, and small for practical purposes.

    directed_tree: blocktree
    P: block failure rate (ignored if node attributes)
    """
    predecessors = get_predecessors(directed_tree, nodes[0])
    union_predecessors = set(predecessors)
    for n in nodes[1:]:
        new_path = set(get_predecessors(directed_tree, n))
        union_predecessors.update(new_path)
        while predecessors[-1] not in new_path:
            predecessors.pop()
    return predecessors, union_predecessors


def to_directed(G: nx.Graph):
    DG = nx.DiGraph()
    DG.add_nodes_from(G.nodes())
    DG.add_edges_from(G.edges())
    return DG

def plot_graph(G: Union[nx.Graph,nx.DiGraph], strongest_edge_color='blue',
               show: bool=True, save_as: str=None, scale: int=1, use_spiral=True, recolor_jack=True, 
               miner_on_last_node=True, strongest_node=None, labels = None) -> None:
    """This function plots a graph with the given nodes and edges. It will plot
    the strongest path in a horizontal line and the branches in vertical lines.


    Args:
        G (nx.Graph): The graph to plot, with colored edges, weights, and node labels.
        strongest_edge_color (str, optional): The color of the strongest path edges. The
            input graph, G, should have the edge attribute 'color' set to this color. Every
            other edge will be drawn vertically in the plot and colored according to its
            color attribute
        show (bool, optional): Whether to show the plot. Defaults to True.
        save_as (str, optional): The path to save the plot. Defaults to None.
    """
    edges = G.edges()
    try:
        colors = [G[u][v]['color'] for u, v in edges]
    except:
        strongest_node = list(G.nodes())[-1]
        predecessors = get_predecessors(to_directed(G), strongest_node)
        colorsN = {n: 'red' for n in G.nodes()}
        colorsN.update({n: 'blue' for n in predecessors})
        #colorsN.update({strongest_node: 'black'})
        nx.set_node_attributes(G, name='color', values=colorsN)
        nx.set_edge_attributes(G, name='color', values={e: colorsN[e[1]] for e in G.edges()})
        colors = [colorsN[e[1]] for e in G.edges()]
        
    node_colors = ['red' for node in G.nodes]
    for node in G.nodes:
        G.nodes[node]['color'] = 'red'
    try:
        weights = [G[u][v]['weight'] * 3 * scale for u, v in edges]
    except:
        weights = [1]*len(edges)
    straight_line_edges = [list(edges)[idx] for idx,color in enumerate(colors) if color == strongest_edge_color]
    branch_edges = [list(edges)[idx] for idx,color in enumerate(colors) if color != strongest_edge_color]
    node_labels = nx.get_node_attributes(G, 'label')
    
    
    positions = {}
    last_pos_x = 0
    diff = 1 * scale
    for (start, end) in straight_line_edges:
        positions[start] = (last_pos_x, diff)
        last_pos_x += diff
        positions[end] = (last_pos_x, diff)
        #color the nodes on the strongest path in blue
        G.nodes[start]['color'] = 'blue'
        G.nodes[end]['color'] = 'blue'
    
    for (start, end) in branch_edges:
        try:
            last_pos_x = positions[start][0]
        except KeyError:
            continue
        last_pos_y = positions[start][1] + diff
        G.nodes[end]['color'] = G.edges[(start, end)]['color']
        while (last_pos_x, last_pos_y) in positions.values():
            last_pos_x += diff
        positions[end] = (last_pos_x, last_pos_y)
    
    #don't display any node with no position in the first row
    to_remove = []
    for node in G.nodes:
        if node not in positions:
            to_remove.append(node)
    for node in to_remove:
        G.remove_node(node)

    # node_colors = {node: G.nodes[node]['color'] for node in G.nodes}
    if recolor_jack:
        if miner_on_last_node is True and G.number_of_nodes()>0:
            G.nodes[list(G.nodes())[-1]]['color'] = 'black'

        mined_nodes = [node for node in G.nodes if G.nodes[node]['color']=='black']

        if len(mined_nodes) >= 1:
            ns, ns2 = common_predecessors(to_directed(G), nodes=mined_nodes)
        else:
            ns = mined_nodes
            ns2 = mined_nodes
        nx.set_node_attributes(G, name='color', values='#FF7006')
        nx.set_node_attributes(G, {n: {"color": "#888888"} for n in ns2})
        nx.set_node_attributes(G, {n: {"color": "#2a7de1"} for n in ns})
        nx.set_node_attributes(G, {n: {"color": "black"} for n in mined_nodes})
        nx.set_edge_attributes(G, {e: {"color": G.nodes[e[1]]['color']} for e in G.edges()})
        
    node_colors = [G.nodes[node]['color'] for node in G.nodes]
    colors = nx.get_edge_attributes(G, 'color').values()
    fig, ax = plt.subplots()
    if use_spiral:
        pos = nx.spiral_layout(G.nodes(), scale=1, center=(0.5,0.5), dim=2, resolution=np.pi/16, equidistant=False)
        if labels:
            nx.draw(G, pos, edge_color=colors, width=weights, node_size=np.arange(1, G.number_of_nodes()+1)/G.number_of_nodes()*100 * scale, 
                    node_color=node_colors, ax=ax, with_labels=True, labels=labels)
        else:
            nx.draw(G, pos, edge_color=colors, width=weights, node_size=np.arange(1, G.number_of_nodes()+1)/G.number_of_nodes()*100 * scale, 
                    node_color=node_colors, ax=ax)
    else:
        nx.draw(G, pos=positions, with_labels=False, edge_color=colors, width=weights, 
                node_size=400 * scale, node_color=node_colors, ax=ax)
    
        for node, (x, y) in positions.items():
            ax.text(x, y, node_labels[node], horizontalalignment='center', verticalalignment='center', 
                    color='white', size=15 * scale, weight='bold')
        
    ax.set_aspect('auto')
    plt.tight_layout()

    if save_as is not None:
        plt.savefig(save_as)

    if show:
        plt.show()
    else:
        plt.close()
