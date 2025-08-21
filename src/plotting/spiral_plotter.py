import math
import plotly.graph_objects as go
import plotly.express as px

class GraphBranch:
    def __init__(self, branch_data_dict):
        self.map = branch_data_dict["map"]
        self.soundness_list = branch_data_dict["soundness"]
        self.depth = branch_data_dict["depth"]
        self.root = branch_data_dict["root"]
        self.root_depth = branch_data_dict["root_depth"]
        self.start_node = self.map[0]
        self.end_node = self.map[-1]
        self.x_edges = []
        self.y_edges = []
        self.x_points = []
        self.y_points = []
        
    def create_size_chart(self, master_size_chart: list, size_scale: float=1.0):
        self.size_chart = [size_scale*size for idx, size in enumerate(master_size_chart) if idx in self.map]

class SpiralPlotter:
    def __init__(self):
        self.fig_width = 1
        self.center = (self.fig_width/2,self.fig_width/2)
        self.min_pnt_size = 5
        self.max_pnt_size = 18
        self.branch_pnt_scaling = 0.65
        self.max_point_per_rev = 32  #Largest number of points plotted in a single revolution
        self.min_points_per_rev = 8  #Smallest allowable point spacing (so that graphs with very few points are spread out over a wider arc)
        self.segs_per_point = 4  #How many segements are used to built each section of spiral between points: more segments = smoother curve

    def create_master_size_chart(self):
        step_size = (self.max_pnt_size - self.min_pnt_size)/max(self.num_nodes-1,1)
        return [self.min_pnt_size + i*step_size for i in range(self.num_nodes)]

    def import_plotting_data(self, trunk_dict, branch_data, num_nodes):
        self.num_nodes = num_nodes
        self.points_per_rev = min(self.max_point_per_rev, max(self.min_points_per_rev, self.num_nodes+1))
        self.angles = [2*math.pi*i/self.points_per_rev for i in range(1, self.points_per_rev + 1)]
        self.num_revs = (self.num_nodes+1)/self.points_per_rev
        self.loop_spacing = 0.99*(self.fig_width/(2*self.num_revs)) #Farthest edge should stop just short of the edge of the figure
        self.trunk = GraphBranch(trunk_dict)
        self.full_node_map = [i for i in range(1,num_nodes+1)]
        self.master_size_chart = self.create_master_size_chart()
        self.trunk.create_size_chart(self.master_size_chart)

        self.branches = []
        for entry in branch_data:
            new_branch = GraphBranch(entry)
            new_branch.create_size_chart(self.master_size_chart, self.branch_pnt_scaling)
            self.branches.append(new_branch)
        self.max_branch_depth = max([abs(b.depth) for b in self.branches]) #Farthest in or out a branch will be from the trunk
        self.branch_spacing =1/(2*self.max_branch_depth + 1)  #Controls how much space is left between overlapping branches

    def generate_spiral_section(self, branch):
        if branch.depth != 0:
            start_index = branch.root + 1
        else:
            start_index = branch.root
        stop_index = branch.map[-1] + 1

        points = []

        #TODO just explicitly retrieve previous point's coordinates and use it.
        r_0 = self.loop_spacing*(branch.root)/self.points_per_rev
        adjustment = min(self.loop_spacing, r_0)*branch.root_depth*self.branch_spacing
        r_0 += adjustment
        theta_0 = self.angles[branch.root%self.points_per_rev]
        x_0 = self.center[0] + r_0*math.cos(theta_0)
        y_0 = self.center[1] + r_0*math.sin(theta_0)
        branch.x_edges.append(x_0)
        branch.y_edges.append(y_0)

        for i in range(start_index, stop_index):
            for j in range(self.segs_per_point):
                r_j = self.loop_spacing*(i+ j/self.segs_per_point)/self.points_per_rev
                theta_j = self.angles[i%self.points_per_rev] + (j*2*math.pi/self.segs_per_point)/self.points_per_rev
                adjustment = min(self.loop_spacing, r_j)*branch.depth*self.branch_spacing
                r_j += adjustment

                point_ij = [self.center[0] + r_j*math.cos(theta_j), self.center[1] + r_j*math.sin(theta_j)]
                points.append(point_ij)

                branch.x_edges.append(point_ij[0])
                branch.y_edges.append(point_ij[1])

                if i in branch.map and j == 0: #Add point to point map
                    branch.x_points.append(point_ij[0])
                    branch.y_points.append(point_ij[1])
                    if i == branch.map[-1]:
                        break #Do not draw remaining edges after the last node





    def plot_spiral(self):

        self.generate_spiral_section(self.trunk)
        for branch in self.branches:
            self.generate_spiral_section(branch)

        color_seq = px.colors.diverging.RdYlBu_r
        trunk_colors = [color_seq[i] if i < len(color_seq) else color_seq[-1] for i in range(len(self.trunk.x_points))]

        trunk_edge_trace = go.Scatter(x=self.trunk.x_edges, y=self.trunk.y_edges, mode="lines+markers", marker={"size":0, "opacity":0})
        trunk_node_trace = go.Scatter(x=self.trunk.x_points, y=self.trunk.y_points, mode="markers", marker={"size": self.trunk.size_chart, "color": self.trunk.soundness_list, "colorscale": "plasma_r", "opacity":1})
        plot_data = [trunk_edge_trace, trunk_node_trace]

        for branch in self.branches:
            branch_edge_trace = go.Scatter(x=branch.x_edges, y=branch.y_edges, mode="lines", line={'color':"#FF7006"})
            branch_node_trace = go.Scatter(x=branch.x_points, y=branch.y_points, mode="markers", marker={'color': "#FF7006", 'size': branch.size_chart})           
            plot_data.append(branch_edge_trace)
            plot_data.append(branch_node_trace)

        fig = go.Figure(data=plot_data)
        fig.show()

