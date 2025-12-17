from src.protocols.hash_calculator import SolverName, initialize_solver
from src.structures.block_score_tree import BlockScoreTree

solver_list = []

for name in SolverName:
    try:
        next_solver = initialize_solver(str(name.value))
        solver_list.append(next_solver)
    except:
        print(f"Failed: {str(name.value)}")

AVAILABLE_SOLVERS = solver_list

test_tree = BlockScoreTree()
main_hashes = ["ab", "bc", "cd", "de", "ef","fg", "gh"]
side_hashes = ["cp", "dq", "fw","wx"]

for i in range(len(main_hashes)-1):
    test_tree.add_block(block_hash=main_hashes[i+1], prev_block_hash=main_hashes[i], block_score=1.0)
test_tree.add_block(block_hash=side_hashes[0], prev_block_hash=main_hashes[1], block_score=-1.0)
test_tree.add_block(block_hash=side_hashes[1], prev_block_hash=main_hashes[2], block_score=-1.0)
test_tree.add_block(block_hash=side_hashes[2], prev_block_hash=main_hashes[4], block_score=-1.0)
test_tree.add_block(block_hash=side_hashes[3], prev_block_hash=side_hashes[2], block_score=1.0)


TEST_TREE = test_tree