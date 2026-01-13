[![Open in GitHub Codespaces](
  https://img.shields.io/badge/Open%20in%20GitHub%20Codespaces-333?logo=github)](
  https://codespaces.new/dwave-examples/quantum-blockchain?quickstart=1)

# Proof of Quantum Work Blockchains

Ledgers are widespread record keeping structures. A proof of work blockchain is a ledger supported
by concensus mechanisms to ensure that no single authority is required to verify the ledger.
Cryptographically-linked hard problems are solved by miners to encode new transactions.
Transactions can be considered finalized in the ledger because the community is incentived by concensus mechanisms to behave honestly, and any attacker must out-work this majority to manipulate the ledger.

The proof of quantum work blockchain demonstrated in this example, works similarly to Bitcoin [[1]](#arXiv_2503_14462), but replaces the hard problem of finding rare SHA256 hashes with the problem of finding quantum experiments consistent with rare statistics. The particular quantum experiments can be chosen to be beyond-classical, so that only quantum computers can participate [[2]](#10.1126/science.ado6285).

In this example, a blockchain evolution is simulated by fixing the number of miners, depth of the chain, and computational context (the set of QPUs available to the miners).
Concensus on the state of the chain from the perspective of mining participants is presented.

![Demo Example](static/demo.png "Image of demo interface")


## Installation
You can run this example without installation in cloud-based IDEs that support the
[Development Containers Specification](https://containers.dev/supporting) (aka "devcontainers")
such as GitHub Codespaces.

For development environments that do not support `devcontainers`, install requirements:

```bash
pip install -r requirements.txt
```

If you are cloning the repo to your local system, working in a
[virtual environment](https://docs.python.org/3/library/venv.html) is recommended.

## Usage
Your development environment should be configured to access the
[Leap&trade; quantum cloud service](https://docs.dwavequantum.com/en/latest/ocean/sapi_access_basic.html).
You can see information about supported IDEs and authorizing access to your Leap account
[here](https://docs.dwavequantum.com/en/latest/ocean/leap_authorization.html).

Run the following terminal command to start the Dash application:

```bash
python app.py
```

Access the user interface with your browser at http://127.0.0.1:8050/.

The demo program opens an interface where you can configure problems and submit these problems to
a solver.

Configuration options can be found in the [demo_configs.py](demo_configs.py) file.

> [!NOTE]\
> If you plan on editing any files while the application is running, please run the application
with the `--debug` command-line argument for live reloads and easier debugging:
`python app.py --debug`

Tests can be run by running

```bash
pytest -k "test" 
```
from the quantum-blockchain/tests directory.


# Problem Description

This demo implements a simplified version of a blockchain with adherence of miners to the blockchain rules. Modeling of transactions and passive (non-mining) stakeholders is omitted - this does not impact the evolution of the blockchain. Networking delays are not modeled, and miners use identical (by defaulted distributed) computing resources.

Miners demonstrate completion of quantum work by performing experiments parameterized by the state of the blockchain. Experimental results (sample sets) are post-processed to pairwise correlation statistics. Correlations realized by a particular experiment define a point in a high dimensional space; a miner must find experimental parameters such that this point falls in a small subspace. Miners search by varying nonce parameters, which change the parameters of the unitary evolution and post-processing. Statistics can be digitalized to produce a hash. Any other miner can rerun the experiment to verify a claim of work, up to control and sampling errors. The process of generating a hash is demonstrated below.

![Quantum Hash Generation](static/DW_Quantum_Hashing_Infographic_Final_V3-01.png "Image of quantum hash generation")

Miners present work subject to statistical uncertainty, their work is not guaranteed to be accepted by the community. Concensus mechanisms ensure that such uncertainty is resolved subject to a delay, so that the state of the ledger can be confidently asserted. An example of how probabilistic verification impacts the state of the chain is shown below. 
Consensus mechanisms guarantee that such disagreements are short lived, and there is only ever uncertainty on the status of very recently proposed blocks.

![Blockchain State Uncertainty](static/UTF-8DW_Quantum_Hashing_Infographic_Final_V4.png "Image of blockchain state uncertainty")

This demo implements a quantum blockchain wherein a set of miners perform quantum experiments on a set of QPUs (and embeddings), yet arrive at a consensus on experimental outcomes and the state of the ledger.
After setting parameters in the browser, the blockchain is initiated with a genesis block.
As blocks are mined and proposed they are assessed independently by miners conducting their own quantum experiments.

This example implements methods found in the paper, “Blockchain with Proof of Quantum Work” [[1]](#arXiv_2503_14462), where D-Wave executes the first-ever demonstration of distributed quantum computing deployed blockchain across four cloud-based annealing quantum computers in Canada and the United States. The research highlights how D-Wave built and tested a “proof of quantum” algorithm that uses quantum computation to generate and validate blockchain hashes. The resulting techniques demonstrated that D-Wave’s quantum blockchain architecture could enhance security and significantly reduce electricity costs.


### Comparison with Amin et al. Blockchain with Proof of Quantum Work [[1]](#arXiv_2503_14462)

The simulations in this example execute unitary evolutions on cubic spin glasses matching the paper with simple +/- chain work, subject to changes in the generally available solvers.
The hash length is fixed to 32 and `num_reads` to 600 in order to reduce the QPU access time and accelerate the blockchain evolution (as opposed to the standardized 1 second of QPU access time in the [[1]](#arXiv_2503_14462) experiments).


## Model and Code Overview

### Parameters
The demo defines the following parameters for the underlying proof-of-work protocol

* Number of miners: The number of participating miners.
<!-- TODO: -->
* The length of the chain:
* The set of QPUs used: One can select a single generally available QPU or all available QPUs. 

The simulation can be run, paused, and reset at fixed parameters.

### Initialization

The user selects the number of participating miners, the number of mining events to simulate,
and a set of QPUs (single or multiple). If multiple QPUs are selected, each experiment selects the QPU uniformly from the available QPUs. Each QPU supports a large set of programmings (differing in control error), which are also sampled uniformly at random on every evaluation. Experimental outcomes are subject to control and sampling errors.

### Mining and Validation

For each round of mining, one miner is randomly selected to be the 'winner' of that round,
simulating a distributed community with competitive mining where each miner has an equal chance
of winning. The winning miner completes a quantum experiment, creates a hash, and publishes a block.
Each unsuccessful miner validates the block and adjusts their pattern of mining based on the validation.
As this process iterates a panel is updated to demonstrate verification patterns.
A central graphic showing the state of the chain is updated showing either a single miner view
or the global view. The genesis block is placed at the center, with blocks spiraling outward in the order of proposal.

### Miner Blockchain View

The outer blue path representing the strongest chain, with other proposals marked in orange.
A miner can trust that the initial part of their strongest chain is immutable with high probability [[1]](#arXiv_2503_14462).
Transactions in this portion of the chain can be trusted, with some lower confidence in finality for the final few blocks.

### Global Blockchain View

The user can can select a global view that shows the consistency amongst the various miners.
Blocks that are finalized for all miners are marked blue. Blocks that are rejected by all users are marked orange.
Gray and black blocks have disputed status, with black blocks being actively mined by at least one miner (only black blocks have potential for further branching).
The efficiency is determined by the proportion of blue blocks, which should be large.
The delay is determined by the number of grey and black blocks, which indicate blocks whose validity is currently contested by miners.


### Quantum Unitary Evolution and the Quantum Hash

The unitary evolution that defines "the quantum puzzle", is defined by a set of programmable couplers, J, cryptographically determined by the strongest block (the block defining maximum chain work).
Each coupler is sampled uniformly at random +/- J for each edge matched to a 4x4x4 dimerized cubic lattice, with the desired evolution definded by a 5ns quench on the Advantage2_prototype2 system.
For other annealing QPUs to emulate the Advantage2_protocol2 schedule it is necessary to perform time energy rescaling (i.e. the rescaling of the problem Hamiltonian and annealing time is device specific with values precalculated).
A dimerized cubic lattice is a simple cubic lattice in which each node is replaced by a pair of nodes.
Miners access QPUs uniformly at random from the specified QPUs.
The QPU sampling makes use of the Ocean&trade; SDK composites framework with parallel embedding,
automorphism, and spin-reversal transform (SRT) averaging. The use of automorphism and SRT averaging,
enhances (relative) control errors, simulating variability that may exist across a more diverse ecosystem of QPUs.

After the sampleset is collected, it is post-processed to nearest neighbor correlations. These correlations are then randomly projected by normally distributed random vectors, to give witnesses. The sign on the witnesses specify the bits of the quantum hash. 

<!-- TODO: Add description of simulation (botstrapping) [probably just omit at this stage]? -->

### Per-QPU One-Time Calibration:

The unitary evolution is adjusted by selection of a QPU-specific energy-time rescaling and embedding,
precalculated for a restricted set of available solvers.
The files `generate_enery_time_rescaling.py` and `generate_embedding.py` can be used to generate parameters for a currently unsupported solver. 

## References

<a id="arXiv_2503_14462"></a>
Blockchain with proof of quantum work
Mohammad H. Amin el al., arXiv:2503.14462 (2025)
https://arxiv.org/abs/2503.14462

<a id="10.1126/science.ado6285"></a>
Beyond-classical computation in quantum simulation
Andrew D. King et al., Science (2025)
https://doi.org/10.1126/science.ado6285

## License

Released under the Apache License 2.0. See [LICENSE](LICENSE) file.