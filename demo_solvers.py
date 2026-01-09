from src.protocols.hash_calculator import SolverName, initialize_solver
from src.values import DEFAULT_ENERGY_TIME_RESCALING

solver_list = []

for name in SolverName:
    name = str(name.value)
    try:
        if "simulated" not in name:
            if name not in DEFAULT_ENERGY_TIME_RESCALING:
                raise Exception("Solver energy scale not found!")
        next_solver = initialize_solver(name)
        solver_list.append(next_solver)
    except:
        print(f"Failed: {name}")

AVAILABLE_SOLVERS = solver_list