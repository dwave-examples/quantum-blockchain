import random

from src.common.initialize_default_blockchain import initialize_blockchain
from src.common.owner import Owner
from src.common.block import Block


class TrialOwners:

    def __init__(self, private_key_list = None):
        self.initialize_owners(private_key_list)

    def initialize_owners(self, key_list: list[str]) -> Block:
        """
        Initializes a set of 5 owners with 100 coins each

        Args:
            key_list: a list of owner private keys. This should be passed when you want to re-create Owner objects
            with the same identity on the chain, such as when re-starting a trial from files.
        """

        if not key_list or len(key_list) < 5:
            dan = Owner()
            firas = Owner()
            jack = Owner()
            mohammad = Owner()
            kelsey = Owner()
        else:  #TODO This is a very inelegant patch, but this code will probably change a lot soon, so not worth optimizing now.
            dan = Owner(key_list[0])
            firas = Owner(key_list[1])
            jack = Owner(key_list[2])
            mohammad = Owner(key_list[3])
            kelsey = Owner(key_list[4])


        self.owners = {
            'dan': dan,
            'firas': firas,
            'jack': jack,
            'mohammad': mohammad,
            'kelsey': kelsey,
        }

        self.initial_distributions = {
            dan: 100.0,
            jack: 100.0,
            mohammad: 100.0,
            firas: 100.0,
            kelsey: 100.0,
        }
    
    def select_random_pair(self) -> tuple[Owner, Owner]:
        """Selects a random pair of owners to use in a simulated transaction

        Returns:
            tuple: A tuple of the sender and receiver
        """
        owners = list(self.owners.values())
        receiver = random.choice(owners)
        sender = random.choice([owner for owner in owners if owner != receiver])

        return sender, receiver

    
    def __iter__(self):
        return iter(self.owners.values())


    def __len__(self):
        return len(self.owners)
