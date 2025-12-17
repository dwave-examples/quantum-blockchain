import os



STATIC_PATH = os.path.join("", "static")
BOOTSTRAP_PATH = os.path.join("static", "bootstrap_data")
DEFAULT_MINERS_PATH = os.path.join(STATIC_PATH, "default_miners")
DEFAULT_OWNERS_PATH = os.path.join(STATIC_PATH, "default_owners")
EMBEDDINGS_PATH = os.path.join(STATIC_PATH, "embeddings")


SRC_PATH = os.path.dirname(os.path.realpath(__file__))
OUTPUT_PATH = os.path.join(SRC_PATH, "output")
