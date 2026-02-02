# Copyright 2024 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

REPO_PATH = os.path.dirname(os.path.realpath(__file__))
STATIC_PATH = os.path.join(REPO_PATH, "static")
BOOTSTRAP_PATH = os.path.join(STATIC_PATH, "bootstrap_data")
EMBEDDINGS_PATH = os.path.join(STATIC_PATH, "embeddings")
