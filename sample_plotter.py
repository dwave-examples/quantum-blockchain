from tests.data_generation.tree_generation import generate_random_tree
from src.utilities.spiral_plotter import SpiralPlotter

""" This script is not part of the core demo code, it is a utility to generate randomized plots with SpiralPlotter.
    The purpose is to make it easier to debug and evaluate cosmetic changes to SpiralPlotter, as it allows
    new plots to be generated in seconds, rather than having to wait for them to be produced slowly by
    the demo. Generate plots will display in a browser tab."""

test_tree = generate_random_tree(num_nodes=100, branch_probability=0.07)
last_active_block = test_tree.trunk[-15]
active_block_cutoff = last_active_block.block_number
my_plotter = SpiralPlotter()
test_plot = my_plotter.create_plot_from_tree(test_tree, active_block_cutoff=active_block_cutoff)
test_plot.show()
