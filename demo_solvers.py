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


from src.protocols.hash_calculator import SolverName, initialize_solver
from src.values import DEFAULT_ENERGY_TIME_RESCALING

solver_list = []
bootstrap_list = []

for name in SolverName:
    name = str(name.value)
    if "simulated" in name:
        next_solver = initialize_solver(name)
        bootstrap_list.append(next_solver)
    else:
        try:
            if name not in DEFAULT_ENERGY_TIME_RESCALING:
                raise Exception("Solver energy scale not found!")
            next_solver = initialize_solver(name)
            solver_list.append(next_solver)
        except:
            print(
                f"Initialization failed for a parameterized solver, likely unavailable through the client: {name}"
            )

if len(solver_list) <= 0:
    raise Exception("Cannot connect to any solvers. Unable to run.")

AVAILABLE_QPU_SOLVERS = solver_list
BOOTSTRAP_SOLVERS = bootstrap_list
