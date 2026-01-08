import math
from typing import Optional
import plotly.graph_objects as go
import plotly.express as px

from src.structures.score_tree_branch import ScoreTreeBranch, BlockNode
from src.structures.block_score_tree import BlockScoreTree

from demo_configs import GRAPH_POINT_MIN_SIZE, GRAPH_POINT_MAX_SIZE, GRAPH_MAX_POINTS_PER_REV, GRAPH_MIN_POINTS_PER_REV, GRAPH_SEGS_PER_REV

#TODO higher priority: used line_profiler to determine how long various tasks take. Use this to guide optimization

#TODO consider how much of this can be pre-computed and stored.

#TODO work carefully through branch arrangement logic to improve depth assignments

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

    def assign_depth_adjustment(self, parent_depth_adjustment: int, depth_limits: list[int]):

        local_depth_adjustment = None
        base_depth = self.depth + parent_depth_adjustment 
        for depth in range(base_depth, len(depth_limits)): 
            bound = depth_limits[depth]
            if self.tip.block_number < bound:
                local_depth_adjustment = depth - self.depth
                depth_limits[depth] = self.root.block_number    
                break

        if local_depth_adjustment is None: #In this case, we exceeded the max depth in depth_limits without finding a space
            depth_limits.append(self.root.block_number) #So we extend depth_limits to accommodate
            local_depth_adjustment = len(depth_limits) - self.depth

        self.depth_adjustment = local_depth_adjustment
        sorted_children = [x for x in self.children]
        sorted_children.sort(key=lambda x: len(self) - x.root.block_number)
        for child in sorted_children:
            child.assign_depth_adjustment(self.depth_adjustment, depth_limits)
 
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
        self.trunk_edge_color = "#6fa8ee" #TODO move to demo_configs
        self.trunk_point_color = "#1458aa"
        self.branch_edge_color = "#F5A86E"
        self.branch_point_color = "#B85103"
        self.trunk_tip_color = "black"

    def create_master_size_chart(self):
        step_size = (self.max_pnt_size - self.min_pnt_size)/max(self.num_nodes-1,1)
        return [self.min_pnt_size + i*step_size for i in range(self.num_nodes + 1)]


    def import_plotting_data(self, tree_data: BlockScoreTree): 
        """ Takes a BlockScoreTree object and processes the data to prepare it to be plotted"""

        tree_data.refactor_branches()
        self.num_nodes = tree_data.num_nodes
        self.master_size_chart = self.create_master_size_chart()
        self.points_per_rev = min(self.max_point_per_rev, max(self.min_points_per_rev, self.num_nodes+1))
        self.num_revs = (self.num_nodes+1)/self.points_per_rev
        self.segs_per_point = math.ceil(self.segs_per_rev/self.points_per_rev)
        self.loop_scaling = 2/3
        self.max_r = 0.999
        
        angle_step = 2*math.pi/self.points_per_rev
        self.angles = [i*angle_step for i in range(1, self.points_per_rev + 1)]
        self.fractional_angles = [[(i+j/self.segs_per_point)*angle_step for j in range(1, self.segs_per_point)] for i in range(1, self.points_per_rev+1)]
        self.radii = [self.calculate_r(i) for i in range(self.num_nodes+1)]
        self.fractional_radii = [[self.calculate_r(i+j/self.segs_per_point) for j in range(1, self.segs_per_point)] for i in range(self.num_nodes)]
        

        self.min_branch_adjustment = 0.78
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

    def calculate_r(self, node_num: int|float):
        """ Calculates the distance from the center at which a point should be drawn. The logic
            is chosen such that the furthest-out turn of the spiral will take up 1/3 of the total
            radius, while the next turn in will take up 1/3 of the remainder. A correction factor
            is added to this so that points very near the beginning of the spiral will converge 
            more quickly towards the center (which would otherwise only happen in the limit of
            very many revolutions). 
            
            Args:
                node_num (int or float): the block number (order in the blockchain) of the node
                    being computed. Allows for fractional node numbers to assist in drawing
                    graph lines, which requires plotting points in between the actual graph nodes."""
        if node_num == 0:
            r_exp = -math.inf
        else:
            node_rev_num = node_num/self.points_per_rev
            r_exp = node_rev_num - 1/node_rev_num

        r_scale = self.loop_scaling**(self.num_revs-r_exp)
        return self.max_r*r_scale

    def arrange_branches(self):
        """ Queries the overall structure of the tree, and modifies the depth_adjustment
            attribute of branches as necessary to allow every branch to be graphed on the
            tree without any crossing or overlapping. This relies partially on the
            refactor_branches() method of BlockScoreTree (which should have been called
            as soon as the tree was imported), which ensures that the branches are 
            arranged such that this can be done simply and efficiently."""

        bottom_level_branches = [branch for branch in self.branches if branch.depth == 1]
        bottom_level_branches.sort(key=lambda x: self.num_nodes - x.root.block_number)
        max_depth = max(b.depth for b in self.branches)

        #Depth 0 will always be fully occupied by trunk, but including it makes list indices line up to depth values
        depth_limits = [0]+[self.num_nodes+1 for _ in range(max_depth)] 

        for branch in bottom_level_branches:
            branch.assign_depth_adjustment(0, depth_limits)

        self.max_branch_depth = max(len(depth_limits)-1, 3)

    def calculate_depth_adjustment(self, branch_depth: int):
        adjustment_fraction = branch_depth*(1 - self.min_branch_adjustment)
        return (self.max_branch_depth - adjustment_fraction)/self.max_branch_depth

    def plot_spiral_points(self, branch):
        """ Computes and records the x and y coordinates for each node on a particular branch.
            """

        adjustment = self.calculate_depth_adjustment(branch.depth + branch.depth_adjustment)

        for node in branch:
            r_node = self.radii[node.block_number]*adjustment
            theta_node = self.angles[node.block_number%self.points_per_rev]
            x_node = self.center[0] + r_node*math.cos(theta_node)
            y_node = self.center[1] + r_node*math.sin(theta_node)
            branch.x_points.append(x_node)
            branch.y_points.append(y_node)
            self.coord_dict.update({node.block_number: (x_node, y_node)})

    def plot_spiral_curves(self, branch: GraphBranch, trunk: bool = True):
        """ For a given branch, adds the points defining the 'curves' connecting the points
            on that branch. Each such 'curve' will be made up of a number of line segments 
            defined by the self.segs_per_point attribute. Plotly accepts these as lists
            of x- and y-coordinates, between which it will draw the lines. These coordinates
            include all of the coordinates of points on the graph, but also many points 
            between them so as to create a smooth curve:
            
            Args:
                branch (GraphBranch): the branch to be plotted
                trunk (bool): Defaults to 'True'. Flag to signal whether the branch
                is the trunk: non-trunk branches need a 'stem' segment drawn
                to connect them to their parent branch."""
        
        if not trunk: #Adds straight "stem" segment connecting branch to parent
            root_idx = branch.parent.hash_to_index_lookup[branch.root_hash]
            root_x = branch.parent.x_points[root_idx]
            root_y = branch.parent.y_points[root_idx]
            branch.x_edges.append(root_x)
            branch.y_edges.append(root_y)

        start_idx = branch.start_idx
        stop_idx = branch.tip.block_number
        adjustment = self.calculate_depth_adjustment(branch.depth + branch.depth_adjustment)
        for i in range(start_idx, stop_idx+1):
            r_i = self.radii[i]*adjustment
            theta_i = self.angles[i%self.points_per_rev]
            x_i = self.center[0] + r_i*math.cos(theta_i)
            y_i = self.center[1] + r_i*math.sin(theta_i)
            branch.x_edges.append(x_i)
            branch.y_edges.append(y_i)
            if i == stop_idx:
                break
            for j in range(self.segs_per_point-1):
            
                r_ij = self.fractional_radii[i][j]*adjustment
                theta_ij = self.fractional_angles[i%self.points_per_rev][j]
                x_ij = self.center[0] + r_ij*math.cos(theta_ij)
                y_ij = self.center[1] + r_ij*math.sin(theta_ij)
                branch.x_edges.append(x_ij)
                branch.y_edges.append(y_ij)


    def plot_spiral(self):
        """ Plots all the points and edges for every branch in the current tree."""

        self.arrange_branches()

        self.plot_spiral_points(self.trunk)
        for branch in self.branches:
            self.plot_spiral_points(branch)

        for branch in self.branches:
            self.plot_spiral_curves(branch, trunk=bool(branch == self.trunk))

    def draw_radial_lines(self):
        """ Draws radial lines at the pre-defined angles at which blocks will be plotted. """
        traces = []
        for angle in self.angles:
            x_end = self.center[0] + self.max_r*math.cos(angle)
            y_end = self.center[1] + self.max_r*math.sin(angle)
            x_edge = [self.center[0], x_end]
            y_edge = [self.center[1], y_end]
            new_trace = go.Scatter(x=x_edge, y=y_edge, mode="lines", line={"color": "grey", "width":0.5})
            traces.append(new_trace)

        return traces
    
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

        radial_traces = self.draw_radial_lines()
        for trace in radial_traces:
            plot_data.append(trace)

        fig = go.Figure(plot_data)
        return fig  
    
    def create_plot_from_tree(self, tree: BlockScoreTree):
        self.import_plotting_data(tree_data=tree)
        self.plot_spiral()
        plot = self.draw_spiral()
        return plot