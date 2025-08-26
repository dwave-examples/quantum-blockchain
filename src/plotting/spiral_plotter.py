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
        self.point_colors = []
        self.edge_colors = []
        
    def create_size_chart(self, master_size_chart: list, size_scale: float=1.0):
        self.size_chart = [size_scale*size for idx, size in enumerate(master_size_chart) if idx in self.map]


class SpiralPlotter:
    def __init__(self):
        self.fig_width = 1
        self.center = (self.fig_width/2,self.fig_width/2)
        self.min_pnt_size = 5
        self.max_pnt_size = 15
        self.branch_pnt_scaling = 0.65
        self.max_point_per_rev = 32  #Largest number of points plotted in a single revolution
        self.min_points_per_rev = 8  #Smallest allowable point spacing (so that graphs with very few points are spread out over a wider arc)
        self.segs_per_point = 4  #How many segements are used to built each section of spiral between points: more segments = smoother curve
        self.trunk_color_scale = px.colors.sequential.ice_r
        self.trunk_color_ints = []
        for color_string in self.trunk_color_scale:
            color_seq = color_string.split("(")[1].split(")")[0]
            int_colors = [int(color) for color in color_seq.split(",")]
            self.trunk_color_ints.append(int_colors)

        self.branch_color_scale = px.colors.sequential.YlOrBr_r
        self.branch_color_ints = []
        for color_string in self.branch_color_scale:
            color_seq = color_string.split("(")[1].split(")")[0]
            int_colors = [int(color) for color in color_seq.split(",")]
            self.branch_color_ints.append(int_colors)
        

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
        self.trunk_sound_max= max(self.trunk.soundness_list)
        self.trunk_sound_min = min(self.trunk.soundness_list)
        self.branches = []
        for entry in branch_data:
            new_branch = GraphBranch(entry)
            new_branch.create_size_chart(self.master_size_chart, self.branch_pnt_scaling)
            self.branches.append(new_branch)
        self.branch_sound_max = max([max(b.soundness_list) for b in self.branches])
        self.branch_sound_min = min([min(b.soundness_list) for b in self.branches])
        self.trunk.point_colors = [self.soundness_to_color(s) for s in self.trunk.soundness_list]
        for branch in self.branches:
            branch.point_colors = [self.soundness_to_color(s,trunk=False) for s in branch.soundness_list]

        self.max_branch_depth = max([abs(b.depth) for b in self.branches]) #Farthest in or out a branch will be from the trunk
        self.branch_spacing =1/(2*self.max_branch_depth + 1)  #Controls how much space is left between overlapping branches

    def generate_spiral_section(self, branch, trunk = True):
        
        start_index = branch.root + 1
        stop_index = branch.map[-1] + 1

        #TODO just explicitly retrieve previous point's coordinates and use it.
        r_0 = self.loop_spacing*(branch.root)/self.points_per_rev
        adjustment = min(self.loop_spacing, r_0)*branch.root_depth*self.branch_spacing
        r_0 += adjustment
        theta_0 = self.angles[branch.root%self.points_per_rev]
        x_0 = self.center[0] + r_0*math.cos(theta_0)
        y_0 = self.center[1] + r_0*math.sin(theta_0)
        branch.x_edges.append(x_0)
        branch.y_edges.append(y_0)

        branch.edge_colors.append(self.soundness_to_color(branch.soundness_list[0], trunk=trunk))

        stem_dist = branch.map[0] - start_index
        stem_segs = stem_dist*self.segs_per_point
        sounds = [branch.soundness_list[0] for i in range(stem_segs)]
        first_idx = start_index
        for k in range(1,len(branch.map)):
            second_idx = branch.map[k]
            diff = second_idx - first_idx
            steps = diff*self.segs_per_point
            frac_sounds = [(j*branch.soundness_list[k-1] + (steps-j)*branch.soundness_list[k])/steps for j in range(steps)]
            sounds += frac_sounds
            first_idx = second_idx
        sounds.append(branch.soundness_list[-1])
        siter = iter(sounds)

        for i in range(start_index, stop_index):
            for j in range(self.segs_per_point):
                r_j = self.loop_spacing*(i+ j/self.segs_per_point)/self.points_per_rev
                theta_j = self.angles[i%self.points_per_rev] + (j*2*math.pi/self.segs_per_point)/self.points_per_rev
                adjustment = min(self.loop_spacing, r_j)*branch.depth*self.branch_spacing
                r_j += adjustment

                point_ij = [self.center[0] + r_j*math.cos(theta_j), self.center[1] + r_j*math.sin(theta_j)]

                branch.x_edges.append(point_ij[0])
                branch.y_edges.append(point_ij[1])
                branch.edge_colors.append(self.soundness_to_color(next(siter), trunk=trunk))

                if i in branch.map and j == 0: #Add point to point map
                    branch.x_points.append(point_ij[0])
                    branch.y_points.append(point_ij[1])
                    if i == branch.map[-1]:
                        break #Do not draw remaining edges after the last node

        assert len(branch.edge_colors) == len(branch.x_edges), f"Edge color map for branch {branch.map[0]} is length {len(branch.edge_colors)} but there are {len(branch.x_edges)} branch edges"
    
    def soundness_to_color(self, soundness: float, trunk: bool = True):

        if trunk:
            color_scale = self.trunk_color_scale
            color_ints = self.trunk_color_ints
            sound_min = self.trunk_sound_min
            sound_max = self.trunk_sound_max
        else:
            color_scale = self.branch_color_scale
            color_ints = self.branch_color_ints
            sound_min = self.branch_sound_min
            sound_max = self.branch_sound_max

        adjusted_soundness = (soundness-sound_min)/(sound_max-sound_min)
        scale_len = len(color_scale)  

        scaled_soundness = scale_len*((1-adjusted_soundness)**3)
        low_idx = min(max(int(scaled_soundness),0), len(color_scale)-1)
        high_idx = min(low_idx+1, len(color_scale)-1)
        fract_idx = scaled_soundness - low_idx
        rgb_ints = [0,0,0]
        for rgb in range(3):
            rgb_float = (1-fract_idx)*color_ints[low_idx][rgb] + fract_idx*color_ints[high_idx][rgb]
            rgb_ints[rgb] = int(rgb_float)

        return f"rgb({rgb_ints[0]},{rgb_ints[1]}, {rgb_ints[2]})"
    
    def plot_spiral(self):

        self.generate_spiral_section(self.trunk)
        for branch in self.branches:
            self.generate_spiral_section(branch, trunk=False)

        trunk_edge_traces =[]
        for i in range(len(self.trunk.x_edges)-1):
            edge = go.Scatter(x=self.trunk.x_edges[i:i+2], y=self.trunk.y_edges[i:i+2], mode="lines", line={"color":self.trunk.edge_colors[i]})
            trunk_edge_traces.append(edge)
        trunk_node_trace = go.Scatter(x=self.trunk.x_points, y=self.trunk.y_points, mode="markers", marker={"size": self.trunk.size_chart, "color": self.trunk.point_colors, "opacity":1})
        plot_data = trunk_edge_traces

        node_traces = [trunk_node_trace]

        for branch in self.branches:
            for i in range(len(branch.x_edges)-1):
                edge = go.Scatter(x=branch.x_edges[i:i+2], y=branch.y_edges[i:i+2], mode="lines", line={"color":branch.edge_colors[i]})
                plot_data.append(edge)
            branch_node_trace = go.Scatter(x=branch.x_points, y=branch.y_points, mode="markers", marker={'color': branch.point_colors, "opacity":1, "size": branch.size_chart})           
            node_traces.append(branch_node_trace)

        for trace in node_traces:
            plot_data.append(trace)

        fig = go.Figure(data=plot_data)
        fig.show()

