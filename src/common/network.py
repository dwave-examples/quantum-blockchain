import logging

import requests

from common.initialize_default_blockchain import initialize_default_blockchain
from common.blockchain_memory import BlockchainMemory
from common.io_known_nodes import KnownNodesMemory
from common.node import Node
from common.values import FIRST_KNOWN_NODE_HOSTNAME

class Network:

    def __init__(self, node: Node, known_nodes_dir: str=None , blockchain_memory_dir: str=BlockchainMemory,
        init_known_nodes_file: bool=False):
        """Initializes the Network class

        Args:
            node (Node): The node object to be used in the network
            init_known_nodes_file (bool, optional): Whether to initialize
                the known nodes file (whcih would reset the known nodes
                file to only include the FIRST_KNOWN_NODE_HOSTNAME). This
                should only be used the first time the network is 
                initialized. Defaults to False.
        """
        self.node = node
        self.blockchain_memory = BlockchainMemory(blockchain_memory_dir)
        self.known_nodes_memory = KnownNodesMemory(known_nodes_dir)
        if init_known_nodes_file:
            self.initialize_known_nodes_file()

    def initialize_known_nodes_file(self) -> None:
        """Initializes the known nodes file with the FIRST_KNOWN_NODE_HOSTNAME
        and the current node's hostname (if the current node's hostname is not
        the same as the FIRST_KNOWN_NODE_HOSTNAME)
        """
        logging.info("Initializing known nodes file")
        initial_known_node = Node(hostname=FIRST_KNOWN_NODE_HOSTNAME)
        if self.node.dict != initial_known_node.dict:
            self.known_nodes_memory.store_known_nodes([self.node.dict, initial_known_node.dict])
        else:
            self.known_nodes_memory.store_known_nodes([self.node.dict])

    def advertise_to_all_known_nodes(self) -> None:
        """Sends a request to all known nodes to advertise that this network's
        node exists.
        """
        logging.info("Advertising to all known nodes")
        for node in self.known_nodes_memory.known_nodes:
            if node.hostname != self.node.hostname:
                try:
                    node.advertise(self.node.hostname)
                except requests.exceptions.ConnectionError:
                    logging.info(f"Node not answering: {node.hostname}")

    def advertise_to_default_node(self) -> bool:
        """Sends a request to the default node to advertise that this network's
        node exists.

        Returns:
            bool: True if the default node answered to the advertising request,
                False otherwise.
        """
        logging.info(f"Advertising to default node: {FIRST_KNOWN_NODE_HOSTNAME}")
        default_node = Node(hostname=FIRST_KNOWN_NODE_HOSTNAME)
        try:
            default_node.advertise(self.node.hostname)
            logging.info("Default node answered to advertising!")
            return True
        except requests.exceptions.ConnectionError:
            logging.info(f"Default node not answering: {FIRST_KNOWN_NODE_HOSTNAME}")
            return False

    def ask_known_nodes_for_their_known_nodes(self) -> list[str]:
        """Asks all known nodes for their known nodes to get a list of all
        known nodes in the network.

        Returns:
            list: A list of all known nodes in the network, identified by their
                hostname
        """
        logging.info("Asking known nodes for their own known nodes")
        known_nodes_of_known_nodes = []
        for currently_known_node in self.known_nodes_memory.known_nodes:
            if currently_known_node.hostname != self.node.hostname:
                try:
                    known_nodes_of_known_node = currently_known_node.known_node_request()
                    for node in known_nodes_of_known_node:
                        if node["hostname"] != self.node.hostname:
                            known_nodes_of_known_nodes.append(Node(node["hostname"]))
                except requests.exceptions.ConnectionError:
                    logging.info(f"Node not answering: {currently_known_node.hostname}")
        return known_nodes_of_known_nodes

    def initialize_blockchain(self) -> None:
        """Initializes the blockchain memory with the longest blockchain in the
        network

        TODO: This method should look for the longest valid blockchain, rather
        than just the longest blockchain.
        """
        longest_blockchain = self.get_longest_blockchain()
        self.blockchain_memory.store_blockchain_dict_in_memory(longest_blockchain)

    def get_longest_blockchain(self) -> list:
        """Gets the longest blockchain in the network by asking all known nodes
        for their blockchains and comparing the lengths of the blockchains.

        Returns:
            list: The longest blockchain in the network
        """
        logging.info("Retrieving the longest blockchain")
        longest_blockchain_size = 0
        longest_blockchain = None
        for node in self.known_nodes_memory.known_nodes:
            if node.hostname != self.node.hostname:
                try:
                    blockchain = node.get_blockchain()
                    blockchain_length = len(blockchain)
                    if blockchain_length > longest_blockchain_size:
                        longest_blockchain_size = blockchain_length
                        longest_blockchain = blockchain
                except requests.exceptions.ConnectionError:
                    logging.info(f"Node not answering: {node.hostname}")
        logging.info(f"Longest blockchain has a size of {longest_blockchain_size} blocks")
        return longest_blockchain

    @property
    def other_nodes_exist(self) -> bool:
        """Checks if there are other nodes in the network

        Returns:
            bool: True if there are other nodes in the network, False otherwise
        """
        if len(self.known_nodes_memory.known_nodes) == 0:
            return False
        elif len(self.known_nodes_memory.known_nodes) == 1 and \
                self.known_nodes_memory.known_nodes[0].hostname == self.node.hostname:
            return False
        else:
            return True

    def join_network(self) -> None:
        """Joins the network by advertising to the default node, asking all known
        nodes for their known nodes, advertising to all known nodes, and initializing
        the blockchain memory.

        If there are no other nodes in the network, the blockchain memory is initialized
        with the default blockchain.
        """
        logging.info("Joining network")
        if self.other_nodes_exist:
            default_node_answered = self.advertise_to_default_node()
            if default_node_answered:
                known_nodes_of_known_node = self.ask_known_nodes_for_their_known_nodes()
                self.known_nodes_memory.store_nodes(known_nodes_of_known_node)
                self.advertise_to_all_known_nodes()
                self.initialize_blockchain()
            else:
                logging.info("Default node didn't answer. This could be caused by a network issue.")
                initialize_default_blockchain(self.blockchain_memory)
        else:
            logging.info("No other node exists. We might be the first node out here.")
            initialize_default_blockchain(self.blockchain_memory)

    def return_known_nodes(self) -> list[dict]:
        """Returns the known nodes of this network
        
        Returns:
            list[dict]: A list of the known nodes of this network
        """
        return self.known_nodes_memory.return_known_nodes()