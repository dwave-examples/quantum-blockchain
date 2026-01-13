import os

STATIC_PATH = os.path.join("..", "static")
BOOTSTRAP_PATH = os.path.join(STATIC_PATH, "bootstrap_data")
EMBEDDINGS_PATH = os.path.join(STATIC_PATH, "embeddings")

SRC_PATH = os.path.dirname(os.path.realpath(__file__))
OUTPUT_PATH = os.path.join(SRC_PATH, "output")
