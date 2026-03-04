# Copyright 2026 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import math

import plotly.graph_objects as go

from demo_configs import (
    ABANDONED_BRANCH_EDGE_COLOR,
    ABANDONED_BRANCH_POINT_COLOR,
    ACTIVE_BRANCH_EDGE_COLOR,
    ACTIVE_BRANCH_POINT_COLOR,
    GRAPH_BRANCH_POINT_SCALING,
    GRAPH_LOOP_SCALING,
    GRAPH_MAX_BRANCH_DISTANCE,
    GRAPH_MAX_POINTS_PER_REVOLUTION,
    GRAPH_MAX_RADIUS,
    GRAPH_MIN_POINTS_PER_REVOLUTION,
    GRAPH_POINT_MAX_SIZE,
    GRAPH_POINT_MIN_SIZE,
    GRAPH_RADIAL_LINE_COLOR,
    GRAPH_RADIAL_LINE_WIDTH,
    GRAPH_SEGMENTS_PER_REVOLUTION,
    MINING_BLOCK_BORDER_COLOR,
    TRUNK_EDGE_COLOR,
    TRUNK_POINT_COLOR,
    TRUNK_TIP_COLOR,
)
from src.structures.block_score_tree import BlockScoreTree
from src.structures.score_tree_branch import ScoreTreeBranch


class GraphBranch(ScoreTreeBranch):
    """This class holds a single branch of a BlockScore tree object, storing necessary
    data to plot that branch in a spiral plot alongside the standard branch data from
    the ScoreTreeBranch class. Coordinates for points and edge sections will initialize
    to empty lists (they must be computed and appended by the relevant methods from
    the SpiralPlotter class)."""

    def __init__(
        self,
        branch: ScoreTreeBranch,
        point_color: str = ABANDONED_BRANCH_POINT_COLOR,
        edge_color: str = ABANDONED_BRANCH_EDGE_COLOR
    ):
        """Initializes the graph branch.

        Args:
            branch (ScoreTreeBranch): the branch to be graphed
            point_color (str): the color assigned to the branch's points
            edge_color (str): the color assigned to the branch's edges"""

        super().__init__()
        for node in branch.node_list:
            self.append_block(node)

        self.depth = branch.depth
        self.x_edges = []
        self.y_edges = []
        self.x_points = []
        self.y_points = []
        self.point_colors = [point_color] * len(self.node_list)
        self.edge_color = edge_color
        self.depth_adjustment = 0

    @property
    def start_idx(self) -> int:
        if self.parent is None:
            return 0

        return self.root.block_number + 1

    @property
    def final_idx(self) -> int:
        return self.tip.block_number

    @property
    def adjusted_depth(self) -> int:
        return self.depth + self.depth_adjustment

    def create_size_chart(self, master_size_chart: list, size_scale: float = 1.0):
        """Creates a size chart, assigning a size to each point in the branch. This
        must be based on a master size chart, which defines the size progression.
        This method allows all the points in the branch to be proportionally
        scaled down.

        Args:
            master_size_chart (list): size chart for the trunk. Branch size charts are computed relative
                to the trunk.
            size_scale (float): Defaults to 1.0. Factor by which to scale the points in the branch.
                In general, non-trunk branches should be passed values less than 1, so they are drawn
                smaller than the points on the trunk."""

        self.size_chart = [
            size_scale * size
            for idx, size in enumerate(master_size_chart)
            if idx in [b.block_number for b in self]
        ]

    def assign_depth_adjustment(self, parent_adjusted_depth: int, depth_limits: list[int]):
        """Assigns a depth adjustment to the branch, indicating how far away from the trunk
        it must be drawn so as not to collide with any other branches. This function is
        called recursively on all the children of the branch, as the children of a branch
        should not be assigned independently of one-another (optimal assignment depends on
        assigning them in order)."""

        local_depth_adjustment = None
        for depth in range(parent_adjusted_depth, len(depth_limits)):
            bound = depth_limits[depth]
            if self.tip.block_number < bound:
                local_depth_adjustment = depth - self.depth
                depth_limits[depth] = self.root.block_number
                break

        # In this case, we exceeded the max depth in depth_limits without finding a space
        if local_depth_adjustment is None:
            depth_limits.append(self.root.block_number)  # So we extend depth_limits to accommodate
            local_depth_adjustment = len(depth_limits) - self.depth

        self.depth_adjustment = local_depth_adjustment
        sorted_children = [x for x in self.children]
        sorted_children.sort(key=lambda x: len(self) - x.root.block_number)
        for child in sorted_children:
            child.assign_depth_adjustment(self.adjusted_depth, depth_limits)


class SpiralPlotter:
    """This class facilitates plotting blockchain graphs as a collection of concentric spiral sections,
    with the longest chain (the "trunk") extending from the center to the edge of the plot and smaller,
    soft forks paralleling the main spiral to the inside."""

    def __init__(self):
        self.fig_width = 1
        self.center = (self.fig_width / 2, self.fig_width / 2)
        self.coord_dict = {}

    def _create_master_size_chart(self) -> list[float]:
        """Creates a size chart for the points in the trunk, which determines how large each point
        will appear on the chart. Points closer to the center will appear smaller, points
        closer to the tip will appear larger.

        Returns:
            master_size_chart (list[float]): A list of floats indicating how to scale the sizes
                points in the trunk. Points nearer the center (earlier in the trunk) will be
                close to GRAPH_MIN_POINT_SIZE. Moving out from there, points will grow
                smoothly larger as they approach the trunk tip. The points at the tip
                should be close to GRAPH_MAX_POINT_SIZE."""

        step_size = (GRAPH_POINT_MAX_SIZE - GRAPH_POINT_MIN_SIZE) / max(self.num_nodes - 1, 1)
        return [GRAPH_POINT_MIN_SIZE + i * step_size for i in range(self.num_nodes + 1)]

    def import_plotting_data(self, tree_data: BlockScoreTree, mining_hashes: list[str]):
        """ Takes a BlockScoreTree object and processes the data to prepare it to be plotted. When
            the data is imported, each of the branches of the original BlockScoreTree has its 
            data used to define a GraphBranch--a child class of ScoreTreeBranch which uses the same
            data organization scheme, but adds some methods and fields useful for preparing the 
            data to be graphed. The GraphBranch objects are linked together with the same 
            parent-child relationships that the branches of the original BlockScoreTree had, 
            which allows them to call properties inherited from ScoreTreeBranch that are
            useful for organizing the graph. However, this class is not a child of BlockScoreTree,
            as it is not intended for storing and dynamically updating the data, only processing
            it long enough to create a graph. In general, the size and location of elements on
            the plot may change significantly with the addition of even one additional block,
            so the data should be imported and re-plotted from scratch after each change in 
            the data of the BlockScoreTree object.

            Args:
                tree_data (BlockScoreTree): a BlockScoreTree object containing data to be
                    plotted on a spiral plot."""

        self.tree = tree_data
        self.tree.refactor_branches()
        self.tree.promote_by_hashes(mining_hashes)
        self.num_nodes = tree_data.num_nodes
        self.master_size_chart = self._create_master_size_chart()
        self.points_per_rev = self.calculate_points_per_rev()
        self.num_revs = (self.num_nodes + 1) / self.points_per_rev
        self.segs_per_point = math.ceil(GRAPH_SEGMENTS_PER_REVOLUTION / self.points_per_rev)

        angle_step = 2 * math.pi / self.points_per_rev
        self.angles = [i * angle_step for i in range(1, self.points_per_rev + 1)]
        self.fractional_angles = [
            [(i + j / self.segs_per_point) * angle_step for j in range(1, self.segs_per_point)]
            for i in range(1, self.points_per_rev + 1)
        ]
        self.radii = [self._calculate_r(i) for i in range(self.num_nodes + 1)]
        self.fractional_radii = [
            [self._calculate_r(i + j / self.segs_per_point) for j in range(1, self.segs_per_point)]
            for i in range(self.num_nodes)
        ]

        self.branches = []
        self.trunk = GraphBranch(self.tree.trunk, TRUNK_POINT_COLOR, TRUNK_EDGE_COLOR)
        self.trunk.point_colors[-1] = TRUNK_TIP_COLOR
        self.branches.append(self.trunk)
        self.trunk.create_size_chart(self.master_size_chart)
        sorted_branches=tree_data.branches
        sorted_branches.sort(key=lambda x: x.depth)

        for branch in sorted_branches[1:]:

            new_graph_branch = GraphBranch(branch)
            new_graph_branch.create_size_chart(
                    self.master_size_chart, GRAPH_BRANCH_POINT_SCALING
                )
            if branch.depth == 1:
                self.trunk.link_child_branch(new_graph_branch)
            else:
                for lower_branch in self.branches:
                    if branch.root in lower_branch:
                        lower_branch.link_child_branch(new_graph_branch)
                        break

            self.branches.append(new_graph_branch)

    def calculate_points_per_rev(self):
        """ Calculates how many points will be drawn in a single turn of the spiral. This changes
            dynamically so that graphs with small numbers of points will still have a distinctly
            spiral shape, but graphs with large numbers will be compressed enough to display data
            efficiently. The specific algorithm is intended to change the view relatively smoothly,
            not making too many adjustments to the spacing, but still ensuring that each adjustment
            is not too big of a change from the previous graph.

            Returns:
                points_per_rev (int): the number of points that will be drawn in a single
                    revolution."""

        allowed_vals = list(
            range(GRAPH_MIN_POINTS_PER_REVOLUTION, GRAPH_MAX_POINTS_PER_REVOLUTION + 1, 4)
        )
        if self.num_nodes <= GRAPH_MIN_POINTS_PER_REVOLUTION * 1.5:
            return GRAPH_MIN_POINTS_PER_REVOLUTION
        elif self.num_nodes >= GRAPH_MAX_POINTS_PER_REVOLUTION * 1.5:
            return GRAPH_MAX_POINTS_PER_REVOLUTION

        allowed_index = 0
        for idx, val in enumerate(allowed_vals):
            if self.num_nodes < val * 1.5:
                break

            allowed_index = idx

        return allowed_vals[allowed_index]

    def _calculate_r(self, node_num: int | float) -> float:
        """ Calculates the distance from the center at which a point should be drawn. The logic
            is chosen such that the furthest-out turn of the spiral will take up 1/3 of the total
            radius, while the next turn in will take up 1/3 of the remainder. A correction factor
            is added to this so that points very near the beginning of the spiral will converge
            more quickly towards the center (which would otherwise only happen in the limit of
            very many revolutions).

            Args:
                node_num (int or float): the block number (order in the blockchain) of the node
                    being computed. Allows for fractional node numbers to assist in drawing
                    graph lines, which requires plotting points in between the actual graph nodes.

            Returns:
                radius: distance from the center at which this graph point should be drawn."""

        if node_num == 0:
            r_exp = -math.inf
        else:
            node_rev_num = node_num / self.points_per_rev
            r_exp = node_rev_num - 1 / node_rev_num

        r_scale = GRAPH_LOOP_SCALING ** (self.num_revs - r_exp)
        return GRAPH_MAX_RADIUS * r_scale

    def _arrange_branches(self):
        """ Queries the overall structure of the tree, and modifies the depth_adjustment
            attribute of branches as necessary to allow every branch to be graphed on the
            tree without any crossing or overlapping. This relies partially on the
            refactor_branches() method of BlockScoreTree, which ensures that the branches are
            arranged such that this can be done simply and efficiently."""

        bottom_level_branches = [branch for branch in self.branches if branch.depth == 1]
        bottom_level_branches.sort(key=lambda x: self.num_nodes - x.root.block_number)
        max_depth = max(b.depth for b in self.branches)

        # Depth 0 will always be fully occupied by trunk, but including it makes list indices line up to depth values
        depth_limits = [0] + [self.num_nodes + 1 for _ in range(max_depth)]

        for branch in bottom_level_branches:
            branch.assign_depth_adjustment(0, depth_limits)

        self.max_branch_depth = max(len(depth_limits) - 1, 3)

    def _calculate_depth_adjustment(self, branch_depth: int) -> float:
        """ Calculates the adjustment factor used to scale the radii of points in a branch. Each
            should be drawn slightly farther inward towards the center of the graph than the
            trunk; how much farther depend on how many other branches are between it and
            the trunk, passed as the branch_depth argument.

            Args:
                branch_depth (int): The number of branches (self included) between this branch and
                    the trunk. The trunk should always be depth 0, a branch with no other branches
                    near it will be depth 1, and so on."""
        adjustment_fraction = branch_depth * (1 - GRAPH_MAX_BRANCH_DISTANCE)
        return (self.max_branch_depth - adjustment_fraction) / self.max_branch_depth

    def _plot_spiral_points(self, branch: GraphBranch):
        """ Computes and records the x and y coordinates for each node on a particular branch.

            Args:
                branch (GraphBranch): the GraphBranch object to be plotted"""

        adjustment = self._calculate_depth_adjustment(branch.depth + branch.depth_adjustment)

        for node in branch:
            r_node = self.radii[node.block_number] * adjustment
            theta_node = self.angles[node.block_number % self.points_per_rev]
            x_node = self.center[0] + r_node * math.cos(theta_node)
            y_node = self.center[1] + r_node * math.sin(theta_node)
            branch.x_points.append(x_node)
            branch.y_points.append(y_node)
            self.coord_dict.update({node.block_number: (x_node, y_node)})

    def _plot_spiral_curves(self, branch: GraphBranch):
        """ For a given branch, adds the points defining the 'curves' connecting the points
            on that branch. Each such 'curve' will be made up of a number of line segments
            defined by the self.segs_per_point attribute. Plotly accepts these as lists
            of x- and y-coordinates, between which it will draw the lines. These coordinates
            include all of the coordinates of points on the graph, but also many points
            between them so as to create a smooth curve.

            Args:
                branch (GraphBranch): the branch to be plotted
                trunk (bool): Defaults to 'True'. Flag to signal whether the branch
                is the trunk: non-trunk branches need a 'stem' segment drawn
                    to connect them to their parent branch."""

        if branch.parent is not None:  # Adds straight "stem" segment connecting branch to parent
            root_idx = branch.parent.hash_to_index_lookup[branch.root_hash]
            root_x = branch.parent.x_points[root_idx]
            root_y = branch.parent.y_points[root_idx]
            branch.x_edges.append(root_x)
            branch.y_edges.append(root_y)

        start_idx = branch.start_idx
        stop_idx = branch.tip.block_number
        adjustment = self._calculate_depth_adjustment(branch.depth + branch.depth_adjustment)
        for i in range(start_idx, stop_idx + 1):
            r_i = self.radii[i] * adjustment
            theta_i = self.angles[i % self.points_per_rev]
            x_i = self.center[0] + r_i * math.cos(theta_i)
            y_i = self.center[1] + r_i * math.sin(theta_i)
            branch.x_edges.append(x_i)
            branch.y_edges.append(y_i)
            if i == stop_idx:
                break

            for j in range(self.segs_per_point - 1):
                r_ij = self.fractional_radii[i][j] * adjustment
                theta_ij = self.fractional_angles[i % self.points_per_rev][j]
                x_ij = self.center[0] + r_ij * math.cos(theta_ij)
                y_ij = self.center[1] + r_ij * math.sin(theta_ij)
                branch.x_edges.append(x_ij)
                branch.y_edges.append(y_ij)

    def _color_for_global_view(self, mining_hashes: list[str]):
        """ Performs TODO update"""

        print(f"In color for global view with hash list {mining_hashes}")
        
        # In miner view trunk tip will always be a mining block, in global view it may not be
        self.trunk.point_colors[-1] = TRUNK_POINT_COLOR
        for branch in self.branches:
            if branch != self.trunk:
                if branch.has_blocks(mining_hashes):
                    branch.point_colors = [ACTIVE_BRANCH_POINT_COLOR for _ in range(len(branch))]
                    branch.edge_color = ACTIVE_BRANCH_EDGE_COLOR

            for block_hash in mining_hashes:
                if block_hash in branch.hash_to_index_lookup:
                    block_index = branch.hash_to_index_lookup[block_hash]
                    branch.point_colors[block_index] = TRUNK_TIP_COLOR

        print("Finished color for global view.")

    def draw_radial_lines(self) -> list[go.Scatter]:
        """Draws radial lines at the pre-defined angles at which blocks will be plotted. These are
        very simple straight segments extending from the center of the plot to the edge,
        lining up with the angles at which points are drawn.

        Return:
            traces (list[go.Scatter]). A list of Plotly Graph Objects Scatter objects,
            each one containing a single radial line."""
        traces = []
        for angle in self.angles:
            x_end = self.center[0] + GRAPH_MAX_RADIUS * math.cos(angle)
            y_end = self.center[1] + GRAPH_MAX_RADIUS * math.sin(angle)
            x_edge = [self.center[0], x_end]
            y_edge = [self.center[1], y_end]
            new_trace = go.Scatter(
                x=x_edge,
                y=y_edge,
                mode="lines",
                line={"color": GRAPH_RADIAL_LINE_COLOR, "width": GRAPH_RADIAL_LINE_WIDTH},
            )
            traces.append(new_trace)

        return traces

    def draw_spiral(self, mining_hashes: list[str], is_global: bool = False) -> go.Figure:
        """ Assuming all the points and edges have been plotted, draws them on the figure, coloring
            and sizing them according to the pre-defined color and size schema. This will draw two 
            distinct sorts of elements onto the graph area: points and lines. Each branch of the 
            graph will have one set of points (indicating the blocks that are part of that branch)
            and one set of lines, arranged so as to connect those points in a curving spiral shape.

            mining_hashes (list[str]): TODO
            is_global (bool):

            Returns:
                fig: The Plotly figure with the spiral graphed as determined by the data stored in
                    the branches."""

        self._arrange_branches()

        self._plot_spiral_points(self.trunk)
        for branch in self.branches:
            self._plot_spiral_points(branch)

        for branch in self.branches:
            self._plot_spiral_curves(branch)

        active_mining_hash = mining_hashes[0]
        if is_global:
            self._color_for_global_view(mining_hashes)

        plot_data = self.draw_radial_lines()

        edge_traces = []
        point_traces = []

        for branch in self.branches:

            edges = go.Scatter(
                x=branch.x_edges,
                y=branch.y_edges,
                mode="lines",
                line={"color":branch.edge_color}
            )
            edge_traces.append(edges)

            points = go.Scatter(
                x=branch.x_points,
                y=branch.y_points,
                mode="markers",
                marker={"color":branch.point_colors, "size":branch.size_chart}
            )

            point_traces.append(points)

            # Give point distinctive border color, indicating the block currently being mined
            if active_mining_hash in branch:
                mining_idx = branch.hash_to_index_lookup[active_mining_hash]
                mining_x = branch.x_points[mining_idx]
                mining_y = branch.y_points[mining_idx]
                mining_size = branch.size_chart[mining_idx]
                mining_trace = go.Scatter(
                    x=[mining_x],
                    y=[mining_y],
                    mode="markers",
                    marker={
                    "color": TRUNK_TIP_COLOR,
                    "size": mining_size,
                    "line": {"width": 4, "color": MINING_BLOCK_BORDER_COLOR},
                    },
                )
                point_traces.append(mining_trace)

        for trace in edge_traces:
            plot_data.append(trace)

        for trace in point_traces:
            plot_data.append(trace)

        fig = go.Figure(plot_data)
        return fig

    def create_plot_from_tree(self,
        tree: BlockScoreTree,
        mining_hashes: list[str],
        is_global_tree: bool = False,
        ) -> go.Figure:
        """ Given a BlockScoreTree object, creates a spiral plot displaying that tree. Calls all
            the necessary SpiralPlotter functions in order.

            Args:
                tree (BlockScoreTree): the BlockScoreTree object you wish to plot.
                mining_hash (str): the hash of the block that is currently being mined.
                is_global_tree (bool): Flag indicating whether the tree should be recolored to
                    represent the global view. Should be left on defaults for individual miner 
                    graphs.


            Returns:
                plot (go.Figure): a Plotly Graph Objects figure, containing the spiral plot for
                    the tree.

        """

        self.import_plotting_data(tree_data=tree, mining_hashes=mining_hashes)
        plot = self.draw_spiral(mining_hashes, is_global_tree)
        return plot