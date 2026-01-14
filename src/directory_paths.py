import os

SRC_PATH = os.path.dirname(os.path.realpath(__file__))
OUTPUT_PATH = os.path.join(SRC_PATH, "output")
STATIC_PATH = os.path.join(SRC_PATH, "..", "static")
BOOTSTRAP_PATH = os.path.join(STATIC_PATH, "bootstrap_data")
EMBEDDINGS_PATH = os.path.join(STATIC_PATH, "embeddings")


