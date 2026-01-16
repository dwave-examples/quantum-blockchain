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
