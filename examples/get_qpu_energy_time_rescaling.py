# Copyright 2025 D-Wave
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import sys
from typing import Literal

import dimod
import numpy as np
from dwave.samplers import SimulatedAnnealingSampler
from dwave.system import DWaveSampler

sys.path.append("../")
from src.utilities.quantum_cubic_utils import create_lattice, create_model, generate_default_sampler

ADV2_PROTOTYPE2_FIT = {
    "kappa_t": 0.93,
    "kappa_R": 0.71,
    "res_en": 18.82,
    "dres_en": 0.25,
    "annealing_time": 0.005,
}


def get_energy(
    qpu: DWaveSampler,
    *,
    energy_rescaling: float = 1.0,
    annealing_time: float = 0.005,
    fast_anneal: bool = True,
    num_reads: int = 1000,
    seed_bqm: int | None = None,
    statistic_type: Literal["mean-energy", "min-energy"] = "mean-energy",
) -> float:
    """Return the expected energy by embedding

    Args:
        qpu: the D-Wave sampler
        energy_rescaling: scaling down of the problem Hamiltonian.
        annealing_time: time in microseconds.
        fast_anneal: QPU parameter
        num_reads: number of reads per model
        seed_bqm: integer seed for J distribution
        statistic_type: statistic to extract per embedding
    Returns:
        An energy statistic
    """
    _, edge_list = create_lattice()
    solver = generate_default_sampler(
        edge_list,
        qpu=qpu,
    )
    solver_kwargs = {
        "auto_scale": False,
        "annealing_time": annealing_time,
        "fast_anneal": fast_anneal,
        "num_reads": num_reads,
    }

    bqm = (
        dimod.BinaryQuadraticModel("SPIN").from_ising(*create_model(seed=seed_bqm))
        / energy_rescaling
    )

    result = solver.sample(bqm, **solver_kwargs)
    if statistic_type == "mean-energy":
        return (
            energy_rescaling
            * np.sum(result.record.energy * result.record.num_occurrences)
            / np.sum(result.record.num_occurrences)
        )
    elif statistic_type == "min-energy":
        return energy_rescaling * result.first.energy
    else:
        raise ValueError("Unknown statistic")


def fit_rescaling_to_kibble_zurek_form(
    qpu: DWaveSampler,
    *,
    num_bqms: int = 25,
    kappa_t: float | None = None,
    kappa_R: float | None = None,
    res_en_target: float | None = None,
    annealing_time_model: float | None = None,
    energy_time_rescaling: tuple[float,float] | None = None,  # Initial guess
    ground_state_estimates: np.ndarray | None = None,
) -> tuple[tuple[float,float], tuple[float,float], np.ndarray]:
    r"""Determine a time (or as necessary energy) rescaling to match a reference Kibble-Zurek curve.


    The residual energy is well-enough described by a Kibble-Zurek scaling form
    :math:`<<H(x)>-min_x H(x) >_{model} = E (t_a/t_0)^{-\kappa_t} (J/R_0)^{-\kappa_R}` (1)
    where J is the problem Hamiltonian scale (relative to max value 1),
    and t_a is the programmed annealing time.
    R_0 and t_0 are QPU specific rescalings of problem-Hamiltonian and annealing time.
    kappa_* are ensemble-specific scaling parameters, approximately constant across QPUs.

    If residual energy is well matched between devices, correlation error is
    approximately minimized, and cross-validation rate is maximized.
    Owing primarily to small system size, decoherence and control error, the
    detailed form is expected to differ from a pure power law.


    The Advantage2_prototype2 energy versus annealing time curve is taken as a
    reference profile, per the methodology of arXiv:2503.14462. The model is
    fitted to data averaged on on 25 seeds with problem Hamiltonian rescalings
    in [0.5,1], and annealing times 5-10ns.
    Note kappa is approximately constant (per model ensemble). We fix E=-153.2 +/- 0.4,
    which is the average energy <Hp> achieved at t_a = 0.005us, and t_0=R=J=1.

    To calculate R and/or t_0 for another QPU we can guess parameter settings
    to match Advantage2_prototype2, by default (R_0, t_0) = 1., 1. for Advantage2
    and 1., 0.5 for Advantage. We can then collect data with R = R_0 and t=0.005/t_0
    to obtain an estimate <Hp>, we can then solve for (1) for either t_0 or R_0.
    If t_0 is viable (does not result in an annealing_time out-of-programmable bounds)
    a time rescaling is sufficient. Otherwise R_0 > 1 (energy rescaling) is sufficient.

    This function applies a 1-step approach.
    This process can be applied iteratively as part of a stoquastic gradient
    descent process. A collapse method similar to arXiv:2503.14462 Figure 6 can
    be used as an alternative.

    Args:
        qpu: The DWaveSampler for which energy-time rescaling is required.
        num_bqms: The number of models to test.
        kappa_t: Scaling of time as a function of annealing time.
        kappa_R: Scaling of energy as function of problem Hamiltonian rescaling.
        res_en_target: residual energy for target model
        annealing_time_model: annealing_time for which model energy is defined.
        energy_time_rescaling: An initial estimate for the rescaling.
        ground_state_estimates: An array of ground state energies.

    Returns:
        energy_rescaling_proposal (float, float): estimate of the problem Hamiltonian 
            rescaling required to emulate the reference residual energy curve 
        time_rescaling_proposal (float, float): estimate of the annealing time rescaling 
            required to emulate the reference residual energy curve
        residual_energies (np.ndarray): mean energy of each problem, minus estimated 
            ground-state energy
    """
    if energy_time_rescaling is None:
        energy_rescaling = 1.0
        if qpu.properties["chip_id"].startswith("Advantage_"):
            # Suitable guess for Advantage:
            time_rescaling = 0.5
        else:
            # Suitable guess for Advantage2:
            time_rescaling = 1.0
    else:
        energy_rescaling, time_rescaling = energy_time_rescaling

    if annealing_time_model is None:
        annealing_time_model = ADV2_PROTOTYPE2_FIT["annealing_time"]
    if kappa_t is None:
        kappa_t = ADV2_PROTOTYPE2_FIT["kappa_t"]
    if kappa_R is None:
        kappa_R = ADV2_PROTOTYPE2_FIT["kappa_R"]
    if ground_state_estimates is None:
        # A single QPU programming with 100 microsecond annealing and 1000 samples 
        # (other values left at default) solves these problems to optimality with 
        # high (sufficient) probability:
        ground_state_estimates = np.array(
            [
                get_energy(
                    qpu=qpu,
                    annealing_time=100,
                    fast_anneal=False,
                    num_reads=1000,
                    seed_bqm=seed_bqm,
                    statistic_type="min-energy",
                )
                for seed_bqm in range(num_bqms)
            ]
        )

    if res_en_target is None:
        res_en_target = ADV2_PROTOTYPE2_FIT["res_en"]

    residual_energies = [
        get_energy(
            qpu=qpu,
            energy_rescaling=energy_rescaling,
            annealing_time=annealing_time_model / time_rescaling,
            seed_bqm=seed_bqm,
        )
        - ground_state_estimates[seed_bqm]
        for seed_bqm in range(num_bqms)
    ]
    mean_residual_energy = np.mean(residual_energies)
    if mean_residual_energy <= 0:
        raise ValueError(
            "Expected residual energies should be positive, but the "
            f"expected value is {mean_residual_energy}."
            "Kibble-Zurek scaling fits are ill-defined as mean energies "
            "approach the ground state and/or if ground state energies "
            "are overestimated."
        )
    lin_target = np.log(mean_residual_energy / res_en_target)
    proposed_t = time_rescaling * np.exp(-lin_target / kappa_t)
    proposed_R = energy_rescaling * np.exp(-lin_target / kappa_R)
    if proposed_R < 1:
        print(
            f"Inviable problem-energy rescaling {proposed_R}, out of standard range 1/|J| in [1,infty)"
        )

    annealing_time = annealing_time_model / proposed_t
    if (
        annealing_time < qpu.properties["fast_anneal_time_range"][0]
        or annealing_time > qpu.properties["fast_anneal_time_range"][1]
    ):
        print(
            f"Inviable annealing time rescaling {annealing_time}, out of programmable annealing_time range"
        )
    candidate_energy_rescaling = (float(proposed_R), time_rescaling)
    candidate_time_rescaling = (energy_rescaling, float(proposed_t))
    return (
        candidate_energy_rescaling,
        candidate_time_rescaling,
        residual_energies,
    )


def main(
    qpu: DWaveSampler,
    verbose: bool = True,
) -> list[dict]:
    """Present a rescaling option

    See :code:`fit_rescaling_to_kibble_zurek_form`.

    This function performs a basic fit, more careful parameterization may allow 
    higher cross-validation rates.

    Args:
        qpu: DWaveSampler, the edgelist and topology information is used.
        verbose: Print a method summary and information on search completion.
    Returns:
        A list of embeddings
    """

    if verbose:
        print(f"Solving for chip_id {qpu.properties['chip_id']}")
        print()
        print(
            "A Kibble-Zurek model model provides a good description of the ensemble-average "
            "expected energy for all Advantage and Advantage2 processors given a suitable "
            "selection of the device and ensemble specific parameters. "
            "<Hp> = E_0 + E_1 (t_a/t_0)^{-kappa_t} (J/R_0)^{-kappa_R}. "
            "A fit to the Advantage2_prototype2_x_internal system yields all but the time (t_0) "
            "and energy (R_0) rescaling factors. These are determined by fitting the R_0 or t_0 "
            "to the experimental average energy from 25 QPU programmings. A short delay applies "
            "during data collection."
        )
    (
        energy_option,
        time_option,
        _,
    ) = fit_rescaling_to_kibble_zurek_form(qpu)
    print()  # NEW LINE
    if time_option[1] < 1:
        candidate = time_option
        print(f"The following time-rescaling option is viable: {time_option}")
    else:
        candidate = energy_option
        print(f"The following energy-rescaling option is viable: {energy_option}")
    if verbose:
        print(
            "This solver-name key, and rescaling value can be added to "
            "the DEFAULT_ENERGY_TIME_RESCALING dictionary in src/values.py"
        )
        print(
            "The solver_name should also be enumerated as a SOLVER in "
            "src/protocols/hash_calculator.py"
        )

    return candidate


if __name__ == "__main__":
    description = (
        "Create per-QPU energy-time rescalings for cubic or biclique lattices "
        "to allow cross-validation between QPUs in the context of the blockchain example. "
        "Typically one should first run examples/get_embeddings.py to generate embeddings."
    )

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "-Q",
        "--solver_name",
        type=str,
        help="Option to specify QPU solver, by default an experimental system supporting fast reverse anneal",
        default=None,
    )
    parser.add_argument(
        "-P",
        "--profile",
        type=str,
        help="profile used for the client connection",
        default=None,
    )
    parser.add_argument(
        "--verbose_off",
        action="store_true",
        help="Use this flag to switch off majority of print() statements.",
    )

    args = parser.parse_args()
    verbose = not args.verbose_off
    if verbose:
        print(description)
    qpu = DWaveSampler(
        solver=args.solver_name,
        profile=args.profile,
    )
    main(
        qpu=qpu,
        verbose=verbose,
    )
