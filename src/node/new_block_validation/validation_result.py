from dataclasses import dataclass, field
from typing import Iterable

@dataclass
class ValidationResult:
    """This class is used to store attributes from a quantum mining
    validation attempt.
    """
    valid: bool
    vector: Iterable
    stats: Iterable = field(default_factory=list)
    dot_vector: Iterable = field(default_factory=list)
    solver: str = None
    chip_id: str = None
    problem_id: str = None