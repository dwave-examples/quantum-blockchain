import random
import math

from src.common.block_score_tree import BlockNode, BlockScoreTree

def dummy_hash(num: int):
    cap_block  = [i for i in range(65,91)]
    digit_block = [i for i in range(48,58)]
    lower_block = [i for i in range(97,123)]
    return chr(cap_block[num%26]) + chr(digit_block[((num+1)//26)%10]) + chr(lower_block[((num+2)//260)%26])

def generate_tree(num_nodes: int, branch_probability: float = 0.1, branch_range: int = 2, branch_end_prob = 0.25, earliest_branch: int = 1):
    
    tree = BlockScoreTree()

    prev_hash = None
    active_branches = [tree.trunk]
    for i in range(num_nodes):
        node_hash = dummy_hash(i)
        active_branch_roll = random.randint(0, len(active_branches)-1)
        active_branch = active_branches[active_branch_roll]
        unbranched = True
        if len(active_branch) > earliest_branch:
            branch_roll = random.randint(1,100)
            if branch_roll < branch_probability*100:
                unbranched = False
        if not unbranched: #Find where to start the new branch
            pred_idx = -len(active_branch)
            while (len(active_branch) + pred_idx < earliest_branch):
                branch_loc_roll = random.randint(1, 2**10 -1)
                pred_idx = -math.ceil(branch_range*(10 - math.log2(branch_loc_roll)))
        else:
            pred_idx = -1

        if len(active_branch) > 0:
            prev_hash = active_branch[pred_idx].hash
        else:
            prev_hash = None

        tree.add_block(block_hash=node_hash, prev_block_hash=prev_hash, block_score=1, canonical=unbranched)

        if not unbranched:
            new_branch = tree.branches[-1]
            active_branches.append(new_branch)

        if active_branch_roll > 0:
            branch_end_roll = random.randint(1,100)
            if branch_end_roll < branch_end_prob*100:
                active_branches.pop(active_branch_roll)

    return tree
        