import os, time
from pathlib import Path
from demo_constants import TRIAL_OUTPUTS_PATH, RUNNING_DIRECTORY_LIST

def prep_directory(directory: str):
    
    if not os.path.exists(directory):
        os.makedirs(directory)
    else:
        p = Path(directory)
        for file in p.iterdir():
            if not os.path.isdir(file):
                os.remove(file)

def make_output_directory() -> str:
    CUR_DIR = os.path.dirname(os.path.realpath(__file__))
    output_directory = os.path.join(CUR_DIR, TRIAL_OUTPUTS_PATH, time.strftime('%Y%m%d-%H%M%S'))
    os.makedirs(output_directory)
    return output_directory

def prep_directories() -> None:
    for directory in RUNNING_DIRECTORY_LIST:
        prep_directory(directory)

