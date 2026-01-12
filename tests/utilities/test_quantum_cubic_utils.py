import dimod
from dwave.system import DWaveSampler
from dwave.system.testing import MockDWaveSampler

from src.utilities.quantum_cubic_utils import (
    dimerize_coupling_3d,
    get_embeddings,
    displace_n_by_c,
    create_lattice,
    create_model,
    build_stats,
    generate_default_sampler,
    source_dimer_orientation,
    target_dimer_orientation,
)

try:
    qpu_client = DWaveSampler()
    client_unavailable = False
except:
    client_unavailable = True


def test_get_embeddings():
    # Improvemnet, test some graph known to be in the repo and verify embeddings.
    edge_list_source = [(0, 1), (1, 2)]  # source nodes are ints.
    edge_list_target = [(-1, -2)] + [
        (n1 + 3 * i, n2 + 3 * i) for i in range(2) for n1, n2 in edge_list_source
    ]  # Target nodes are ints
    # There are only 2 viable disjoint embeddings:
    # e.g. {i: i for i in range(3)} or {i: 3+i for i in range(3)}
    # or reflections thereof
    embs = get_embeddings(
        edge_list_source=edge_list_source,
        edge_list_target=edge_list_target,
        embedding_directory="./",  # absent
        embedding_timeout=10,  # Plenty of time.
        max_num_emb=None,
        save_to_cache=False,
        verify_embeddings=True,
    )
    assert len(embs) == 2
    assert all(len(emb) == 3 for emb in embs)
    assert set(v[0] for v in embs[0].values()) == set(range(3)) or set(
        v[0] for v in embs[1].values()
    ) == set(range(3))
    embs2 = get_embeddings(
        edge_list_source=edge_list_source,
        edge_list_target=edge_list_target,
        embedding_directory="./",  # absent
        embedding_timeout=0,
        max_num_emb=0,
        save_to_cache=True,
        verify_embeddings=True,
    )  # Loads successfully
    assert all(e1 == e2 for e1, e2 in zip(embs, embs2))


def test_dimerize_coupling_3d():
    for z_parity in [0, 1]:
        e = dimerize_coupling_3d((0, 0, 1), (1, 0, 0), z_parity=z_parity, lattice_dims=(2, 2, 2))
        assert all(len(n) == 4 for n in e)


def test_displace_n_by_c():
    n = (0, 1, 2, 3)
    c = (1, 1, 3, 0)
    modulo = (2, 2, 4, 4)
    n2 = displace_n_by_c(n, c, modulo)
    assert n2 == (1, 0, 1, 3)


def test_create_lattice():
    node_list, edge_list = create_lattice(lattice_dims=(4, 4), dim_periodicity=(False, False))
    for L in [3, 4]:
        for dim_periodicity in [(False, False, False), (False, False, True)]:
            node_list, edge_list = create_lattice(
                lattice_dims=(L, L, L),
                dim_periodicity=dim_periodicity,
            )
            node_list, edge_list = create_lattice(
                lattice_dims=(L, L, L),
                dim_periodicity=dim_periodicity,
            )

            assert len(node_list) == L * L * L * 2
            simple_num_edges = 3 * L * L * (L - 1) + int(dim_periodicity[2]) * L * L
            assert (
                len(edge_list) == simple_num_edges + L**3
            ), "Expected simple-lattice edges plus one additional edge per dimer"


def test_create_model():
    h, J = create_model(seed=10)
    assert type(h) is dict
    assert type(J) is dict
    h2, J2 = create_model(seed=10)

    assert len(list(h2.keys())[0]) == 4, "dimerized cubic"
    assert all(n == n1 for n, n1 in zip(h.items(), h2.items()))
    assert all(e == e1 for e, e1 in zip(J.items(), J2.items()))


def test_build_stats():
    sampler = dimod.ExactSolver()
    response = sampler.sample_ising({i: 1 for i in range(3)}, {})

    for edge_list in [[(0, 1)], list((i, j) for i in range(3) for j in range(i))]:
        corrs = build_stats(response, edge_list=edge_list)
        assert all(0 == c for c in corrs)


def test_target_dimer_orientation():
    # First qubit is always vertical, final qubit is always horizontal
    # defect free cases
    for topology_type in ["chimera", "pegasus", "zephyr"]:
        qpu = MockDWaveSampler(topology_type=topology_type)
        orientations = target_dimer_orientation(qpu)
        assert orientations[qpu.nodelist[0]] == "vertical"
        assert orientations[qpu.nodelist[-1]] == "horizontal"


def test_source_dimer_orientation():
    int_to_str = {0: "vertical", 1: "horizontal"}
    for args in [[], [(4, 4), (True, False)]]:
        node_list, _ = create_lattice(*args)
        orientations = source_dimer_orientation(node_list)
        assert all(
            int_to_str[k[-1]] == v for k, v in orientations.items()
        ), "dimer (final) index does not match orientation"


def test_generate_default_sampler():
    source_edge_list = [((0,0,0,0), (0,0,0,1))]
    t = 4
    qpu = MockDWaveSampler(topology_type="chimera", topology_shape=[1, 1, t])
    sampler = generate_default_sampler(
        source_edge_list, qpu=qpu, embedding_timeout=10  # To avoid QPU default
    )  # find embeddings
    assert len(sampler.child.embeddings) == t
