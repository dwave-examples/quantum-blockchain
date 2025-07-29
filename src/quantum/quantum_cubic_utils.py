import hashlib

from itertools import product
import os
import pickle
from typing import Optional
import warnings  # temporary


import dimod
import numpy as np

import dwave
from dwave.preprocessing.composites import SpinReversalTransformComposite
from dwave.system import DWaveSampler
from dwave.samplers import SimulatedAnnealingSampler
import minorminer.subgraph  # TODO Used cached values instead

import networkx as nx
import pynauty


def get_permutations(Gembeddable):
    """From latqa"""
    Gpn = pynauty.Graph(Gembeddable.number_of_nodes())
    node_index_dict = {n: i for i, n in enumerate(Gembeddable.nodes)}
    for u, v in Gembeddable.edges:
        Gpn.connect_vertex(node_index_dict[u], node_index_dict[v])
        # Gpn.connect_vertex(node_index_dict[v], node_index_dict[u])
    return np.array(pynauty.autgrp(Gpn)[0]), {
        n: i for i, n in node_index_dict.items()
    }  # automorphism generators


def get_energy_scale(solver, adv_fudge_factor=1):
    # To do: better to scale down energy than scale up time??
    # To do: consider removing this fudge factor, minimal impact and not well controlled?
    if adv_fudge_factor is None:  # legacy
        adv_fudge_factor = 5 / 5.2
    if (
        solver == "Advantage2_prototype2.6"
        or solver == "Advantage2_prototype2_x_internal"
    ):
        return 1
    elif solver == "Advantage_system4.1":
        return 0.535 * adv_fudge_factor
    elif solver == "Advantage_system6.4":
        return 0.488 * adv_fudge_factor
    elif solver == "Advantage_system7.1":
        return 0.458 * adv_fudge_factor
    elif solver == "BAY20_Z12_ALPHA":
        return 1.32
    elif solver == "Advantage2_system1.1":# Old name "BAY3_Z6_ALPHA":
        return 1.32
    else:
        raise ValueError("Unknown energy scale")


def get_GA_solver_energy_scales(scheme=None, return_energies=True):
    """Available solvers and associated energy scales"""
    # By collapse of energy PMJ (Uniform)
    if scheme is None:
        solvers = {
            "Advantage2_prototype2.6",
            "Advantage_system4.1",  # (0.543)
            "Advantage_system6.4",  # (0.488)
            "Advantage_system7.1",
        }
    elif scheme == "Adv2":
        solvers = {
            "Advantage2_prototype2_x_internal",
            "BAY20_Z12_ALPHA",
            "BAY3_Z6_ALPHA",
        }
    else:
        raise ValueError("Unknown scheme")
    if return_energies:
        return {solver: get_energy_scale(solver) for solver in solvers}
    else:
        return solvers


def random_key_map(nodes, seed=None, L=None):
    if L is None:
        L = max(v[0] for v in nodes) + 1
    prng = np.random.default_rng(seed)
    key_map = {k: k for k in nodes}
    offset_z = prng.integers(L)
    key_map = {k: (v[0], v[1], (v[2] + offset_z) % L, v[3]) for k, v in key_map.items()}

    for f0, f1, f2 in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
        flip = prng.integers(2)
        key_map = {
            k: (
                v[0] + flip * f0 * (L - 1 - 2 * v[0]),
                v[1] + flip * f1 * (L - 1 - 2 * v[1]),
                v[2] + flip * f2 * (L - 1 - 2 * v[2]),
                v[3],
            )
            for k, v in key_map.items()
        }
    flip_xy = prng.integers(2)
    key_map = {
        k: (
            v[0] * (1 - flip_xy) + v[1] * flip_xy,
            v[1] * (1 - flip_xy) + v[0] * flip_xy,
            v[2],
            (v[3] + flip_xy) % 2,
        )
        for k, v in key_map.items()
    }
    return key_map


def generator_shuffle(
    i_to_map, generators, seed=None, num_shuffles=4
):  # Yes its fast mixing
    prng = np.random.default_rng(seed)
    for _ in range(num_shuffles):
        for generator in generators[0]:
            i_to_map = {i_to_map[idx]: i_to_map[i] for idx, i in enumerate(generator)}

    return i_to_map


def shuffle_embedding(embedding, seed=None, L=None, generators=None):
    """Permute keys"""
    if generators is not None:
        key_map = generator_shuffle({k: k for k in embedding.keys()}, generators)
    else:
        key_map = random_key_map(embedding.keys(), seed=seed, L=L)
    return {key_map[k]: v for k, v in embedding.items()}


def get_embeddings(
    edgelist_source,
    edgelist_target,
    apply_key_automorphism=True,
    key_automorphism_seed=None,
    embedding_directory: str = "./embeddings",
    generators=None,
) -> list[dict]:
    """Check for embeddings compatible with source and target edgelist hashes.
    Return as list of embeddings.
    """
    eS = hashlib.sha256(str(tuple(sorted(edgelist_source))).encode()).hexdigest()
    eT = hashlib.sha256(str(tuple(sorted(edgelist_target))).encode()).hexdigest()
    embedding_filename = os.path.join(embedding_directory, f"emb_S{eS}_T{eT}.pkl")
    if os.path.isfile(embedding_filename):
        with open(embedding_filename, "rb") as f:
            embeddings = pickle.load(f)
    else:
        embeddings = []
    if apply_key_automorphism:
        # We can randomize the embedding, important for noise mitigation
        prng = np.random.default_rng(key_automorphism_seed)
        embeddings = [
            shuffle_embedding(embedding, seed=prng, generators=generators)
            for embedding in embeddings
        ]
    # Format as iterable:
    embeddings = [{k: (v,) for k, v in emb.items()} for emb in embeddings]
    return embeddings


class ParallelEmbeddingsComposite(
    dimod.Sampler, dimod.Structured
):  # dimod.ComposedSampler):
    """Sample many disjoint embeddings in parallel and aggregate results

    Basically the TilingComposite but without the garbage find embeddings code.
    """

    nodelist = []
    edgelist = []
    parameters = []
    properties = []

    def __init__(self, child_sampler, embeddings, edgelist=[], generators=None):
        self.nodelist = []
        if len(embeddings) > 0:
            self.nodelist = list(embeddings[0].keys())

        self.edgelist = edgelist

        self.embeddings = embeddings

        self.child = child_sampler

        # set the parameters
        self.parameters = child_sampler.parameters.copy()

        # set the properties
        self.properties = dict(child_properties=child_sampler.properties.copy())

        self.generators = generators
        # self.target_structure = child_structure_search(child_sampler) # Not used (for now)

    @dimod.bqm_structured
    def sample(self, bqm, randomize_embedding=True, num_programmings=1, **kwargs):
        """Sample from the specified binary quadratic model.

        Args:
            bqm (:obj:`~dimod.BinaryQuadraticModel`):
                Binary quadratic model to be sampled from.

            **kwargs:
                Optional keyword arguments for the sampling method, specified per solver.

        Returns:
            :class:`~dimod.SampleSet`

        Examples:
            This example submits a simple Ising problem of just two variables on a
            D-Wave system.
            Because the problem fits in a single :term:`Chimera` unit cell, it is tiled
            across the solver's entire Chimera graph, resulting in multiple samples
            (the exact number depends on the working Chimera graph of the D-Wave system).

            >>> from dwave.system import DWaveSampler, EmbeddingComposite
            >>> from dwave.system import TilingComposite
            ...
            >>> sampler = EmbeddingComposite(TilingComposite(DWaveSampler(), 1, 1, 4))
            >>> sampleset = sampler.sample_ising({},{('a', 'b'): 1})
            >>> len(sampleset) > 1
            True

        See `Ocean Glossary <https://docs.ocean.dwavesys.com/en/stable/concepts/index.html>`_
        for explanations of technical terms in descriptions of Ocean tools.

        """
        if num_programmings > 1:
            responses = [
                self.sample(bqm, randomize_embedding=True, **kwargs)
                for _ in range(num_programmings)
            ]
            response = dimod.concatenate(responses)
            response.info.update(responses[0].info)
            return response
        # apply the embeddings to the given problem to tile it across the child sampler
        embedded_bqm = dimod.BinaryQuadraticModel.empty(bqm.vartype)
        try:
            __, __, target_adjacency = self.child.structure
        except:
            __, __, target_adjacency = (
                self.child.child.structure
            )  # SpinReversalComposite problem!
        if randomize_embedding:
            _embs = [
                shuffle_embedding(emb, generators=self.generators)
                for emb in self.embeddings
            ]
        else:
            _embs = self.embeddings
        for embedding in _embs:
            embedded_bqm.update(
                dwave.embedding.embed_bqm(bqm, embedding, target_adjacency)
            )

        # solve the problem on the child system
        tiled_response = self.child.sample(embedded_bqm, **kwargs)

        responses = []

        for embedding in _embs:
            embedding = {
                v: chain for v, chain in embedding.items() if v in bqm.variables
            }

            responses.append(
                dwave.embedding.unembed_sampleset(tiled_response, embedding, bqm)
            )

        answer = dimod.concatenate(responses)
        answer.info.update(tiled_response.info)

        return answer


def dimerize_coupling_3d(n1, n2, z_parity, modulo):
    # x are 0,0; y are 1,1 ; z are (0,1), (1,0); both or random. The former two cases break reflection symmetry in x,y
    if (n2[0] - n1[0]) % modulo[0] == 1 or (n2[0] - n1[0]) % modulo[0] == modulo[0] - 1:
        d1 = d2 = 0
    elif (n2[1] - n1[1]) % modulo[1] == 1 or (n2[1] - n1[1]) % modulo[1] == modulo[
        1
    ] - 1:
        d1 = d2 = 1
    elif (n2[2] - n1[2]) % modulo[2] == 1:
        d1 = z_parity
        d2 = 1 - z_parity
    elif (n2[2] - n1[2]) % modulo[2] == modulo[2] - 1:
        d1 = 1 - z_parity
        d2 = z_parity
    else:
        raise ValueError("bad spec")
    return n1 + (d1,), n2 + (d2,)


def disp_n(n, c: tuple[int, int] = (0, 1), modulo: tuple[int, int] = (1000, 1000)):
    return tuple((n[i] + c[i]) % modulo[i] for i in range(len(n)))


def create_dimerizedbiclique(dimensions=18):
    edge_list = [
        (0, 1),
        (0, 48),
        (0, 56),
        (0, 50),
        (0, 58),
        (0, 52),
        (0, 60),
        (0, 54),
        (0, 62),
        (1, 80),
        (1, 64),
        (1, 88),
        (1, 72),
        (1, 82),
        (1, 66),
        (1, 90),
        (1, 74),
        (1, 84),
        (1, 68),
        (1, 92),
        (1, 76),
        (1, 86),
        (1, 70),
        (1, 94),
        (1, 78),
        (8, 9),
        (8, 48),
        (8, 64),
        (8, 56),
        (8, 72),
        (8, 50),
        (8, 66),
        (8, 58),
        (8, 74),
        (8, 52),
        (8, 68),
        (8, 60),
        (8, 76),
        (8, 54),
        (8, 70),
        (8, 62),
        (8, 78),
        (9, 80),
        (9, 88),
        (9, 82),
        (9, 90),
        (9, 84),
        (9, 92),
        (9, 86),
        (9, 94),
        (2, 3),
        (2, 48),
        (2, 56),
        (2, 50),
        (2, 58),
        (2, 52),
        (2, 60),
        (2, 54),
        (2, 62),
        (3, 80),
        (3, 64),
        (3, 88),
        (3, 72),
        (3, 82),
        (3, 66),
        (3, 90),
        (3, 74),
        (3, 84),
        (3, 68),
        (3, 92),
        (3, 76),
        (3, 86),
        (3, 70),
        (3, 94),
        (3, 78),
        (10, 11),
        (10, 48),
        (10, 64),
        (10, 56),
        (10, 72),
        (10, 50),
        (10, 66),
        (10, 58),
        (10, 74),
        (10, 52),
        (10, 68),
        (10, 60),
        (10, 76),
        (10, 54),
        (10, 70),
        (10, 62),
        (10, 78),
        (11, 80),
        (11, 88),
        (11, 82),
        (11, 90),
        (11, 84),
        (11, 92),
        (11, 86),
        (11, 94),
        (4, 5),
        (4, 48),
        (4, 56),
        (4, 50),
        (4, 58),
        (4, 52),
        (4, 60),
        (4, 54),
        (4, 62),
        (5, 80),
        (5, 64),
        (5, 88),
        (5, 72),
        (5, 82),
        (5, 66),
        (5, 90),
        (5, 74),
        (5, 84),
        (5, 68),
        (5, 92),
        (5, 76),
        (5, 86),
        (5, 70),
        (5, 94),
        (5, 78),
        (12, 13),
        (12, 48),
        (12, 64),
        (12, 56),
        (12, 72),
        (12, 50),
        (12, 66),
        (12, 58),
        (12, 74),
        (12, 52),
        (12, 68),
        (12, 60),
        (12, 76),
        (12, 54),
        (12, 70),
        (12, 62),
        (12, 78),
        (13, 80),
        (13, 88),
        (13, 82),
        (13, 90),
        (13, 84),
        (13, 92),
        (13, 86),
        (13, 94),
        (6, 7),
        (6, 48),
        (6, 56),
        (6, 50),
        (6, 58),
        (6, 52),
        (6, 60),
        (6, 54),
        (6, 62),
        (7, 80),
        (7, 64),
        (7, 88),
        (7, 72),
        (7, 82),
        (7, 66),
        (7, 90),
        (7, 74),
        (7, 84),
        (7, 68),
        (7, 92),
        (7, 76),
        (7, 86),
        (7, 70),
        (7, 94),
        (7, 78),
        (14, 15),
        (14, 48),
        (14, 64),
        (14, 56),
        (14, 72),
        (14, 50),
        (14, 66),
        (14, 58),
        (14, 74),
        (14, 52),
        (14, 68),
        (14, 60),
        (14, 76),
        (14, 54),
        (14, 70),
        (14, 62),
        (14, 78),
        (15, 80),
        (15, 88),
        (15, 82),
        (15, 90),
        (15, 84),
        (15, 92),
        (15, 86),
        (15, 94),
        (16, 17),
        (16, 56),
        (16, 58),
        (16, 60),
        (16, 62),
        (16, 49),
        (16, 51),
        (16, 53),
        (16, 55),
        (17, 88),
        (17, 72),
        (17, 90),
        (17, 74),
        (17, 92),
        (17, 76),
        (17, 94),
        (17, 78),
        (17, 81),
        (17, 65),
        (17, 83),
        (17, 67),
        (17, 85),
        (17, 69),
        (17, 87),
        (17, 71),
        (24, 25),
        (24, 56),
        (24, 72),
        (24, 58),
        (24, 74),
        (24, 60),
        (24, 76),
        (24, 62),
        (24, 78),
        (24, 49),
        (24, 65),
        (24, 51),
        (24, 67),
        (24, 53),
        (24, 69),
        (24, 55),
        (24, 71),
        (25, 88),
        (25, 90),
        (25, 92),
        (25, 94),
        (25, 81),
        (25, 83),
        (25, 85),
        (25, 87),
        (18, 19),
        (18, 56),
        (18, 58),
        (18, 60),
        (18, 62),
        (18, 49),
        (18, 51),
        (18, 53),
        (18, 55),
        (19, 88),
        (19, 72),
        (19, 90),
        (19, 74),
        (19, 92),
        (19, 76),
        (19, 94),
        (19, 78),
        (19, 81),
        (19, 65),
        (19, 83),
        (19, 67),
        (19, 85),
        (19, 69),
        (19, 87),
        (19, 71),
        (26, 27),
        (26, 56),
        (26, 72),
        (26, 58),
        (26, 74),
        (26, 60),
        (26, 76),
        (26, 62),
        (26, 78),
        (26, 49),
        (26, 65),
        (26, 51),
        (26, 67),
        (26, 53),
        (26, 69),
        (26, 55),
        (26, 71),
        (27, 88),
        (27, 90),
        (27, 92),
        (27, 94),
        (27, 81),
        (27, 83),
        (27, 85),
        (27, 87),
        (20, 21),
        (20, 56),
        (20, 58),
        (20, 60),
        (20, 62),
        (20, 49),
        (20, 51),
        (20, 53),
        (20, 55),
        (21, 88),
        (21, 72),
        (21, 90),
        (21, 74),
        (21, 92),
        (21, 76),
        (21, 94),
        (21, 78),
        (21, 81),
        (21, 65),
        (21, 83),
        (21, 67),
        (21, 85),
        (21, 69),
        (21, 87),
        (21, 71),
        (28, 29),
        (28, 56),
        (28, 72),
        (28, 58),
        (28, 74),
        (28, 60),
        (28, 76),
        (28, 62),
        (28, 78),
        (28, 49),
        (28, 65),
        (28, 51),
        (28, 67),
        (28, 53),
        (28, 69),
        (28, 55),
        (28, 71),
        (29, 88),
        (29, 90),
        (29, 92),
        (29, 94),
        (29, 81),
        (29, 83),
        (29, 85),
        (29, 87),
        (22, 23),
        (22, 56),
        (22, 58),
        (22, 60),
        (22, 62),
        (22, 49),
        (22, 51),
        (22, 53),
        (22, 55),
        (23, 88),
        (23, 72),
        (23, 90),
        (23, 74),
        (23, 92),
        (23, 76),
        (23, 94),
        (23, 78),
        (23, 81),
        (23, 65),
        (23, 83),
        (23, 67),
        (23, 85),
        (23, 69),
        (23, 87),
        (23, 71),
        (30, 31),
        (30, 56),
        (30, 72),
        (30, 58),
        (30, 74),
        (30, 60),
        (30, 76),
        (30, 62),
        (30, 78),
        (30, 49),
        (30, 65),
        (30, 51),
        (30, 67),
        (30, 53),
        (30, 69),
        (30, 55),
        (30, 71),
        (31, 88),
        (31, 90),
        (31, 92),
        (31, 94),
        (31, 81),
        (31, 83),
        (31, 85),
        (31, 87),
        (32, 33),
        (32, 49),
        (32, 57),
        (32, 51),
        (32, 59),
        (32, 53),
        (32, 61),
        (32, 55),
        (32, 63),
        (33, 81),
        (33, 65),
        (33, 89),
        (33, 73),
        (33, 83),
        (33, 67),
        (33, 91),
        (33, 75),
        (33, 85),
        (33, 69),
        (33, 93),
        (33, 77),
        (33, 87),
        (33, 71),
        (33, 95),
        (33, 79),
        (40, 41),
        (40, 49),
        (40, 65),
        (40, 57),
        (40, 73),
        (40, 51),
        (40, 67),
        (40, 59),
        (40, 75),
        (40, 53),
        (40, 69),
        (40, 61),
        (40, 77),
        (40, 55),
        (40, 71),
        (40, 63),
        (40, 79),
        (41, 81),
        (41, 89),
        (41, 83),
        (41, 91),
        (41, 85),
        (41, 93),
        (41, 87),
        (41, 95),
        (34, 35),
        (34, 49),
        (34, 57),
        (34, 51),
        (34, 59),
        (34, 53),
        (34, 61),
        (34, 55),
        (34, 63),
        (35, 81),
        (35, 65),
        (35, 89),
        (35, 73),
        (35, 83),
        (35, 67),
        (35, 91),
        (35, 75),
        (35, 85),
        (35, 69),
        (35, 93),
        (35, 77),
        (35, 87),
        (35, 71),
        (35, 95),
        (35, 79),
        (42, 43),
        (42, 49),
        (42, 65),
        (42, 57),
        (42, 73),
        (42, 51),
        (42, 67),
        (42, 59),
        (42, 75),
        (42, 53),
        (42, 69),
        (42, 61),
        (42, 77),
        (42, 55),
        (42, 71),
        (42, 63),
        (42, 79),
        (43, 81),
        (43, 89),
        (43, 83),
        (43, 91),
        (43, 85),
        (43, 93),
        (43, 87),
        (43, 95),
        (36, 37),
        (36, 49),
        (36, 57),
        (36, 51),
        (36, 59),
        (36, 53),
        (36, 61),
        (36, 55),
        (36, 63),
        (37, 81),
        (37, 65),
        (37, 89),
        (37, 73),
        (37, 83),
        (37, 67),
        (37, 91),
        (37, 75),
        (37, 85),
        (37, 69),
        (37, 93),
        (37, 77),
        (37, 87),
        (37, 71),
        (37, 95),
        (37, 79),
        (44, 45),
        (44, 49),
        (44, 65),
        (44, 57),
        (44, 73),
        (44, 51),
        (44, 67),
        (44, 59),
        (44, 75),
        (44, 53),
        (44, 69),
        (44, 61),
        (44, 77),
        (44, 55),
        (44, 71),
        (44, 63),
        (44, 79),
        (45, 81),
        (45, 89),
        (45, 83),
        (45, 91),
        (45, 85),
        (45, 93),
        (45, 87),
        (45, 95),
        (38, 39),
        (38, 49),
        (38, 57),
        (38, 51),
        (38, 59),
        (38, 53),
        (38, 61),
        (38, 55),
        (38, 63),
        (39, 81),
        (39, 65),
        (39, 89),
        (39, 73),
        (39, 83),
        (39, 67),
        (39, 91),
        (39, 75),
        (39, 85),
        (39, 69),
        (39, 93),
        (39, 77),
        (39, 87),
        (39, 71),
        (39, 95),
        (39, 79),
        (46, 47),
        (46, 49),
        (46, 65),
        (46, 57),
        (46, 73),
        (46, 51),
        (46, 67),
        (46, 59),
        (46, 75),
        (46, 53),
        (46, 69),
        (46, 61),
        (46, 77),
        (46, 55),
        (46, 71),
        (46, 63),
        (46, 79),
        (47, 81),
        (47, 89),
        (47, 83),
        (47, 91),
        (47, 85),
        (47, 93),
        (47, 87),
        (47, 95),
        (48, 49),
        (56, 57),
        (50, 51),
        (58, 59),
        (52, 53),
        (60, 61),
        (54, 55),
        (62, 63),
        (64, 65),
        (72, 73),
        (66, 67),
        (74, 75),
        (68, 69),
        (76, 77),
        (70, 71),
        (78, 79),
        (80, 81),
        (88, 89),
        (82, 83),
        (90, 91),
        (84, 85),
        (92, 93),
        (86, 87),
        (94, 95),
    ]
    spins = np.reshape(np.arange(96), (-1, 2))
    if dimensions < 24:
        # Reduce
        spins = spins[np.array([i for i in range(48) if i % 4 < dimensions // 6]), :]
        relabel = {label: ilabel for ilabel, label in enumerate(spins.ravel())}
        edge_list = [
            (relabel[u], relabel[v]) for u, v in edge_list if u in spins and v in spins
        ]
    return np.unique([n for e in edge_list for n in e]), edge_list


def create_lattice(Ls=[10, 10], is_periodic=[False, False], dimerize_lattice=None):
    ndim = len(Ls)
    if dimerize_lattice is None:
        if ndim == 2:
            dimerize_lattice = False
        else:
            dimerize_lattice = True  # 'doubled'
    nodelist = list(product(*[range(l) for l in Ls]))
    nodeset = set(nodelist)
    modulo = [(1 + (not i)) * l for l, i in zip(Ls, is_periodic)]
    cs = [tuple(int(i == j) for i in range(ndim)) for j in range(ndim)]
    edgelist = [
        tuple(sorted([n, disp_n(n, c, modulo)]))
        for n in nodelist
        for c in cs
        if disp_n(n, c, modulo) in nodeset
    ]
    if dimerize_lattice is not False:
        edgeset = {(n + (0,), n + (1,)) for n in nodelist}
        nodelist = [n + (t,) for n in nodelist for t in range(2)]
        edgeset |= {
            dimerize_coupling_3d(n1, n2, z_parity=0, modulo=modulo)
            for n1, n2 in edgelist
        }
        if dimerize_lattice == "doubled":
            edgeset |= {
                dimerize_coupling_3d(n1, n2, z_parity=1, modulo=modulo)
                for n1, n2 in edgelist
            }

        edgelist = sorted(edgeset)
    return nodelist, edgelist


def create_model(
    ensemble, seed, Ls=[4, 4, 4], is_periodic=[False, False, True], dimensions=18
):
    """Create supremacy paper model"""
    prng = np.random.default_rng(seed)
    if ensemble == "DimBiClique":
        nodelist, edgelist = create_dimerizedbiclique(dimensions=dimensions)
        tupledict = {
            v: (v // 36, (v % 36) // 2, (v % 36) % 6 // 2, v % 2) for v in nodelist
        }
        h = {i: 0 for i in nodelist}
        Jlog = 1 / np.sqrt(dimensions)
        J = {
            e: (
                -1.0
                if (tupledict[e[0]][0] == tupledict[e[1]][0])
                else (2 * prng.integers(2) - 1) * Jlog
            )
            for e in edgelist
        }

        assert (
            np.sum([abs(v + 1.0) < 1e-8 for v in J.values()]) == 2 * dimensions
        )  # dimensions^2 logical
        assert np.all(
            np.unique([n for ij, v in J.items() for n in ij if v == -1.0]) == nodelist
        )  ## Sanity check, dimers only can add to unit tests later.
        assert (
            np.sum([abs(v) - Jlog < 1e-8 for v in J.values()]) == dimensions**2
        )  # dimensions^2 logical
    elif ensemble == "PMJ":  # Low precision no-dimer
        nodelist, edgelist = create_lattice(Ls, is_periodic, dimerize_lattice=True)
        J = {ij: 2 * prng.integers(2) - 1 for ij in edgelist}
    elif ensemble == "Uniform":  # High precision no-dimer
        nodelist, edgelist = create_lattice(Ls, is_periodic, dimerize_lattice=True)
        J = {ij: 2 * prng.random() - 1 for ij in edgelist}
    elif ensemble == "PMJC2":  # Low precision cubic-dimer (almost!)
        nodelist, edgelist = create_lattice(Ls, is_periodic, dimerize_lattice="doubled")
        J = {
            ij: (
                2 * prng.integers(2) - 1
                if ij[0][2] != ij[1][2]
                else (2 * prng.integers(2) - 1) / 2
            )
            for ij in edgelist
        }
        J.update({ij: -2 for ij in edgelist if ij[0][:3] == ij[1][:3]})
    elif ensemble == "UniformC2":
        nodelist, edgelist = create_lattice(Ls, is_periodic, dimerize_lattice="doubled")
        J = {
            ij: (
                2 * prng.random() - 1
                if ij[0][2] != ij[1][2]
                else (2 * prng.random() - 1) / 2
            )
            for ij in edgelist
        }
        J.update({ij: -2 for ij in edgelist if ij[0][:3] == ij[1][:3]})
    h = {i: 0 for i in nodelist}

    return h, J


def default_ising_model(L: int = 4, random_seed: int = None, ensemble: str = "PMJ"):
    """Creates a LxLxLx2 embedded cubic lattice, periodic in z-direction, with one coupler
    only per z-orientated couplers (3D nodimer in supremacy paper, up to gauge)"""
    return create_model(
        ensemble=ensemble,
        seed=random_seed,
        Ls=[L] * 3,
        is_periodic=[False, False, True],
    )


def ss_to_corrs(ss, edgelist):
    """Calculate correlations associated to a set of edges"""
    if ss.record.sample.dtype != np.float64:
        _samples = ss.record.sample.astype(float)
    else:
        _samples = ss.record.sample
    nodelist_to_linear = {n: idx for idx, n in enumerate(ss.variables)}
    corrs = np.array(
        [
            np.sum(
                _samples[:, nodelist_to_linear[i]]
                * _samples[:, nodelist_to_linear[j]]
                * ss.record.num_occurrences
            )
            / np.sum(ss.record.num_occurrences)
            for i, j in edgelist
        ]
    )

    return corrs  # Check edges in same orbit for differences averaged on models ...


def build_stats(response: dimod.SampleSet, edgelist) -> np.ndarray:
    """This function builds the statistics from the sampled output.

    Args:
        sampleset: An unembedded dimod sampleset
        edgelist: edges on which to estimate correlations

    Returns:
        stats: An array of the output statistics.
    """

    return ss_to_corrs(response, edgelist)


def get_qpu_access_times(qpu, qpu_kwargs: dict, num_var: int = None):
    if num_var is None:
        num_var = qpu.properties["num_qubits"]
    _qpu_kwargs = qpu_kwargs.copy()
    _qpu_kwargs["num_reads"] = 0
    constant_time = qpu.solver.estimate_qpu_access_time(num_var, **_qpu_kwargs)
    _qpu_kwargs["num_reads"] = 1
    per_read_time = (
        qpu.solver.estimate_qpu_access_time(num_var, **_qpu_kwargs) - constant_time
    )
    return constant_time, per_read_time


def get_max_num_reads(qpu, qpu_kwargs, num_var=None, max_time=float("Inf")):
    """max_time in seconds."""
    estimated_runtime = min(
        qpu.properties["problem_run_duration_range"][1], max_time * 1000000
    )
    constant_time, per_read_time = get_qpu_access_times(
        qpu, qpu_kwargs, num_var=num_var
    )
    if estimated_runtime < constant_time + per_read_time:
        num_reads = 0
    else:
        num_reads = min(
            qpu.properties["num_reads_range"][1],
            int((estimated_runtime - constant_time) / per_read_time),
        )
    # Following code is (now) unnecessary sanity check:
    # _qpu_kwargs["num_reads"] = num_reads
    # assert (
    #     eqat(num_var, **_qpu_kwargs) <= estimated_runtime
    # ), f"{eqat(num_var, **_qpu_kwargs)} <= {estimated_runtime}"
    return num_reads


# Proof of Work protocol should
def generate_default_sampler(
    J: dict,  # J.values() used only by SA, sufficient to provide keys for QPU
    num_reads: Optional[int] = None,  # Use upper bound, unless time contrained
    qpu_access_time_ub: float = float("Inf"),  # max(this value, solver upper bound)
    use_qpu: bool = True,
    verbose: bool = False,
    seed_SA: int = None,
    solver: str = "Advantage2_prototype2.6",  # Minor specific!
    annealing_time=0.005,
    randomize_embedding=False,
    randomize_embedding_seed=None,  # Minor specific!
    qpu=None,
    embedding_directory="./embeddings",
    use_pynauty=False,
) -> tuple:
    """This function generates a sampler (either a QPU or a SA sampler), appropriately
    parameterized based on the input to this function.

    Args:
        J (dict): A dictionary of the form {((x1, y1), (x2, y2)): Jij} where Jij is the
            coupling strength between spins at (x1, y1) and (x2, y2). Note that for QPU
            only the keys() are used and values are assumed to be in programmable range.
        num_reads (int, optional): The number of reads to perform. Defaults to 10000.
        qpu_access_time_ub (float, optional): Upper bound on QPU access time.
        use_qpu (bool, optional): Whether to use a QPU or not. Defaults to False, which
            means that a SA sampler will be used.
        verbose (bool, optional): Whether to print out verbose information. Defaults to False.
        seed (int, optional): The seed for the random number generator. Defaults to None.
        solver (str, QPU solver): Must be general access.
        annealing_time: Adjust the default annealing time for QPU

    Returns:
        tuple: A tuple containing the sampler and the sampler_kwargs.
    """
    if use_pynauty:
        G = nx.Graph()
        G.add_nodes_from(np.unique([n for e in J.keys() for n in e]))
        G.add_edges_from(J.keys())
        generators = get_permutations(G)
    else:
        generators = None
    if use_qpu:
        if qpu is None:
            raise ValueError(
                "QPU must be provided - re-instantiating QPU can result in threading error"
            )
            qpu = DWaveSampler(solver=solver)
        embeddings = get_embeddings(
            J.keys(),
            qpu.edgelist,
            apply_key_automorphism=randomize_embedding,
            key_automorphism_seed=randomize_embedding_seed,
            embedding_directory=embedding_directory,
            generators=generators,
        )
        if len(embeddings) > 0:
            embedding = embeddings[0]  # Modify later, use all embeddings
        else:
            raise ValueError(
                "Embeddings not found, using find_subgraph (should not happen?)"
            )
            embedding = minorminer.subgraph.find_subgraph(J.keys(), qpu.edgelist)
            if randomize_embedding:
                embeddings = [
                    shuffle_embedding(
                        embedding={k: (v,) for k, v in embedding.items()},
                        seed=randomize_embedding_seed,
                        L=None,
                        generators=generators,
                    )
                ]
        # if randomize_embedding: embeddings = [shuffle_graph(embedding) for emb in self.embeddings] (if embeddings not created locally)
        sampler_kwargs = dict(
            num_reads=num_reads,
            fast_anneal=True,
            annealing_time=annealing_time / get_energy_scale(solver),
            auto_scale=False,
        )
        if num_reads is None:
            # num_reads = 2000
            num_reads = get_max_num_reads(
                qpu,
                qpu_kwargs=sampler_kwargs,
                num_var=len(embeddings) * len(embeddings[0]),
                max_time=qpu_access_time_ub,
            )

            sampler_kwargs["num_reads"] = num_reads
        if randomize_embedding:
            # could perhaps avoid branching here, by branching kwargs num_spin_reversal_transforms = 0 or 1 in proof_of_work code when calling sample?
            # sampler = FixedEmbeddingComposite(qpu, embedding={k: (v,) for k,v in embedding.items()})
            sampler = ParallelEmbeddingsComposite(
                SpinReversalTransformComposite(
                    qpu
                ),  # seed SRT would be desirable! can reuse randomize_embedding_seed
                generators=generators,
                embeddings=embeddings,
                edgelist=[(i, j) for i in embedding for j in embedding if i < j],
            )
        else:
            sampler = ParallelEmbeddingsComposite(
                qpu,
                embeddings=embeddings,
                edgelist=[(i, j) for i in embedding for j in embedding if i < j],
            )
    else:
        if num_reads is None:
            num_reads = 1000
        sampler = SimulatedAnnealingSampler()

        # These two dependent parameters are required for reasonable
        # spoofing:
        beta_max = 3  # Limits how spiky equilibrated distribution is.
        num_sweeps = 16  # Controls how equilibrated distribution is.
        # Approx match: (1) mean energy and (2) rate of local excitations.

        sampler_kwargs = {
            "beta_range": [
                1 / np.sqrt(np.sum([Jij**2 for Jij in J.values()])),
                beta_max,
            ],
            "num_reads": num_reads,
            "num_sweeps": num_sweeps,  # Controls ohw out-of-equilibrium
            "randomize_order": True,
            "seed": seed_SA,
        }
    # qpu.client.close()
    return sampler, sampler_kwargs


def unit_test_basic():
    # Move to unit tests later:
    h, J = default_ising_model(4)
    qpu = DWaveSampler(solver="Advantage_system4.1")
    embedding = minorminer.subgraph.find_subgraph(J.keys(), qpu.edgelist)
    embs = [embedding]
    qpu_kwargs = {"annealing_time": 0.005, "fast_anneal": True}
    num_reads = get_max_num_reads(
        qpu, qpu_kwargs, num_var=len(embs[0]) * len(embs), max_time=float("Inf")
    )
    print(
        f"#embs={len(embs)} x #reads={num_reads} = {np.sum(ss.record.num_occurrences)}"
    )
    assert np.sum(ss.record.num_occurrences) == num_reads * len(embs)


def unit_test_functional_BER(
    ensemble="PMJ", num_tests=20, stat_type=None, annealing_time=0.005
):  # Or None for cubic
    """A script used for debugging"""

    from random_projection import RandomProjectionHasher

    # For 100 models and 1024 projections on Adv2 and Adv4.1 measure bit errors within and between.
    expected_num_reads = {}  # Optional checks
    expected_annealing_time = {}  # Optional checks
    randomize_embedding = True
    fudge_factor = 1  # New settings
    if ensemble == "PMJ":
        stat_type = "NN"
        solver = "Advantage2_prototype2.6"
        if annealing_time == 0.005 and fudge_factor == None:
            expected_num_reads = {
                "Advantage2_prototype2.6": 9558,
                "Advantage_system4.1": 3860,
            }
            expected_annealing_time = {
                "Advantage2_prototype2.6": 0.005,
                "Advantage_system4.1": 0.0097196261682243,
            }
        solvers = [
            "Advantage2_prototype2.6",
            "Advantage_system4.1",
            "Advantage_system6.4",
            "Advantage_system7.1",
        ]
        profile = {s: "cloud" for s in solvers}
        use_pynauty = False
    else:
        solver = "Advantage2_prototype2_x_internal"
        solvers = ["Advantage2_prototype2_x_internal", "BAY20_Z12_ALPHA"]
        solvers = [
            "Advantage2_prototype2_x_internal",
            "Advantage2_prototype2_x_internal",
        ]  # Easy
        profile = {
            "Advantage2_prototype2_x_internal": "cloud",
            "BAY20_Z12_ALPHA": "vpn",
        }
        use_pynauty = True
        randomize_embedding = True
        # 'BAY3_Z6_ALPHA'

    h, J = create_model(ensemble, seed=0)  # Only used for qpu access time defaulting.
    if stat_type == "NN":
        stat_edges = J.keys()
    elif stat_type == "Debuggin":  # Yep, that works!
        stat_edges = [
            e for e, v in J.items() if v == -1
        ]  # Frozen out edges! Should be super robust
    else:
        nodelist = list(h.keys())
        stat_edges = [
            (int(n1), int(n2))
            for idx, n1 in enumerate(nodelist)
            for n2 in nodelist[idx:]
        ]

    kwargs0 = dict(
        J=J,  # Used by SA only! Should really just do at ensemble level.
        num_reads=None,  # Use upper bound, unless time contrained
        qpu_access_time_ub=float("Inf"),  # max(this value, solver upper bound)
        use_qpu=True,
        solver=solver,  # Minor specific!
        annealing_time=annealing_time,
        randomize_embedding=randomize_embedding,
        randomize_embedding_seed=None,
        use_pynauty=use_pynauty and randomize_embedding,
    )
    print(solvers)
    qpus = {
        solver: DWaveSampler(solver=solver, profile=profile[solver])
        for solver in solvers
    }
    BitErrorRate = {(s1, s2): [] for s1, s2 in product(solvers, solvers)}
    ValidationRate28 = {(s1, s2): [] for s1, s2 in product(solvers, solvers)}
    NZ = 32
    nbits = NZ * (1024 // NZ)
    for seed in range(num_tests):
        h, J = create_model(ensemble, seed)
        hv = RandomProjectionHasher(
            random_seed=seed + 1, nbits=nbits, input_dimension=len(stat_edges)
        )
        returned_bits = {}
        for solver in solvers:
            kwargs = kwargs0.copy()
            kwargs["solver"] = solver
            sampler, sampler_kwargs = generate_default_sampler(
                **kwargs, qpu=qpus[solver]
            )
            if solver in expected_num_reads:
                assert sampler_kwargs["num_reads"] == expected_num_reads[solver]
            if solver in expected_annealing_time:
                assert (
                    abs(
                        sampler_kwargs["annealing_time"]
                        - expected_annealing_time[solver]
                    )
                    < 1e-8
                )
            sampler_output = sampler.sample_ising(
                h,
                J,
                num_programmings=1,
                randomize_embedding=randomize_embedding,
                **sampler_kwargs,
            )
            stats = build_stats(sampler_output, stat_edges)  ## NN case
            returned_bits[solver] = hv.hash_vector(stats.reshape(-1))[0].reshape(
                (NZ, nbits // NZ)
            )
        for s1 in solvers:
            for s2 in solvers:
                BitErrorRate[(s1, s2)].append(
                    np.mean(returned_bits[s1] != returned_bits[s2])
                )
                ValidationRate28[(s1, s2)].append(
                    np.mean(
                        np.sum(returned_bits[s1] == returned_bits[s2], axis=0) == NZ
                    )
                )
        numelB = (seed + 1) * nbits
        numelV = (seed + 1) * nbits // NZ
        print("Bit Error Rate by solver pair")
        print(solvers)
        print(
            np.array(
                [[np.mean(BitErrorRate[(s1, s2)]) for s1 in solvers] for s2 in solvers]
            )
        )
        print(
            np.array(
                [
                    [np.sqrt(np.var(BitErrorRate[(s1, s2)]) / numelB) for s1 in solvers]
                    for s2 in solvers
                ]
            )
        )

        print(
            "Bit Error Rate",
            np.mean([BER for BER in BitErrorRate.values()]),
            "+/-",
            np.sqrt(
                np.var([BER for BER in BitErrorRate.values()])
                / (numelB * len(BitErrorRate))
            ),
        )
        print(
            f"{NZ}B Validation Rate",
            np.mean([BER for BER in ValidationRate28.values()]),
            "+/-",
            np.sqrt(
                np.var([BER for BER in ValidationRate28.values()])
                / (numelV * len(BitErrorRate))
            ),
        )

    return BitErrorRate, ValidationRate28


if __name__ == "__main__":
    # unit_test_basic()
    print("Expecting BER to be ~< 0.01")
    for annealing_time in [0.015, 0.005]:
        for scheme in ["PMJ", "DimBiClique"]:
            print(annealing_time, scheme)
            unit_test_functional_BER()
