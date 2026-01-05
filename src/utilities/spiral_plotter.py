import math
from typing import Optional
import plotly.graph_objects as go
import plotly.express as px

from src.structures.score_tree_branch import ScoreTreeBranch, BlockNode
from src.structures.block_score_tree import BlockScoreTree

from demo_configs import GRAPH_POINT_MIN_SIZE, GRAPH_POINT_MAX_SIZE, GRAPH_MAX_POINTS_PER_REV, GRAPH_MIN_POINTS_PER_REV, GRAPH_SEGS_PER_REV
from demo_configs import TRUNK_COLOR_SCALE, BRANCH_COLOR_SCALE

class GraphBranch(ScoreTreeBranch):
    def __init__(self, branch: ScoreTreeBranch):

        super().__init__()
        for node in branch.node_list:
            self.append_block(node)

        self.depth = branch.depth
        self.x_edges = []
        self.y_edges = []
        self.x_points = []
        self.y_points = []
        self.depth_adjustment = 0

    @property
    def start_idx(self):
        if self.parent is None:
            return 0
        else:
            return self.root.block_number + 1
          
    @property
    def final_idx(self):
        return self.tip.block_number

    def create_size_chart(self, master_size_chart: list, size_scale: float=1.0):
        self.size_chart = [size_scale*size for idx, size 
                           in enumerate(master_size_chart) 
                           if idx in [b.block_number for b in self]]

    def assign_depth_adjustment(self, depth_adjustment: int):
        self.depth_adjustment = depth_adjustment
        for child in self.children:
            child.assign_depth_adjustment(depth_adjustment)


class SpiralPlotter:
    def __init__(self):
        self.fig_width = 1
        self.center = (self.fig_width/2,self.fig_width/2)
        self.min_pnt_size = GRAPH_POINT_MIN_SIZE 
        self.max_pnt_size = GRAPH_POINT_MAX_SIZE
        self.branch_pnt_scaling = 0.65
        self.max_point_per_rev = GRAPH_MAX_POINTS_PER_REV
        self.min_points_per_rev = GRAPH_MIN_POINTS_PER_REV
        self.segs_per_rev = GRAPH_SEGS_PER_REV
        self.coord_dict = {}
        self.trunk_edge_color = "#2a7de1"
        self.trunk_point_color = "#2a7de1"
        self.branch_edge_color = "#FF7006"
        self.branch_point_color = "#FF7006"
        self.trunk_tip_color = "black"

    def create_master_size_chart(self):
        step_size = (self.max_pnt_size - self.min_pnt_size)/max(self.num_nodes-1,1)
        return [self.min_pnt_size + i*step_size for i in range(self.num_nodes + 1)]


    def import_plotting_data(self, tree_data: BlockScoreTree): #TODO add code to automatically compute num_nodes
        """ Takes a BlockScoreTree object and processes the data to prepare it to be plotted"""

        tree_data.refactor_branches()
        self.num_nodes = tree_data.num_nodes
        self.master_size_chart = self.create_master_size_chart()
        self.points_per_rev = min(self.max_point_per_rev, max(self.min_points_per_rev, self.num_nodes+1))
        self.angles = [2*math.pi*i/self.points_per_rev for i in range(1, self.points_per_rev + 1)]
        self.num_revs = (self.num_nodes+1)/self.points_per_rev
        self.segs_per_point = math.ceil(self.segs_per_rev/self.points_per_rev)
        self.loop_spacing = 0.99*(self.fig_width/(2*self.num_revs)) #Farthest edge should stop just short of the edge of the figure

        self.branches = []
        branch_pairs = {}
        for branch in tree_data.branches:
            new_graph_branch = GraphBranch(branch)

            if branch == tree_data.trunk:
                new_graph_branch.create_size_chart(self.master_size_chart)
                self.trunk = new_graph_branch
            else:
                new_graph_branch.create_size_chart(self.master_size_chart, self.branch_pnt_scaling)

            self.branches.append(new_graph_branch)
            branch_pairs.update({branch.base.hash: new_graph_branch})

        for base_hash, new_branch in branch_pairs.items():
            base_branch = tree_data.hash_to_branch_lookup[base_hash]
            if base_branch.parent is not None:
                new_branch.parent = branch_pairs[base_branch.parent.base.hash]
            for child in base_branch.children:
                new_branch.child = branch_pairs[child.base.hash]

    def arrange_branches(self):
        """ Queries the overall structure of the tree, and modifies the depth_adjustment
            attribute of branches as necessary to allow every branch to be graphed on the
            tree without any crossing or overlapping. This relies partially on the
            refactor_branches() method of BlockScoreTree (which should have been called
            as soon as the tree was imported), which ensures that the branches are 
            arranged such that this can be done simply and efficiently."""

        bottom_level_branches = [branch for branch in self.branches if branch.depth == 1]
        bottom_level_branches.sort(key=lambda x: self.num_nodes - x.root.block_number)

        depth_limits = [self.num_nodes+1]    
        for branch in bottom_level_branches:
            branch_depth = 1
            while branch_depth <= len(depth_limits):
                if branch.tip.block_number < depth_limits[branch_depth-1]:
                    break
                else:
                    branch_depth += 1

            if branch_depth > len(depth_limits):
                depth_limits.append(branch.base.block_number)
            else:
                depth_limits[branch_depth-1] = branch.base.block_number

            depth_adjustment = branch_depth - branch.depth
            branch.assign_depth_adjustment(depth_adjustment)
            #TODO work children into depth limits

        deepest_branch = max([branch.depth + branch.depth_adjustment for branch in self.branches])
        self.max_branch_depth = max(deepest_branch, 2)
        self.branch_spacing = 0.8/self.max_branch_depth

    def plot_spiral_points(self, branch):
        """ Computes and records the x and y coordinates for each node on a particular branch.
            """
        if branch.depth > 0:
            r_0 = self.loop_spacing*(branch.root.block_number)/self.points_per_rev
            adjustment = -min(r_0, self.loop_spacing)*self.branch_spacing*(branch.depth + branch.depth_adjustment)
        else:
            adjustment = 0
        for node in branch:
            r_node = node.block_number*self.loop_spacing/self.points_per_rev
            r_node += adjustment
            theta_node = self.angles[node.block_number%self.points_per_rev]
            x_node = self.center[0] + r_node*math.cos(theta_node)
            y_node = self.center[1] + r_node*math.sin(theta_node)
            branch.x_points.append(x_node)
            branch.y_points.append(y_node)
            self.coord_dict.update({node.block_number: (x_node, y_node)})

    def compute_fractional_angle(self, start_index, num_steps):
        total_index = (start_index + num_steps/self.segs_per_point)%self.points_per_rev
        whole_index = math.floor(total_index)
        frac_index = round(total_index - whole_index, 6)
        if frac_index > 0:
            angle_adjustment = (self.angles[1] - self.angles[0])*frac_index
        else:
            angle_adjustment = 0

        return self.angles[whole_index] + angle_adjustment

    def plot_spiral_curves(self, branch, trunk: bool = True):
        """ For a given branch, adds the points defining the 'curves' connecting the points
            on that branch. Each such 'curve' will be made up self.segs_per_point line
            segments, with larger numbers making smoother curves."""
        if not trunk: #Adds straight "stem" segment connecting branch to parent
            root_idx = branch.parent.hash_to_index_lookup[branch.root_hash]
            root_x = branch.parent.x_points[root_idx]
            root_y = branch.parent.y_points[root_idx]
            branch.x_edges.append(root_x)
            branch.y_edges.append(root_y)


        first_idx = branch.start_idx
        for i in range(len(branch)):
            if branch.depth > 0:
                r_0 = self.loop_spacing*(branch.root.block_number)/self.points_per_rev
                adjustment = -min(r_0, self.loop_spacing)*self.branch_spacing*(branch.depth + branch.depth_adjustment)
            else:
                adjustment = 0
            second_idx = branch[i].block_number
            if second_idx > first_idx:
                num_points = second_idx - first_idx
                num_segs = num_points*self.segs_per_point
                for j in range(num_segs-1):
                    r_current = (first_idx + j/self.segs_per_point)*self.loop_spacing/self.points_per_rev
                    r_current += adjustment
                    theta_current = self.compute_fractional_angle(first_idx, j)
                    x_next = self.center[0] + r_current*math.cos(theta_current)
                    y_next = self.center[1] + r_current*math.sin(theta_current)
                    branch.x_edges.append(x_next)
                    branch.y_edges.append(y_next)

            branch.x_edges.append(branch.x_points[i]) 
            branch.y_edges.append(branch.y_points[i])
            first_idx = second_idx


    def plot_spiral(self):
        """ Plots all the points and edges for every branch in the current tree."""

        self.arrange_branches()

        self.plot_spiral_points(self.trunk)
        for branch in self.branches:
            self.plot_spiral_points(branch)

        for branch in self.branches:
            self.plot_spiral_curves(branch, trunk=bool(branch == self.trunk))

    
    def draw_spiral(self):
        """ Assuming all the points and edges have been plotted"""
        trunk_edge_traces =[]
        for i in range(len(self.trunk.x_edges)-1):
            edge = go.Scatter(x=self.trunk.x_edges[i:i+2], y=self.trunk.y_edges[i:i+2], mode="lines", line={"color":self.trunk_edge_color})
            trunk_edge_traces.append(edge)
        trunk_node_trace = go.Scatter(x=self.trunk.x_points, y=self.trunk.y_points, mode="markers", marker={"size": self.trunk.size_chart, "color": [self.trunk_point_color for _ in range(len(self.trunk.x_points)-1)] +[self.trunk_tip_color], "opacity":1})
        plot_data = trunk_edge_traces

        node_traces = [trunk_node_trace]

        for branch in self.branches:
            if branch != self.trunk:
                for i in range(len(branch.x_edges)-1):
                    edge = go.Scatter(x=branch.x_edges[i:i+2], y=branch.y_edges[i:i+2], mode="lines", line={"color":self.branch_edge_color})
                    plot_data.append(edge)
                branch_node_trace = go.Scatter(x=branch.x_points, y=branch.y_points, mode="markers", marker={'color': self.branch_point_color, "opacity":1, "size": branch.size_chart})           
                node_traces.append(branch_node_trace)

        for trace in node_traces:
            plot_data.append(trace)

        fig = go.Figure(plot_data)
        return fig  
    
    def create_plot_from_tree(self, tree: BlockScoreTree):
        self.import_plotting_data(tree_data=tree)
        self.plot_spiral()
        plot = self.draw_spiral()
        return plot