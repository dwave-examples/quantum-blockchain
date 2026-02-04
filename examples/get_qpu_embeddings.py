# Copyright 2026 D-Wave
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

sys.path.append("../")
from directory_paths import EMBEDDINGS_PATH
from dwave.system import DWaveSampler
from src.utilities.quantum_cubic_utils import (
    create_lattice,
    get_embeddings,
    get_embeddings_filename,
    source_dimer_orientation,
    target_dimer_orientation,
)


def main(
    qpu: DWaveSampler,
    *,
    subgraph_embedding_timeout: float | int = 60,
    parallel_embedding_timeout: float | int = 600,
    seed: int = 1,
    verbose: bool = True,
    overwrite: bool = False,
) -> list[dict]:
    """Find and save (in examples/ directory) embedding files for a combination of qpu and sampler.

    See verbose statements for operational summary. A file is saved to the
    local directory when embedding succeeds, overwriting any other local
    copy (same edgelist for qpu and target model). This can be moved to
    the repo EMBEDDINGS_PATH for use within the blockchain demo.

    Note that, for typical applications, initial subgraph searches are fast
    and only the final (unsuccessful) search is slow. Default settings
    reflect limited testing and allow room for improvement. :code:`find_subgraph`
    allows a number of parameters that can potentially accelerate search.
    Divide and conquer strategies (e.g. :code:`find_sublattice_embeddings`),
    or post-selection strategies on sets of overlapping embeddings,
    can increase the number of parallel_embeddings yielded beyond those
    achieved by this heuristic method.
    Nevertheless, defaults should be sufficient for the demo use case.

    Args:
        qpu: DWaveSampler, the edgelist and topology information is used.
        subgraph_embedding_timeout: time per embedding search.
        parallel_embedding_timeout: time limit for iterative search process,
            note that this is tested after the subgraph search, the maximum
            time is the sum of subgraph and parallel embedding timeouts.
        seed: Used for reproducible randomization in the search.
        verbose: Print a method summary and information on search completion.
        overwrite: If an embedding exists in the cache, load it rather than
            overwriting.
    Returns:
        A list of embeddings
    """

    if verbose:
        print(f"Solving for chip_id {qpu.properties['chip_id']}")
        print()
        print(
            "find_subgraph is a complete method, guaranteed to return a 1:1 embedding "
            "(also called a subgraph isomorphism), should it exist (given sufficient time). "
            "This routine is called iteratively "
            "to determine disjoint embeddings with the find_multiple_embeddings routine. "
            "The result is returned either when no further subgraphs can be found, "
            "timeouts are reached in either routine, or the routine is interrupted. "
            "Different seeds may impact the sequence of embeddings "
            "found and the maximum number of embeddings. "
            "Since unitary dynamics are parallelized across embeddings with results aggregated "
            "more embeddings results typically results in better sampling error and higher "
            "cross-validation."
        )
        print()
        print(
            f"The parallel embedding timeout is set to {parallel_embedding_timeout} seconds, "
            f"and the find_subgraph_timeout is set to {subgraph_embedding_timeout} seconds, "
            f"which guarantees completion within {(parallel_embedding_timeout + subgraph_embedding_timeout)/60.0} minutes. "
            "Typically less time is required."
        )
    node_list_source, edge_list_source = create_lattice()
    node_labels = (
        source_dimer_orientation(node_list_source),
        target_dimer_orientation(qpu),
    )
    find_subgraph_kwargs = {
        "timeout": subgraph_embedding_timeout,
        "node_labels": node_labels,
        "seed": seed,
    }
    embeddings = get_embeddings(
        edge_list_source=edge_list_source,
        edge_list_target=qpu.edgelist,
        embedding_directory="./",  # EMBEDDINGS_PATH,
        embedding_timeout=parallel_embedding_timeout,
        max_num_emb=None,
        load_from_cache=not overwrite,
        save_to_cache=True,
        verify_embeddings=True,
        find_subgraph_kwargs=find_subgraph_kwargs,
    )
    if verbose:
        fn = get_embeddings_filename(
            edge_list_source=edge_list_source,
            edge_list_target=qpu.edgelist,
            embedding_directory="./",
        )
        print(
            f"A list of disjoint embeddings of length {len(embeddings)} has been created "
            f"and saved to {fn}. To use this file "
            f"for purposes of the demo it should be copied to {EMBEDDINGS_PATH}. "
            "An energy-time rescaling should also be specified, see get_time_energy_rescaling.py"
        )

    return embeddings


if __name__ == "__main__":
    description = (
        "Create per-QPU (or per QPU graph change) embeddings for cubic or biclique lattices "
        "to allow hash generation in the context of the blockchain example. "
        "Typically examples/get_energy_time_rescaling.py should also be run "
        "per QPU, to approximate necessary blockchain parameters."
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
        "-TS",
        "--subgraph_embedding_timeout",
        type=int,
        help="Time allowed per subgraph search in seconds",
        default=60,
    )
    parser.add_argument(
        "-TP",
        "--parallel_embedding_timeout",
        type=int,
        help="Time allowed for all (iterated) subgraph searches in seconds",
        default=600,
    )
    parser.add_argument(
        "-S",
        "--seed",
        type=int,
        help="Seed used by find_subgraph to pseudo-randomize the search",
        default=1,
    )
    parser.add_argument(
        "--verbose_off",
        action="store_true",
        help="Use this flag to switch off majority of print() statements.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Use this flag to ignore existing solutions, overwriting them with a new solution.",
    )

    args = parser.parse_args()
    verbose = not args.verbose_off
    if verbose:
        print(description)
    qpu = DWaveSampler(solver=args.solver_name, profile=args.profile)
    main(
        qpu=qpu,
        subgraph_embedding_timeout=args.subgraph_embedding_timeout,
        parallel_embedding_timeout=args.parallel_embedding_timeout,
        seed=args.seed,
        verbose=verbose,
        overwrite=args.overwrite,
    )
