# Copyright 2026 D-Wave
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

from src.agents.trial_manager import TrialManager
from src.protocols.hash_calculator import SolverName
from src.utilities.get_solvers import get_all_solvers
from src.values import MAX_RNG_SEED_LEN

trial_parameter_fields = {
    "max_blocks": 4,  # Allows 65535 blocks maximum
    "num_miners": 2,  # Allows 255 miners maximum
    "solvers": 2,  # Can currently fit 8 solvers at most. Increase if we add more solvers
    "quantum_hash_length": 4,  # Allows max length of 65535
    "n_zeroes": 2,  # Maximum allowed value of 255
    "allowable_err": 2,  # Maximum allowed value of 255
    "prng_seed": MAX_RNG_SEED_LEN,  # Max size of RNG seed in hex digits
}


def generate_trial_id(manager: TrialManager) -> str:
    """Creates an ID for a trial in the form of a hexadecimal string. This ID will encode all the
    parameters necessary to replicate the trial. Two trials will have identical IDs if and only if
    they use all the same parameters. Every parameter besides 'solvers' contributes to the ID in
    a simple and intuitive way: the integer value is converted to a hexadecimal value with a set
    number of digits (defined in 'trial_parameter_fields' above). Being non-numerical, the solver
    configuration must instead be encoded into an 8-digit binary number. Each solver is represented
    by a single digit, which is 1 if that solver is present in that configuration and 0 otherwise.
    The digits for the 7 current solvers are then padded with an 8th digit (always 0), to enable
    the binary value to be converted smoothly into hexadecimal."""

    trial_id = ""

    for param_name, length in trial_parameter_fields.items():
        param_val = getattr(manager, param_name)
        if param_name == "solvers":
            manager_solver_names = {s.solver_name for s in param_val}
            solver_bits = reversed([int(x.value in manager_solver_names) for x in SolverName])
            param_val = sum([a * 2**idx for idx, a in enumerate(solver_bits)])
        else:
            if param_val > 16**length - 1:
                raise Exception(
                    f"Parameter {param_name} had value {param_val}, exceeding the maximum"
                )

        trial_id += format(param_val, f"0{length}x")

    return trial_id


def get_trial_params_from_id(trial_id: str) -> dict:
    start_idx = 0
    params_dict = {}
    for param_name, length in trial_parameter_fields.items():
        param_hex_value = trial_id[start_idx : start_idx + length]
        start_idx += length
        param_int_value = int(param_hex_value, 16)
        if param_name == "solvers":
            num_digits = 4 * trial_parameter_fields["solvers"]
            bin_rep = format(param_int_value, f"0{num_digits}b")
            if num_digits - bin_rep.index("1") > len(SolverName):
                raise Exception(
                    f"Trial ID encoded a solver in position {num_digits - bin_rep.index("1")}, \
                    but only {len(SolverName)} solvers are defined."
                )

            available_solvers = get_all_solvers()
            solvers = []
            for idx, solver_entry in enumerate(SolverName):
                if bin_rep[idx + (num_digits - len(SolverName))] == "1":
                    if solver_entry.value not in available_solvers:
                        raise Exception(f"Can't recover initialization parameters: required solver \
                            {solver_entry.value} is unavailable.")

                    solvers.append(available_solvers[solver_entry.value])

            params_dict[param_name] = solvers
        else:
            params_dict[param_name] = param_int_value

    return params_dict
