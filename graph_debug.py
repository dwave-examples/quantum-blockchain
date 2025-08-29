import os, sys, argparse
import plotly.graph_objects as go

from src.trials.graph_processor import generate_graph_data
from src.plotting.spiral_plotter import SpiralPlotter
from tests.data_generation.tree_generation import generate_random_tree
from src.common.block_score_tree import BlockScoreTree

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

data_dir = os.path.join(CUR_DIR, "graph_data")
if not os.path.exists(data_dir):
    os.mkdir(data_dir)

def main(num_nodes: int, repeat_last: bool):

    iter = 1
    set_dir = os.path.join(data_dir, f"set{iter}")

    while os.path.exists(set_dir):
        iter += 1
        set_dir = os.path.join(data_dir, f"set{iter}")

    if repeat_last:
        iter -= 1
        set_dir = os.path.join(data_dir, f"set{iter}")
        test_tree = BlockScoreTree.load_from_json_file(os.path.join(set_dir, f"tree{iter}.json"))
        num_nodes = len(test_tree.hash_to_branch_lookup)
    else:
        os.mkdir(set_dir)
        test_tree = generate_random_tree(num_nodes=num_nodes)
        base_tree_json = os.path.join(set_dir, f"base_tree{iter}.json")
        test_tree.write_to_file_json(base_tree_json)
        test_tree.refactor_branches()
        refactored_tree_json = os.path.join(set_dir, f"tree{iter}.json")
        refactored_tree_text = os.path.join(set_dir, f"tree{iter}.txt")
        test_tree.write_to_file_json(refactored_tree_json)
        test_tree.write_to_file(refactored_tree_text)

    data_file = os.path.join(set_dir, f"branch_data{iter}.json")
    map_file = os.path.join(set_dir, f"assign_map{iter}.csv")
    err_file = os.path.join(set_dir, f"errors{iter}.txt")

    tree_data = generate_graph_data(test_tree, err_file, data_file, map_file)
    plotter = SpiralPlotter()
    plotter.import_plotting_data(tree_data, num_nodes)
    plot_data = plotter.plot_spiral()
    fig = go.Figure(plot_data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-N', '--nodes', type=int, help='Number of nodes', default=150)
    parser.add_argument('-R', '--repeat_last', action='store_true', help='Repeat Last Graph', default=False)

    args = parser.parse_args()

    num_nodes = args.nodes
    repeat_last = args.repeat_last

    main(num_nodes=num_nodes, repeat_last=repeat_last)
