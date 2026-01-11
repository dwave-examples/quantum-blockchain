# TO DO (GENERAL):
# Change order of composites so that we have per-embedding automorphisms, rather
# than a common automorphism for all embeddings.
# Move test functions/module code into an example/ (can be removed entirely for demo).
# Automate energy-scale, energy scale as a function of qpu chip_id when looked - up, remove solver argument.
# See also # Improvements comments.

# TO DO (DEMO ONLY):
# Modifications to this module impact a few other files, these should be
# updated to match changes in the pull request.
# Delete non-default code branches, and remove arguments associated to non-default branches.
# See also # Improvements comments.

from itertools import product
import pickle
import os
import math

import hashlib
import networkx as nx
import numpy as np

import dimod
import dwave
import dwave_networkx as dnx
from dwave.experimental.automorphism import (
    AutomorphismComposite,
)  # Module location within dwave-ocean-sdk could be subject to change.
from dwave.preprocessing.composites import SpinReversalTransformComposite
from dwave.system.composites import ParallelEmbeddingComposite
from dwave.system import DWaveSampler
from minorminer.utils.parallel_embeddings import find_multiple_embeddings

from directory_paths import (
    EMBEDDINGS_PATH,
)  # Improvement? Not a fan of this dependency on the directory structure.
from src.values import (
    DEFAULT_BICLIQUE_PARTITION_SIZE,
    DEFAULT_CUBIC_BOUNDARY_CONDITIONS,
    DEFAULT_CUBIC_LATTICE_SHAPE,
    DEFAULT_CUBIC_DIMERIZATION,
)


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
        max_num_emb: max_num_emb to seek when loading from files fails. This
            parameter is ignored if loading succeeds.
        save_to_cache: Whether to save an embedding.
        load_from_cache: attempt to load from the src.static.embeddings directory.
        save_to_cache: save new embeddings to the src.static.embeddings directory.
        verify_embeddings: Whether to test embeddings validity, this is only
            necessary when using embeddings from an untested source.
        find_subgraph_kwargs: kwargs passed to the find_subgraph routine.
    Returns
        A list of dictionaries, each dictionary defines an embedding.

    """
    # Sorted edge lists uniquely identify graphs (up to ordering of nodes within edges,
    # assumed this is canonical - potential future improvement).
    # The hashes of the source and target edgelists can be used to
    # identify embeddings for which valid embeddings are known:
    els_hash = hashlib.sha256(str(tuple(sorted(edge_list_source))).encode()).hexdigest()
    elt_hash = hashlib.sha256(str(tuple(sorted(edge_list_target))).encode()).hexdigest()
    embedding_filename = os.path.join(embedding_directory, f"emb_S{els_hash}_T{elt_hash}.pkl")
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
                print("Should not happen!")
                find_subgraph_kwargs = {"timeout": embedding_timeout}
            embeddings = find_multiple_embeddings(
                S=nx.from_edgelist(edge_list_source),
                T=nx.from_edgelist(edge_list_target),
                timeout=embedding_timeout,
                max_num_emb=max_num_emb,
                embedder_kwargs=find_subgraph_kwargs,
            )
            print(f"A set of {len(embeddings)} embeddings were found.")
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

    # Improvement: json rather than pickle format?
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
    lattice_dims: tuple[int, int, int],
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


def dimer_biclique_to_zephyr_coordinate(
    partition: int, partition_idx: int, dimer_idx: int, t: int = 4
) -> tuple[int, int, int, int, int]:
    """Partition linear order to zephyr coordinates

    Args:
        partition: partition (0 or 1)
        partition_idx: index within the biclique
        z: dimer index (0 ot 1)
        t: tile parameter of the zephyr graph
    Returns:
        zephyr coordinate u, w, k, j, z
    """
    return (
        partition,
        1 + partition_idx // (2 * t),
        (partition_idx // 2) % t,
        partition_idx % 2,
        dimer_idx,
    )


def create_dimerized_biclique(partition_size: int = DEFAULT_BICLIQUE_PARTITION_SIZE):
    """Create a regular biclique embedding on Zephyr

    Nodes of a biclique are expanded onto dimers (pairs of qubits) that define
    a special subgraph of Zephyr[m=2]. Viability of embedding requires that
    :math:`ceil(partition_size/6)` is not larger than the tile parameter
    of the target graph (`t=4` for Advantage system 2).

    Args:
        partition_size: The paritition size (p) of a biclique :math:`K_{p,p}`

    Returns:
        A node and edge list defining the model. Nodes have coordinate the labels.
        The first coordinate indicates the partition (0 or 1). The final
        coordinate indicates the position within the dimer (0 or 1). Contracting
        the dimers results in a biclique.
    """
    t = math.ceil(partition_size / 6)
    emb = {
        (partition, partition_idx): tuple(
            dimer_biclique_to_zephyr_coordinate(partition, partition_idx, dimer_idx, t=t)
            for dimer_idx in range(2)
        )
        for partition in range(2)
        for partition_idx in range(partition_size)
    }

    node_list = [node for logical_node in emb.values() for node in logical_node]
    edge_list = [
        (node1, node2)
        for node1, node2 in dnx.zephyr_graph(m=2, t=t, coordinates=True, node_list=node_list).edges
        if node1[0] != node2[0] or node1[3] == node2[3]
    ]  # Include all but the odd-couplers

    # Improvement: Move following two trivial asserts to tests/
    assert len(node_list) == 4 * partition_size, "Incorrect number of variables"
    assert len(edge_list) == 2 * partition_size + partition_size**2, "Incorrect number of edges"

    return node_list, edge_list


def create_lattice(
    lattice_dims: tuple,
    *,
    dim_periodicity: tuple | None = None,
    dimerization_mode: str | None = None,
) -> tuple[list, list]:
    """Creates a square, cubic or hyper-cubic simple or dimerized lattice

    Args:
        lattice_dims: lattice dimensions
        dim_periodicity: periodic boundary specification in each of the dimensions.
            A tuple of bools of length matching lattice_dims each endicating if the
            dimension is periodic or open.
        dimerization_mode: create a generalized lattice where each variable is expanded onto a dimer.
            This str parameter controls the nature of couplings between dimers, None is used
            to indicate no dimerization.

    Returns:
        A tuple of node and edge lists
    """
    # Improvement: hardcode dimerization_mode=='single' for demo and remove branching.
    ndim = len(lattice_dims)
    if dim_periodicity is None:
        dim_periodicity = tuple([False] * ndim)
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
    if dimerization_mode is not None:
        # Expand simple cubic lattice edges onto dimers (one extra dimension to indicate position in the dimer)
        edge_set = {(node + (0,), node + (1,)) for node in node_list}
        node_list = [node + (t,) for node in node_list for t in range(2)]
        edge_set |= {
            dimerize_coupling_3d(node1, node2, z_parity=0, lattice_dims=lattice_dims)
            for node1, node2 in edge_list
        }
        if dimerization_mode == "double":
            edge_set |= {
                dimerize_coupling_3d(node1, node2, z_parity=1, lattice_dims=lattice_dims)
                for node1, node2 in edge_list
            }
        edge_list = sorted(edge_set)

    return node_list, edge_list


def create_model(
    ensemble: str,
    *,
    seed: np.random.Generator | int | None = None,
    model_dimensions: int | tuple | None = None,
    problem_energy_scale=1.0,
) -> tuple[dict, dict]:
    """Create binary quadratic models compatible with DOI: 10.1126/science.ado6285

    The set of binary quadratic models are chosen for compatibility with demonstrations
    of quantum supremacy in approximate sampling. A subset of the models are supported.

    Args:
        ensemble: Either 'DimBiClique' for the dimerized biclique model, or
            or one of 'PMJ' or 'Uniform' for a cubic lattice (low and high
            precision coupling between dimers respectively).
        seed: A seed for the coupler specification
        model_dimensions: The dimensions of the model, should
            be an integer for DimerizedBiclique in the range 8
            to 24 (specifying the size of each partition in the
            biclique) or a tuple of dimensions for cubic lattices.
        problem_energy_scale: A rescaling of couplings and fields, required
            to emulate evolution on one solver with another.

    Returns
        An Ising model specified by h and J dictionaries keyed by nodes
        and edges respectively.

    """
    prng = np.random.default_rng(seed)
    if ensemble == "DimBiClique":  # Improvement: Use enum for ensemble
        if model_dimensions is None:
            partition_size = DEFAULT_BICLIQUE_PARTITION_SIZE
        else:
            partition_size = model_dimensions
        node_list, edge_list = create_dimerized_biclique(partition_size=partition_size)
        h = {i: 0 for i in node_list}
        abs_J_inter_partition = 1 / np.sqrt(partition_size)  # Coupling between dimers
        J_intra_partition = -1.0  # Coupling within dimer
        J = {
            (node1, node2): (
                J_intra_partition
                if (node1[0] == node2[0])  # Same orientation (dimension 0) define dimers
                else (2 * prng.integers(2) - 1) * abs_J_inter_partition
            )
            / problem_energy_scale
            for node1, node2 in edge_list
        }
        # Improvement: Move following (trivial) assertions to tests
        assert len(node_list) == len(set(node_list)), "node_list should contain no duplications"
        assert len(edge_list) == len(set(edge_list)), "edge_list should contain no duplications"
        assert (
            np.sum([abs(v) == -J_intra_partition for v in J.values()]) == 2 * partition_size
        ), "There should be one chain (with J=-1) per logical variable, in each partition"
        assert set(n for ij, v in J.items() for n in ij if v == J_intra_partition) == set(
            node_list
        ), "couplings should be consistent with node_list"
        assert (
            np.sum([abs(v) != -J_intra_partition for v in J.values()]) == partition_size**2
        ), "There should be exactly one coupling between every dimer"
    else:
        # Improvement: Can restrict to defaults for non-experimental code.
        if model_dimensions is None:
            lattice_dims = DEFAULT_CUBIC_LATTICE_SHAPE
        else:
            lattice_dims = model_dimensions
        if len(lattice_dims) == 3:
            # Cubic lattice defaults:
            dim_periodicity = DEFAULT_CUBIC_BOUNDARY_CONDITIONS
            dimerization_mode = DEFAULT_CUBIC_DIMERIZATION
        else:
            dim_periodicity = None
            dimerization_mode = None

        node_list, edge_list = create_lattice(
            lattice_dims,
            dim_periodicity=dim_periodicity,
            dimerization_mode=dimerization_mode,
        )
        # Improvement: restrict to default for non-experimental code.
        if ensemble == "PMJ":  # Low precision no-dimer
            J = {ij: 2 * prng.integers(2) - 1 for ij in edge_list}
        elif ensemble == "Uniform":  # High precision no-dimer
            J = {ij: 2 * prng.random() - 1 for ij in edge_list}
        else:
            raise ValueError(f"Unknown emsemble {ensemble}")
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


def get_qpu_access_times(
    qpu: DWaveSampler, *, qpu_kwargs: dict | None = None, num_var: int = None
) -> tuple[float, float]:
    """Return the constant overhead time, and per read time.

    Args:
        qpu: The DWaveSampler
        qpu_kwargs: Experimental arguments other than num_var impacting runtime.
        num_var: Total number of programmed qubits (across all embeddings)
    Returns
        A tuple of the constant time and per-read time
    """
    if num_var is None:
        num_var = qpu.properties["num_qubits"]
    if qpu_kwargs is None:
        _qpu_kwargs = {}
    else:
        _qpu_kwargs = qpu_kwargs.copy()
    _qpu_kwargs["num_reads"] = 0
    constant_time = qpu.solver.estimate_qpu_access_time(num_var, **_qpu_kwargs)
    _qpu_kwargs["num_reads"] = 1
    per_read_time = qpu.solver.estimate_qpu_access_time(num_var, **_qpu_kwargs) - constant_time
    return float(constant_time), float(per_read_time)


def get_max_num_reads(
    qpu: DWaveSampler,
    qpu_kwargs: dict | None = None,
    num_var: int | None = None,
    max_time: float = float("Inf"),
) -> int:
    """Number of reads required to fully exploit given QPU access time.

    Args:
        qpu: The DWaveSampler
        qpu_kwargs: Experimental arguments other than num_var impacting runtime.
        num_var: Total number of programmed qubits (across all embeddings)
        max_time: Determine a maximum time in combination with the solver-specific
            max run duration parameter. The smaller of the two is used. The value should
            be seconds.
    Returns:
        number of reads exploiting the given time scale.
    """
    if qpu_kwargs is None:
        qpu_kwargs = {}
    estimated_runtime = min(qpu.properties["problem_run_duration_range"][1], max_time * 1000000)
    constant_time, per_read_time = get_qpu_access_times(qpu, qpu_kwargs=qpu_kwargs, num_var=num_var)
    if estimated_runtime < constant_time + per_read_time:
        num_reads = 0
    else:
        num_reads = min(
            qpu.properties["num_reads_range"][1],
            int((estimated_runtime - constant_time) / per_read_time),
        )
    return num_reads


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


def source_dimer_orientation(node_list: list, ensemble: str) -> dict:
    """A mapping from the node to the expected qubit-orientation on processor.
    Args:
        node_list: A list of nodes.
        ensemble: The ensemble 'PMJ', 'Uniform' or 'DimBiClique' compatible
            with the node format.
    Returns:
        A mapping of nodes to the orientations ('horizontal' or 'vertical')
    """
    if ensemble == "DimBiClique":
        dim_orientation = 0  # First dimension indicates orientation.
    elif ensemble == "PMJ" or ensemble == "Uniform":
        dim_orientation = -1  # Final dimension indicates orientation.
    else:
        return {}  # No (known) labeling
    int_to_str = {0: "vertical", 1: "horizontal"}
    return {n: int_to_str[n[dim_orientation]] for n in node_list}


def generate_default_sampler(
    source_edge_list: list,
    qpu: DWaveSampler,
    *,
    embedding_directory: str = EMBEDDINGS_PATH,
    embedding_timeout: int | float = 0,
    max_num_emb: int = None,
    ensemble: str = None,
) -> tuple[dimod.Sampler | None, dict]:
    """This function generates a sampler (either a QPU or a SA sampler), appropriately
    parameterized based on the input to this function.


    Args:
        source_edge_list: A list of couplers relevant to the programmed Hamiltonian
        qpu: A DWaveSampler
        embedding_directory: Path to the embedding repo
        embedding_timeout: If embeddings are not found, time in seconds to allocate for search.
            Note that this process may be iterated (if `max_num_emb` is None, or larger than 1),
            and so the timeout may be up to 2 times larger.  # REMOVE LATER (MAKE EMBEDDING SEARCH SEPARATE HELPER FUNCTION)
        max_num_emb: When embeddings are not found in the path, a bound on the number
            if embeddings to attempt to find. By default None (unbounded).  # REMOVE LATER (MAKE EMBEDDING SEARCH SEPARATE HELPER FUNCTION)
        ensemble: When specified to a supported ensemble additional information
            settings are adjusted for the find_subgraph embedding utility.  # REMOVE LATER (MAKE EMBEDDING SEARCH SEPARATE HELPER FUNCTION)
    Returns:
        tuple: A sampler aggregating samplesets from random parallel QPU embeddings
    """

    # Improvement: the sampler and kwargs should probably be separated into two functions.
    if qpu is None:
        raise ValueError(
            "QPU might be instantiated on the fly in principle, in practice managing many clients results in inefficiencies."
        )
    if ensemble is not None:
        # Use ensemble-specific dimer orientation properties to accelerate search:
        node_labels = (
            source_dimer_orientation(set(n for e in source_edge_list for n in e), ensemble),
            target_dimer_orientation(qpu),
        )
        find_subgraph_kwargs = {
            "timeout": embedding_timeout,
            "node_labels": node_labels,
        }
    else:
        # The ensemble should be known to assert a dimer orientation:
        find_subgraph_kwargs = {"timeout": embedding_timeout}

    embeddings = get_embeddings(
        source_edge_list,
        qpu.edgelist,
        embedding_directory=embedding_directory,
        embedding_timeout=embedding_timeout,
        max_num_emb=max_num_emb,
        find_subgraph_kwargs=find_subgraph_kwargs,
    )
    if len(embeddings) == 0:
        raise Exception(f"Embeddings not found at {embedding_directory}")
        return None, {}
    # Improvement: (and to match paper implementation) make Automorphism composite inner loop
    # Improvement: allow seeding for reproducibility of SRT and automorphisms.
    sampler = AutomorphismComposite(
        ParallelEmbeddingComposite(
            SpinReversalTransformComposite(qpu),
            embeddings=embeddings,
            source=nx.from_edgelist(source_edge_list),
        )
    )
    return sampler
