import os

MINER_STATS_PATH = os.path.join("static", "miner_stats")

MINER_STATS_FILE = os.path.join(MINER_STATS_PATH, "miner_stats.json")

GLOBAL_GRAPHS_PATH = os.path.join("static", "graphs", "global")

MINER_GRAPHS_PATH = os.path.join("static", "graphs", "miner")

BASE_MINER_GRAPH_FILE = os.path.join(MINER_GRAPHS_PATH, "miner_graph.png")

BASE_GLOBAL_GRAPH_FILE = os.path.join(GLOBAL_GRAPHS_PATH, "global_graph.png")

PAUSE_PATH = os.path.join("static", "pause")

PAUSE_FILE = os.path.join("static", "paused.txt")

TRIAL_OUTPUTS_PATH = os.path.join("src", "trials", "outputs")

STATIC_PARAMS_FILE = os.path.join("static", "defualt_params.json")

EMBEDDINGS_DIRECTORY = os.path.join("src", "trials", "embeddings")

RUNNING_DIRECTORY_LIST = [MINER_STATS_PATH, GLOBAL_GRAPHS_PATH, MINER_GRAPHS_PATH, PAUSE_PATH]