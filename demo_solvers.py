from src.protocols.hash_calculator import SolverName, initialize_solver
from src.utilities.quantum_cubic_utils import get_energy_scale

solver_list = []

for name in SolverName:
    name = str(name.value)
    try:
        if "simulated" not in name:
            get_energy_scale(name)
        next_solver = initialize_solver(name)
        solver_list.append(next_solver)
    except:
        print(f"Failed: {name}")

AVAILABLE_SOLVERS = solver_list