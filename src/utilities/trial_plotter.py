import argparse
import os
import pickle
import sys

import networkx

sys.path.append("src")
import src.utilities.plotting as plotting


##
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-D", "--directory", type=str, help="Output directory")
    parser.add_argument("-N", "--num_to_plot", type=str, help="Number to plot", default="last")
    parser.add_argument("-S", "--save", action="store_true", help="Save", default=False)

    args = parser.parse_args()

    cur_dir = os.path.dirname(os.path.realpath(__file__))
    folder = os.path.join(cur_dir, "output", args.directory)
    if "graphs" in os.listdir(folder):
        folder = os.path.join(folder, "graphs")
    files = os.listdir(folder)
    files = [x for x in files if "graph" in x]
    if len(files) == 1:
        fns = [os.path.join(folder, files[0])]
    elif args.num_to_plot == "last":
        max_num = -1
        for file in files:
            num = int(file.split("_")[1].split(".")[0])
            if num > max_num:
                max_num = num
        fns = [os.path.join(folder, f"graph_{max_num}.pickle")]
    else:
        fns = [os.path.join(folder, fn) for fn in files]
    for fn in fns:
        with open(fn, "rb") as f:
            G = pickle.load(f)
        num = int(fn.split("_")[1].split(".")[0])
        if args.save:
            if args.num_to_plot == "many":
                save_as = os.path.join(folder, f"{num:04d}.png")
                # dpi=100  # 100 jpg, 72 png?; Choose something cheap for gif
            else:
                save_as = os.path.join(folder, f"{args.directory}_{num:04d}.eps")
                # dpi=None
        else:
            save_as = None
        if args.num_to_plot == "first":
            if num >= 32:
                continue
            plotting.plot_graph(G, save_as=save_as, show=(save_as is None), use_spiral=False)
        else:
            # Spirals:
            plotting.plot_graph(G, save_as=save_as, show=(save_as is None), use_spiral=True)
