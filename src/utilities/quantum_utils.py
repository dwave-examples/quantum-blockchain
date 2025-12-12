from dwave.samplers import SimulatedAnnealingSampler
from dwave.system import DWaveSampler, FixedEmbeddingComposite
import minorminer.subgraph  # Thank you McCresh et al., Glasgow U.
import networkx as nx
import numpy as np
import scipy.stats


def uint64_to_bitarray(stats_int: np.ndarray) -> np.ndarray:
    """This function takes an array of integer statistics and
    returns their bit representation

    Args:
        stats_int (np.ndarray): The input statistics

    Returns:
        np.ndarray: The bit representation of the input stats.
    """
    stats_int = np.flip(np.reshape(stats_int.view(np.uint8), (len(stats_int), 8)), axis=1)
    bit_array = np.unpackbits(stats_int.view(np.uint8), axis=1)
    return bit_array


def stat_to_uint64(stat):
    # stats are bounded below by 0 (widths) and above by N, divide by N for [0,1] number.
    # Take 64 bits, must of which are junk
    if np.any(0 > stat):
        raise ValueError("Input value bounded below by 0")
    if np.any(1 < stat):
        raise ValueError("Input value bounded above by 1")
    return np.uint64(stat * np.iinfo(np.uint64).max)


def default_ising_model(
    lattice_size: int = 8, random_seed: int = None, verbose: bool = False
):  # use_qpu is for now a global variable
    """Creates a lattice_size x lattice_size square lattice high-precision spin glass"""

    prng = np.random.default_rng(random_seed)
    # L = 8 - int(use_qpu)*2  # QPU find embedding is slow for L>=7
    if verbose:
        print(f"Default to {lattice_size}x{lattice_size} spin glass, Jij in [-1,1]")
    # Square lattice high precision spin-glass
    J = {
        ((x, y), ((x + disp[0]) % lattice_size, (y + disp[1]) % lattice_size)): 1
        - 2 * prng.random()
        for x in range(lattice_size)
        for y in range(lattice_size)
        for disp in [(0, 1), (1, 0)]
    }
    # h = {(x,y): 0 for x in range(lattice_size) for y in range(lattice_size)}  # h is assumed ordered, python 3.10
    h = {
        (x, y): 2 * (prng.random() - 0.5) for x in range(lattice_size) for y in range(lattice_size)
    }
    # h = {n: (2*(np.random.rand()-.5)) for n in node_list}
    return h, J


def generate_Jdense(JJ: dict, hh: np.ndarray) -> np.ndarray:
    """From a dictionary of Jij and a dictionary of local fields, generate a dense
    representation of the coupling matrix.

    Args:
        JJ (dict): A dictionary of the form {((x1, y1), (x2, y2)): Jij} where Jij is the
            coupling strength between spins at (x1, y1) and (x2, y2).
        hh (np.ndarray): The local fields.

    Returns:
        _type_: _description_
    """
    num_var = len(hh)
    node_list = list(hh.keys())
    label_to_intlabel = {n: idx for idx, n in enumerate(node_list)}

    Jdense = np.zeros(shape=(num_var, num_var))
    for n1n2, Jn1n2 in JJ.items():
        n1 = label_to_intlabel[n1n2[0]]
        n2 = label_to_intlabel[n1n2[1]]
        Jdense[n1, n2] = Jn1n2
        Jdense[n2, n1] = Jn1n2

    return Jdense


def generate_default_sampler(
    J: dict,
    num_reads: int = 10000,
    use_qpu: bool = False,
    verbose: bool = False,
    seed: int = None,
    profile: str = None,
) -> tuple:
    """This function generates a sampler (either a QPU or a SA sampler), appropriately
    parameterized based on the input to this function.

    Args:
        J (dict): A dictionary of the form {((x1, y1), (x2, y2)): Jij} where Jij is the
            coupling strength between spins at (x1, y1) and (x2, y2).
        num_reads (int, optional): The number of reads to perform. Defaults to 10000.
        use_qpu (bool, optional): Whether to use a QPU or not. Defaults to False, which
            means that a SA sampler will be used.
        verbose (bool, optional): Whether to print out verbose information. Defaults to False.
        seed (int, optional): The seed for the random number generator. Defaults to None.

    Returns:
        tuple: A tuple containing the sampler and the sampler_kwargs.
    """
    if use_qpu:
        qpu = DWaveSampler(profile=profile)
        # Use embedding composite, not too large J
        # we can get a subgraph embedding:
        # We should use larger J, or this is
        # very wasteful (can parallelize/tile in small
        # J, might add later)
        source_graph = nx.from_edgelist(J.keys())
        target_graph = qpu.to_networkx_graph()
        if verbose:
            print(
                "Searching for a subgraph, this can be slow "
                "depending on the solver and J, makes sense to cache "
                "if the same coupling topology is reused."
            )
        embedding = minorminer.subgraph.find_subgraph(source_graph, target_graph)
        if verbose:
            print("Embedding found")
        sampler = FixedEmbeddingComposite(qpu, embedding={k: (v,) for k, v in embedding.items()})
        sampler_kwargs = dict(
            num_reads=num_reads,
            answer_mode="raw",
            fast_anneal=True,
            annealing_time=0.005,  # 5 nanosecs.
            auto_scale=False,
        )
    else:
        if verbose:
            print(
                "Placeholder SA sampler has been tuned to look"
                "somewhat like QPU at 5ns for square lattice SG"
            )
        sampler = SimulatedAnnealingSampler()

        # These two dependent parameters are required for reasonable
        # spoofing:
        beta_max = 3  # Limits how spiky equilibrated distribution is.
        num_sweeps = 16  # Controls how equilibrated distribution is.
        # Approx match: (1) mean energy and (2) rate of local excitations.

        sampler_kwargs = {
            "beta_range": [1 / np.sqrt(np.sum([Jij**2 for Jij in J.values()])), beta_max],
            "num_reads": num_reads,
            "num_sweeps": num_sweeps,  # Controls ohw out-of-equilibrium
            "randomize_order": True,
            "seed": seed,
        }
    return sampler, sampler_kwargs


def bit_correlation(bit_array: np.ndarray) -> np.ndarray:
    """This function calculates the correlation matrix of a bit array.

    Args:
        bit_array (np.ndarray): The input bit array.

    Returns:
        np.ndarray: The mean correlations for each row against all other rows.
    """

    correlation_matrix = np.corrcoef(bit_array)
    mean_correlation = (correlation_matrix.sum(1) - np.diag(correlation_matrix)) / (
        correlation_matrix.shape[1] - 1
    )

    return mean_correlation


def bit_bias(bit_array: np.ndarray) -> np.ndarray:
    """This function calculates the bias of a bit array.

    Args:
        bit_array (np.ndarray): The input bit array.

    Returns:
        np.ndarray: The bias of each bit.
    """
    if type(bit_array) is not np.ndarray:
        try:
            bit_array = np.array(bit_array)
        except:
            raise ValueError("Input bit_array must be a numpy array.")
    bias = abs(bit_array.mean(axis=1) - 0.5)
    return 2 * bias


def collision_rate(bit_array1: np.ndarray, bit_array2: np.ndarray) -> np.ndarray:
    """This function calculates the collision rate between two bit arrays.

    Args:
        bit_array1 (np.ndarray): The first bit array.
        bit_array2 (np.ndarray): The second bit array.

    Returns:
        np.ndarray: The collision rate between the two bit arrays.
    """
    collision_rate = np.mean(bit_array1 == bit_array2)
    return collision_rate


def sigma_confidence_interval(df: int, sigma: float, alpha: float) -> list[float, float]:
    """This function calculates the confidence interval for the standard deviation
    of a sample. The confidence interval is calculated using the chi-squared
    distribution.

    Args:
        df (int): The degrees of freedom (n-1 for independent samples)
        sigma (float): The standard deviation.
        alpha (float): The confidence level.

    """
    lower_bound = sigma * np.sqrt(df / scipy.stats.chi2.ppf(1 - alpha / 2, df))
    upper_bound = sigma * np.sqrt(df / scipy.stats.chi2.ppf(alpha / 2, df))
    confidence_interval = [lower_bound, upper_bound]
    return confidence_interval


def build_stats(
    samples: np.ndarray, J: dict, h: np.ndarray, bound: bool = True, weights: np.ndarray = None
) -> np.ndarray:
    """This function builds the statistics from the sampled output.

    Args:
        samples (np.ndarray, optional): An array of shape (num_samples, num_vars)
            containing the sampled output (for spin vars this would be a
            matrix of -1 and 1 values). Samples cannot be None.
        Jdense (np.ndarray, optional): The dense representation of the coupling
            matrix, which is required for generating the eigenvectors, if
            the eigenvectors are not provided. Defaults to None, in which
            case the eigenvectors must be provided.
        bound (bool, optional): Whether to bound the stats by the number
            of variables in the system. Defaults to True.
        weights (np.ndarray, optional): The weights to use when calculating
            the statistics. Defaults to None.


    Returns:
        stats: An array of the output statistics.
    """
    # N stats, could take something like energy, correlations
    assert samples is not None
    Jdense = generate_Jdense(J, h)
    eigenvals, eigenvecs = np.linalg.eigh(Jdense)
    corrs = (
        np.einsum("si,sj->ij", samples, samples) / samples.shape[0]
    )  # sample values should be floats
    stats = np.einsum("ix,jx,ij->x", eigenvecs, eigenvecs, corrs)[:, np.newaxis]

    if bound:
        stats = stats / eigenvecs.shape[1]  # Bounded by N
    if weights is not None:
        stats = np.mean(stats * weights[:, np.newaxis], axis=0)[np.newaxis, :]  # Accumulate
    return stats


if __name__ == "__main__":
    J = np.random.randint(-3, 3, size=(8, 8))
    # convert J to dictionary of (i,j): Jij
    JJ = {(i, j): J[i, j] for i in range(8) for j in range(8)}
    hh = {i: 1 for i in range(8)}

    sampler, sampler_kwargs = generate_default_sampler(
        JJ, num_reads=1000, use_qpu=False, verbose=True, profile="defaults"
    )
    sampler_kwargs["J"] = JJ
    sampler_kwargs["h"] = hh
    sampler_output = sampler.sample_ising(**sampler_kwargs)
    import dimod

    energies = [
        dimod.utilities.ising_energy(sample, hh, JJ) for sample in sampler_output.record.sample
    ]
