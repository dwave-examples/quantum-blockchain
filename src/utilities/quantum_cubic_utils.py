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

import hashlib
import os
import pickle
from itertools import product

import dimod
import dwave
import dwave_networkx as dnx
import networkx as nx
import numpy as np
from directory_paths import EMBEDDINGS_PATH
from dwave.experimental.automorphism import \
    AutomorphismComposite  # Module location within dwave-ocean-sdk could be subject to change.
from dwave.preprocessing.composites import SpinReversalTransformComposite
from dwave.system import DWaveSampler
from dwave.system.composites import ParallelEmbeddingComposite
from minorminer.utils.parallel_embeddings import find_multiple_embeddings
from src.values import DEFAULT_CUBIC_BOUNDARY_CONDITIONS, DEFAULT_CUBIC_LATTICE_SHAPE


def get_embeddings_filename(
    edge_list_source: list[tuple],
    edge_list_target: list[tuple],
    embedding_directory: str = EMBEDDINGS_PATH,
) -> str:
    """Generate a filename unique to the source and target graph pairs

    Sorted edge lists uniquely identify graphs (up to ordering of nodes within edges,
    assumed this is canonical - potential future improvement).
    The hashes of the source and target edgelists can be used to
    identify embeddings for which valid embeddings are known:

    Args:
        edge_list_source: edges defining the source graph. Edges should be sortable.
        edge_list_target: edges defining the target graph. Edges should be sortable.
        embedding_directory: path to the canonical (repository) embeddings.
    Returns:
        A file name
    """

    els_hash = hashlib.sha256(str(tuple(sorted(edge_list_source))).encode()).hexdigest()
    elt_hash = hashlib.sha256(str(tuple(sorted(edge_list_target))).encode()).hexdigest()
    return os.path.join(embedding_directory, f"emb_S{els_hash}_T{elt_hash}.pkl")


def get_embeddings(
    edge_list_source: list[tuple],
    edge_list_target: list[tuple],
    *,
    embedding_directory: str = EMBEDDINGS_PATH,
    embedding_timeout: int = 0,
    max_num_emb: int | None = None,
    load_from_cache: bool = True,
    save_to_cache: bool = True,
    verify_embeddings: bool = True,
    find_subgraph_kwargs: bool = None,
) -> list[dict]:
    """Return embeddings compatible with source and target edge lists.

    By default loaded from a directory. If not present, create
    given a time allocation and target max number of parallel embeddings. Can
    be saved to the embedding cache for reuse.

    Embeddings are dictionaries that define minor embeddings (logical variables)
    on a processor graph.
    Each dictionary key in an embedding defines a variable of a binary
    quadratic model to be simulated. The dictionary value is a tuple, indicating the
    set of processor qubits used to represent the variable.

    Args:
        edge_list_source: edges defining the source graph. Edges should be sortable.
        edge_list_target: edges defining the target graph. Edges should be sortable.
        embedding_directory: path to the canonical (repository) embeddings.
        embedding_timeout: timeout applied to embedding search when loading
            from saved files fails. This parameter is ignored if loading
            succeeds. A value of zero can be used to disable generation on the fly.
            The value is applied to find_multiple_embeddings, if find_subgraph_kwargs
            is None, it is also used as the timeout for find_subgraph_kwargs.
        max_num_emb: max_num_emb to seek when loading from files fails. This
            parameter is ignored if loading succeeds.
        load_from_cache: attempt to load from the src.static.embeddings directory.
        save_to_cache: save new embeddings to the src.static.embeddings directory.
        verify_embeddings: Whether to test embeddings validity, this is only
            necessary when using embeddings from an untested source.
        find_subgraph_kwargs: kwargs passed to the find_subgraph routine.
    Returns
        A list of dictionaries, each dictionary defines an embedding.

    """
    embedding_filename = get_embeddings_filename(
        edge_list_source, edge_list_target, embedding_directory
    )
    if os.path.isfile(embedding_filename) and load_from_cache:
        with open(embedding_filename, "rb") as f:
            embeddings = pickle.load(f)
    else:
        if embedding_timeout > 0:
            if load_from_cache:
                print(
                    f"Cached embeddings not found at {embedding_filename}"
                    " Search for a set of viable embeddings, this may take up to "
                    f"embedding_timeout*2 = {embedding_timeout*2} seconds"
                )
            if find_subgraph_kwargs is None:
                find_subgraph_kwargs = {"timeout": embedding_timeout}

            embeddings = find_multiple_embeddings(
                S=nx.from_edgelist(edge_list_source),
                T=nx.from_edgelist(edge_list_target),
                timeout=embedding_timeout,
                max_num_emb=max_num_emb,
                embedder_kwargs=find_subgraph_kwargs,
            )
            # Subgraph isomorphisms (1 to 1 dictionaries) must be converted to
            # embeddings (1 to iterable dictionaries)
            embeddings = [
                {source_node: (target_node,) for source_node, target_node in emb.items()}
                for emb in embeddings
            ]  # Reformat 1:1 to 1:iterable
            if len(embeddings) and save_to_cache:
                with open(embedding_filename, "wb") as f:
                    pickle.dump(embeddings, f)
                print(f" Embeddings are saved to {embedding_filename} for reuse.")
        else:
            embeddings = []

    if verify_embeddings and len(embeddings) > 0:
        assert all(
            dwave.embedding.verify_embedding(emb, edge_list_source, edge_list_target)
            for emb in embeddings
        ), "An embedding provided (or created) was invalid for the target graph"
    return embeddings


def dimerize_coupling_3d(
    node1: tuple[int, int, int],
    node2: tuple[int, int, int],
    z_parity: int,
    lattice_dims: tuple[int, int, int] = DEFAULT_CUBIC_LATTICE_SHAPE,
) -> tuple[tuple, tuple]:
    """Convert a simple cubic lattice to a dimerized cubic lattice.

    The nodes are specified as a coordinates, a 3-tuple. The pattern
    of couplings between dimers (pairs of qubits) is chosen to be compatible
    with Zephyr and Pegasus (QPU processor) subgraph isomorphism (aka 1:1
    embedding).

    Args:
        node1: first node in the edge.
        node2: second node in the edge.
        z_parity: 0 or 1, specifies one of two isomorphic graphs conventions.
        lattice_dims: The maximum simple-cubic lattice dimension in each of three dimensions.
           Boundary spanning edges (for periodic dimensions) require special handling.
    Returns:
        A node and edge list
    """
    # x are 0,0; y are 1,1 ; z are (0,1), (1,0); both or random. The former two cases break reflection symmetry in x,y
    if (node2[0] - node1[0]) % lattice_dims[0] == 1 or (node2[0] - node1[0]) % lattice_dims[
        0
    ] == lattice_dims[0] - 1:
        d1 = d2 = 0  # Vertical-vertical dimer coupling (dimension 0)
    elif (node2[1] - node1[1]) % lattice_dims[1] == 1 or (node2[1] - node1[1]) % lattice_dims[
        1
    ] == lattice_dims[1] - 1:
        d1 = d2 = 1  # Horizontal-horizontal dimer coupling (dimension 1)
    elif (node2[2] - node1[2]) % lattice_dims[2] == 1:
        d1 = z_parity
        d2 = 1 - z_parity
    elif (node2[2] - node1[2]) % lattice_dims[2] == lattice_dims[2] - 1:
        d1 = 1 - z_parity
        d2 = z_parity
    else:
        raise ValueError("Displacements must be compatible with a simple cubic lattice.")
    return node1 + (d1,), node2 + (d2,)


def displace_n_by_c(n: tuple, c: tuple, lattice_dims: tuple | None = None):
    """Displace a coordinate by c, lattice_dims a lattice dimension.

    Args:
        n: Node coordinates specified as tuple of integers.
        c: Relative displacement of lattice neighbors, specified as
            a tuple of integers.
        lattice_dims: Lattice dimensions (for wrapping around a
            periodic boundary condition). If None, then there
            is no wrapping.

    Returns:
        Displaced coordinate, a tuple of integers
    """
    if lattice_dims is None:
        return tuple((n[i] + c[i]) for i in range(len(n)))
    else:
        return tuple((n[i] + c[i]) % lattice_dims[i] for i in range(len(n)))


def create_lattice(
    lattice_dims: tuple = DEFAULT_CUBIC_LATTICE_SHAPE,
    dim_periodicity=DEFAULT_CUBIC_BOUNDARY_CONDITIONS,
) -> tuple[list, list]:
    """Creates a square, cubic or hyper-cubic simple or dimerized lattice

    Args:
        lattice_dims: lattice dimensions
        dim_periodicity: periodic boundary specification in each of the dimensions.
            A tuple of bools of length matching lattice_dims each endicating if the
            dimension is periodic or open.

    Returns:
        A tuple of node and edge lists
    """
    if len(dim_periodicity) != len(lattice_dims):
        raise ValueError("There should be a periodicity setting for every dimension")
    ndim = len(lattice_dims)
    node_list = list(product(*[range(l) for l in lattice_dims]))
    node_set = set(node_list)
    # We generate 3 edges per node, wrap around those corresponding to
    # periodic dimensions, and set non-periodic dimensions big enough
    # to avoid wrap-around (dimension + 1):
    dim_wrap_around = tuple((1 + (not i)) * l for l, i in zip(lattice_dims, dim_periodicity))
    geometric_displacements = tuple(tuple(int(i == j) for i in range(ndim)) for j in range(ndim))
    edge_list = [
        tuple(sorted([n, displace_n_by_c(n, c, dim_wrap_around)]))
        for n in node_list
        for c in geometric_displacements
        if displace_n_by_c(n, c, dim_wrap_around)
        in node_set  # Exclude open boundary spanning edges.
    ]
    # Expand simple cubic lattice edges onto dimers (one extra dimension to indicate position in the dimer)
    edge_set = {(node + (0,), node + (1,)) for node in node_list}
    node_list = [node + (t,) for node in node_list for t in range(2)]
    edge_set |= {
        dimerize_coupling_3d(node1, node2, z_parity=0, lattice_dims=lattice_dims)
        for node1, node2 in edge_list
    }

    return node_list, sorted(edge_set)


def create_model(
    seed: int | None = None,
    problem_energy_scale=1.0,
) -> tuple[dict, dict]:
    """Create binary quadratic models compatible with DOI: 10.1126/science.ado6285

    The set of binary quadratic models are chosen for compatibility with demonstrations
    of quantum supremacy in approximate sampling. A subset of the models are supported.

    Args:
        seed: A seed for the coupler specification
        problem_energy_scale: A rescaling of couplings and fields, required
            to emulate evolution on one solver with another.

    Returns
        An Ising model specified by h and J dictionaries keyed by nodes
        and edges respectively.

    """
    prng = np.random.default_rng(seed)
    node_list, edge_list = create_lattice()
    J = {ij: (2 * prng.integers(2) - 1) / problem_energy_scale for ij in edge_list}
    h = {i: 0 for i in node_list}

    return h, J


def build_stats(response: dimod.SampleSet, edge_list: list) -> np.ndarray:
    """This function builds the statistics from the sampled output.

    The special case of pairwise correlations is considered.

    Args:
        sampleset: An unembedded dimod sampleset
        edge_list: edges on which to estimate correlations

    Returns:
        stats: An array of the output statistics. The inputs for
            witness construction (locality sensitive hashing).
    """
    if response.record.sample.dtype != np.float64:
        _samples = response.record.sample.astype(float)
    else:
        _samples = response.record.sample
    node_list_to_linear = {n: idx for idx, n in enumerate(response.variables)}
    corrs = np.array(
        [
            np.sum(
                _samples[:, node_list_to_linear[i]]
                * _samples[:, node_list_to_linear[j]]
                * response.record.num_occurrences
            )
            / np.sum(response.record.num_occurrences)
            for i, j in edge_list
        ]
    )

    return corrs


def target_dimer_orientation(qpu: DWaveSampler) -> dict:
    """A labeling of qubits by orientation

    Args:
        qpu: The DWaveSampler

    Returns:
        A mapping from the node to the orientation ('horizontal' or 'vertical')
    """

    if qpu.properties["topology"]["type"] == "zephyr":
        to_coordinates = dnx.zephyr_coordinates(
            *qpu.properties["topology"]["shape"]
        ).linear_to_zephyr
        dim_orientation = 0
    elif qpu.properties["topology"]["type"] == "pegasus":
        to_coordinates = dnx.pegasus_coordinates(
            *qpu.properties["topology"]["shape"]
        ).linear_to_pegasus
        dim_orientation = 0
    elif qpu.properties["topology"]["type"] == "chimera":
        to_coordinates = dnx.chimera_coordinates(
            *qpu.properties["topology"]["shape"]
        ).linear_to_chimera
        dim_orientation = 2
    else:
        raise ValueError("Unknown orientation")
    int_to_str = {0: "vertical", 1: "horizontal"}
    return {n: int_to_str[to_coordinates(n)[dim_orientation]] for n in qpu.nodelist}


def source_dimer_orientation(node_list: list) -> dict:
    """A mapping from the node to the expected qubit-orientation on processor.

    Args:
        node_list: A list of nodes.
    Returns:
        A mapping of nodes to the orientations ('horizontal' or 'vertical')
    """
    int_to_str = {0: "vertical", 1: "horizontal"}
    return {n: int_to_str[n[-1]] for n in node_list}


def generate_default_sampler(
    source_edge_list: list,
    qpu: DWaveSampler,
    *,
    embedding_directory: str = EMBEDDINGS_PATH,
    embedding_timeout: float | int = 0,
    automorphism_per_component: bool = False,
) -> dimod.Sampler:
    """This function generates a sampler (either a QPU or a SA sampler), appropriately
    parameterized based on the input to this function.


    Args:
        source_edge_list: A list of couplers relevant to the programmed Hamiltonian
        qpu: A DWaveSampler
        embedding_directory: Path to saved embeddings.
        embedding_timeout: Timeout for on-the-fly embedding. Embeddings can be
            created as one-time work per QPU using examples/get_qpu_embeddings.py. By
            default the timeout is zero and an error is thrown if the embedding is not
            precalculation.
        automorphism_per_component: If True, each embedding has an independent
            automorphism applied (matching arxiv: ) implementation. If False, independent
            automorphisms are applied ot each component, which is faster in the current
            implementation.
    Returns:
        A sampler aggregating samplesets from random parallel QPU embeddings
    """
    embeddings = get_embeddings(
        source_edge_list,
        qpu.edgelist,
        embedding_directory=embedding_directory,
        embedding_timeout=embedding_timeout,
    )
    if len(embeddings) == 0:
        raise Exception(
            f"Embeddings not found at {embedding_directory}"
            "Use examples/get_qpu_embeddings to generate embeddings/"
        )
    if automorphism_per_component:
        # This should be much faster subject to https://github.com/dwavesystems/dwave-experimental/pull/38
        embedded_edge_list = [
            (emb[v1], emb[v2]) for emb in embeddings for v1, v2 in source_edge_list
        ]
        sampler = ParallelEmbeddingComposite(
            AutomorphismComposite(
                SpinReversalTransformComposite(qpu), G=nx.from_edgelist(embedded_edge_list)
            ),
            embeddings=embeddings,
            source=nx.from_edgelist(source_edge_list),
        )
    else:
        sampler = AutomorphismComposite(
            ParallelEmbeddingComposite(
                SpinReversalTransformComposite(qpu),
                embeddings=embeddings,
                source=nx.from_edgelist(source_edge_list),
            )
        )

    return sampler
