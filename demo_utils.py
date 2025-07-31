import os, time
from pathlib import Path
from demo_configs import TRIAL_OUTPUTS_PATH, GRAPHS_PATH, DYNAMIC_PARAMS_PATH

def prep_directory(directory: str):
    if os.path.exists(directory):
        p = Path(directory)
        for file in p.iterdir():
            if not os.path.isdir(file):
                os.remove(file)
    else:
        os.mkdir(directory)

def make_output_directory() -> str:
    CUR_DIR = os.path.dirname(os.path.realpath(__file__))
    output_directory = os.path.join(CUR_DIR, TRIAL_OUTPUTS_PATH, time.strftime('%Y%m%d-%H%M%S'))
    os.makedirs(output_directory)
    return output_directory

def directory_setup() -> str:
    prep_directory(GRAPHS_PATH)
    prep_directory(DYNAMIC_PARAMS_PATH)
    out_dir = make_output_directory()
    return out_dir