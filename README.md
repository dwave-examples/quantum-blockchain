[![Open in GitHub Codespaces](
  https://img.shields.io/badge/Open%20in%20GitHub%20Codespaces-333?logo=github)](
  https://codespaces.new/dwave-examples/quantum-blockchain?quickstart=1)
[![Linux/Mac/Windows build status](
  https://circleci.com/gh/dwave-examples/quantum-blockchain.svg?style=shield)](
  https://circleci.com/gh/dwave-examples/quantum-blockchain)

# Proof of Quantum Work Blockchains

Ledgers are widespread record keeping structures.
A proof of work blockchain is a ledger supported by concensus mechanisms to ensure that no single authority is required to verify the ledger.
Cryptographically-linked hard problems are solved by miners to encode new transactions.
Transactions can considered finalized in the ledger because the community is incentived by concensus mechanisms to behave honestly, and any attacker must out-work this majority to manipulate the ledger.
The proof of quantum work blockchain we demonstrate works similarly to Bitcoin[[1]](#arXiv:2503.14462), but replaces the hard problem of finding rare SHA256 hashes, with the problem of finding quantum experiments with rare distributional properties. The particular quantum experiments can be chosen to be beyond-classical, so that only quantum computers can participate Bitcoin[[2]](#10.1126/science.ado6285)

Fixing the number of miners, depth of the chain and computational context (the set of QPUs available to the miners) a blockchain evolution is simulated.
Concensus on the state of the chain from the perspective of mining participants is presented. Below is an example output of the program:

![Demo Example](static/demo.png)  # TO DO, CHANGE RESTING IMAGE

<a id="plot"></a>
![Example Solution](static/demo.png)  # TO DO, SUITABLE 4-QPU CHAIN


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

> [!NOTE]\
> If you plan on editing any files while the application is running, please run the application
with the `--debug` command-line argument for live reloads and easier debugging:
`python app.py --debug`

Tests can be run by running

```bash
pytest -k "test" 
```
from the quantum-blockchian/tests directory.


# Problem description

This demo implements a simplified version of a blockchain with adherence of miners to the blockchain rules. Modeling of transactions and passive (non-mining) stakeholders is omitted - this does not impact the evolution of the blockchain. Networking delays are not modeled, and miners use identical (by defaulted distributed) computing resources -- with these assumptions in place the mining rate can be accelerated to on the order of seconds for a timely presentation of the evolution with reduced QPU access time on the order of seconds (in proportion to the number of miners), without impacting the structure of the blockchains presented.

Miners demonstrate completion of quantum work by performing experiments parameterized the state of the blockchain. Experimental results (sample sets) are post-processed to pairwise correlation statistics. Correlations realized by a particular experiment define a point in a high dimensional space, a miner must find experimental parameters such that this point falls in a small subspace. This statistics can be digitalized to produce a hash. Any other miner can rerun the experiment to verify a claim of work, up to control and sampling errors.

![Demo Example](static/DW_Quantum_Hashing_Infographic_Final_V3-01.png "Image of quantum hash generation")

Miners present work subject to statistical uncertainty, their work is not guaranteed to be accepted by the community. Concensus mechanisms ensure that such uncertainty is resolved subject to a delay, so that the state of the ledger can be confidently asserted. An example of how probabilistic verification impacts the state of the chain is shown below. 
Consensus mechanisms guarantee that such disagreements are short lived, and there is only ever uncertainty on the status of very recently proposed blocks.

![Demo Example](static/UTF-8DW_Quantum_Hashing_Infographic_Final_V4.png "Image of blockchain state uncertainty")

This demo implements a quantum blockchain wherein a set of miners perform quantum experiments on a set of QPUs (and embeddings), yet arrive at a consensus on experimental outcomes and the state of the ledger. Miners are selected to use a variety of QPUs, and embeddings over those QPUs.
After setting parameters in the browser, the blockchain is initiated with a genesis block.
As blocks are mined and proposed they are assessed independently by miners conducting their own quantum experiments.

In the paper, “Blockchain with Proof of Quantum Work” [[1]](#arXiv:2503.14462) D-Wave executed the first-ever demonstration of distributed quantum computing deployed blockchain across four cloud-based annealing quantum computers in Canada and the United States. The research highlights how D-Wave built and tested a “proof of quantum” algorithm that uses quantum computation to generate and validate blockchain hashes. The resulting techniques demonstrated that D-Wave’s quantum blockchain architecture could enhance security and significantly reduce electricity costs. This demo implements the methods of the paper.


## Architectural comparison with Amin et al. Blockchain with Proof of Quantum Work

For purposes of timely blockchain evolution, and code simplicity, we highlight the following restrictions: 
* The case of unitary dynamics of 4x4x4 cubic-lattice spin glasses is used for the hash.
* Mining is accelerated with impact only on the blockchain rate (not structure) by setting the hardness at 
minimum
* We also allow the option to simulate the blockchain using resampled experimental data. 
* The hash length is fixed to 128 with confidence-based chainwork.

Weaknesses of the particular demonstrated architecture. Cross-validation rates can be increased by use of additional experimental data (confidence-based validation). Mitigations for attacks are explained in the paper. We do not model a transaction ecosystem of transactions on top of the mining process, although this is supported by the block structure.

### Differences from [[1]](#arXiv:2503.14462) and demonstration weaknesses:

We fix the num_reads to 600 (as opposed to the standardized 1 second of QPU access time in [ar] experiments) in order to accelerate blockchain evolution; to keep this from resulting in undesired extra branching, the error tolerance N_max is somewhat increased.

### Parameters
The demo defines the following parameters for the underlying proof-of-work protocol

* Number of miners: The number of participating miners.
* The length of the chain:
* The set of QPUs used: One can select a single generally available QPU, or all available QPUs. 

## Model and Code Overview

The user selects a number of participating miners, a number of mining events to simulate,
and a set of QPUs (single, or multiple). If multiple QPUs are selected, each experiment is randomized,
selecting uniformly from the available QPUs, and supported programmings per QPU. Experimental
outcomes are also subject to control and sampling errors.

### Mining and validation

For each round of mining, we randomly select one miner to be the 'winner' of that round,
simulating a distributed community with competitive mining where each miner has equal chance
to win the next block (given the simplifying assumption that they all have equal computing power
available). The winning miner completes a quantum experiment, creates a hash, and publishes a block.
Each unsuccessful miner validates the block, and adjusts their pattern of mining on validation.
As the routine iterates this process a panel is updated to demonstrate verification patterns.
A central graphic showing the state of the chain is updated according to either a miner view
or global view.

### Miner blockchain view:

The state of the chain from the perspective of different miners is graphed as a spiral with the first genesis block at the center.
The outer blue path representing the strongest chain, with other proposals marked in orange.
Per [arXiv:] a miner can trust that the initial part of their strongest chain is immutable with high probability;
transactions in this portion of the chain can be trusted, with some lower confidence in finality for the final few blocks.

### Global blockchain view:

The user can select a global view that shows the consistency amongst the various miners.
Blocks that are accepted by all users are marked blue. Blocks that are rejected by all users are marked orange.
The efficiency is determined by the proportion of blue blocks, which should be large.
The delay is determined by the number of grey and black blocks, which indicate blocks whose validity is contested by different miners.
Black blocks indicate blocks that are currently being mined (have potential for further branching). 

The code structure is designed with a view to practical generations including:
* parallelized (desynchronized) operation of miner behaviour,
* implementation of weakness mitigation including confidence-based code evaluations and use of a generalized block-structure


### Quantum unitary evolution and the quantum hash:

The unitary evolution that defines "the quantum puzzle" is defined by a set of programmable couplers J.
Each coupler is sampled uniformly at random +/- J for each edge matched to a 4x4x4 cubic lattice.
Miners access QPUs uniformly at random from the selected set. Each access to a QPU involves a randomization of the programming,
so as to model the enhanced level of control errors that may be expected from a larger set.
The QPU sampling makes use of the ocean-sdk composites framework accessed in quantum_cubic_utils.py.
Per mining or validation event the QPU is chosen at random, the realization of control errors is randomized
(using automorphisms, and spin-reversal transforms) so as to enhance (relative) control errors,
simulating variability that might exist across a more diverse ecosystem of QPUs.

### Per-QPU one-time calibration:

The unitary evolution is adjusted by selection of a QPU-specific energy-time rescaling, and embedding.
These are precalculated for a restricted set of current solvers.
To generate parameters for a currently unsupported solver the code examples/generate_qpu_specific_properties.py can be used. 

## References
x
<a id="arXiv:2503.14462"></a>
Blockchain with proof of quantum work
Mohammad H. Amin el al., arXiv:2503.14462 (2025)
https://arxiv.org/abs/2503.14462

<a id="10.1126/science.ado6285"></a>
Beyond-classical computation in quantum simulation
Andrew D. King et al., Science (2025)
https://doi.org/10.1126/science.ado6285

## License

Released under the Apache License 2.0. See [LICENSE](LICENSE) file.