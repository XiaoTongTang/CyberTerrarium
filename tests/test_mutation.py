"""突变引擎基础测试"""

from cyberterrarium.model import mutation
from cyberterrarium.model.mutation import apply_mutations


def test_no_mutation_when_disabled() -> None:
    original = mutation.MUTATION_ENABLED
    mutation.MUTATION_ENABLED = False
    try:
        genome = bytearray([0x00, 0x00, 0x00, 0x00] * 4)
        result = apply_mutations(genome)
        assert result == genome
    finally:
        mutation.MUTATION_ENABLED = original
