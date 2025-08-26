import os, sys

from src.trials.graph_processor import generate_graph_data
from src.plotting.spiral_plotter import SpiralPlotter
from tests.tree_generation_test import generate_tree
from src.common.block_score_tree import BlockScoreTree

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

data_dir = os.path.join(CUR_DIR, "graph_data")
if not os.path.exists(data_dir):
    os.mkdir(data_dir)

iter = 1
set_dir = os.path.join(data_dir, f"set{iter}")
while os.path.exists(set_dir):
    iter += 1
    set_dir = os.path.join(data_dir, f"set{iter}")
os.mkdir(set_dir)

data_file = os.path.join(set_dir, f"branch_data{iter}.json")
map_file = os.path.join(set_dir, f"assign_map{iter}.csv")
err_file = os.path.join(set_dir, f"errors{iter}.txt")
base_tree_json = os.path.join(set_dir, f"tree.json")
base_tree_text = os.path.join(set_dir, f"tree.txt")

num_nodes = 200
test_tree = generate_tree(num_nodes=num_nodes)
test_tree.refactor_branches()
test_tree.write_to_file_json(base_tree_json)
test_tree.write_to_file(base_tree_text)

trunk, branches = generate_graph_data(test_tree, err_file, data_file, map_file)
plotter = SpiralPlotter()
plotter.import_plotting_data(trunk, branches, num_nodes)
plotter.plot_spiral()