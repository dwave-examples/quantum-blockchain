import argparse
import os
import sys
import time
import json

CUR_DIR = os.path.dirname(os.path.realpath(__file__))

sys.path.append(os.path.join(CUR_DIR, '..','..'))

from src.trials.trial_manager import TrialManager
from trial_owners import TrialOwners

from src.quantum.protocols.proof_of_work_protocol_qpu import ProofOfWorkProtocolQpu
from src.common.values import TRIAL_PARAMETERS_FILE

def main(num_miners: int, num_blocks: int, output_directory: str,
        additional_validation: int=0, randomize_solver: bool=False, profile: str='defaults',
        randomize_embedding: bool=False, solver: str='Advantage_system4.1', #TODO future proof case where no solver is specified
        annealing_time: float=0.005, ensemble: str='PMJ',
        scoring_function: str='basic', validate_transactions: bool=False) -> None:
    """This function instantiates the TrialManager object and iterates through num_blocks.
    If output_directory is None, the output will be saved to a new directory in the output
    folder with a timestamped name. Otherwise, the instance saved in output_directory
    will be re-instantiated and the iteration will continue from where it left off.

    Args:
        num_miners (int): The number of miners to use (not needed if output_directory is provided)
        num_blocks (int): The number of blocks to iterate through
        output_directory (str): The output_directory to load from. If not provided, then
            a new directory will be created in the output folder
        additional_validation (int, optional): The additional validation to use (beyond the
            NUMBER_OF_LEADING_ZEROS). Defaults to 0.
        randomize_solver (bool, optional): Whether to randomize the solver. Defaults to False.
        profile (str, optional): The name of the D-Wave profile to use when submitting problems
            to LEAP. Defaults to 'defaults'.
        annealing_time (float): annealing time in microseconds, defauts to 0.005
        ensemble (str): type of distribution. Main options 'PMJ' (default) and 'DimBiClique'
        scoring_function (str): The scoring function to use, one of "basic" or "confidence-based". Defaults to 'basic'.
        validate_transactions (bool): Whether to require transactions be created and stored on each iteration. 
            Defaults to False for faster testing.
    """
    
    if output_directory is None:
        output_directory = os.path.join(CUR_DIR, 'output', timestamp)
        print ("Output will be sent to ", output_directory)
        os.makedirs(output_directory) #TODO make sure this works when "output" exists. If not, do it in two calls.

        trial_owners = TrialOwners()

        
        input_params = {'Miners':num_miners,'Blocks':num_blocks, 'Validation': additional_validation, 
                        'Random_Solver': randomize_solver, 'Profile': profile, 
                        'Random_Embedding':randomize_embedding, 'Solver': solver, 'Annealing_Time':annealing_time,
                        'Ensemble': ensemble, 'Scoring_Function':scoring_function, 
                        'Transactions': validate_transactions, 
                        'Owners': [owner.private_key.export_key().decode('utf8') for owner in trial_owners] }
        with open(os.path.join(output_directory, TRIAL_PARAMETERS_FILE), 'w') as f:
            json.dump(input_params, f)

        pow_protocol = ProofOfWorkProtocolQpu(embedding_directory=os.path.join(CUR_DIR, 'embeddings'),
                                          randomize_solver=randomize_solver, randomize_embedding=randomize_embedding, profile=profile,
                                          solver=solver, annealing_time=annealing_time, ensemble=ensemble)
        pow_protocol.to_json(output_directory)
    else:
        output_directory = os.path.join(CUR_DIR, 'output', output_directory)
        
    manager = TrialManager(output_directory)
    manager.iterate()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-B', '--blocks', type=int, help='Number of blocks')
    parser.add_argument('-V', '--additional_validation', type=int, help='Additional validation')
    parser.add_argument('-M', '--num_miners', type=int, help='Number of miners')
    parser.add_argument('-S', '--randomize_solver', action='store_true', help='Randomize solver', default=False)
    parser.add_argument('-E', '--randomize_embedding', action='store_true', help='Randomize embedding', default=False)
    parser.add_argument('-D', '--directory', type=str, help='Output directory', default=None)
    parser.add_argument('-Z', '--solver', type=str, help="Solver name", default='Advantage_system4.1')
    parser.add_argument('-A', '--annealing_time', type=float, help='Annealing time in microseconds', default=0.005)
    parser.add_argument('-J', '--ensemble', type=str, help='ensemble (J distribution)', default='PMJ')
    parser.add_argument('-F', '--scoring_function', type=str, help='Scoring function to use, one of "basic" or "confidence-based".', default='basic',
                        choices=['basic', 'confidence-based'])
    parser.add_argument('-T', '--validate_transactions', action='store_true', help='Require transactions be created and stored on each iteration', default=False)
    args = parser.parse_args()

    num_miners = args.num_miners
    num_blocks = args.blocks
    additional_validation = args.additional_validation
    randomize_solver = args.randomize_solver
    randomize_embedding = args.randomize_embedding
    annealing_time = args.annealing_time
    ensemble = args.ensemble
    solver = args.solver
    if args.directory is not None:
        output_directory = os.path.join(CUR_DIR, 'output', args.directory)
    else:
        output_directory = None
    
    if num_miners is None and output_directory is None: #Need either a file or a valid set of other required params
        raise ValueError("If not re-starting from a file, the number of miners must be provided as an argument (use -M or --num_miners)")
    if num_blocks is None and output_directory is None:
        raise ValueError("If not restarting from a file, the number of blocks must be provided as an argument (use -B or --blocks)")
    if additional_validation is None and output_directory is None:
        raise ValueError("If not restarting from a file, the additional validation setting must be provided as an argument (use -V or --additional_validation)")
    if output_directory is not None: #Don't throw an error if both are provided, but do warn the user.
        if num_miners or num_blocks or additional_validation:
            print("Warning! Provided input parameters will be ignored in favor of file data!")

    timestamp = time.strftime('%Y%m%d-%H%M%S')

    main(num_miners, num_blocks, additional_validation=additional_validation,
         randomize_solver=randomize_solver, output_directory=output_directory,
         randomize_embedding=randomize_embedding, solver=solver, annealing_time=annealing_time, ensemble=ensemble,
         scoring_function=args.scoring_function, validate_transactions=args.validate_transactions)
