"""生物实体基础测试"""

from cyberterrarium.model.organism import Organism


def test_organism_creation() -> None:
    org = Organism(
        org_id=0,
        alive=True,
        pc=0,
        regs=[0] * Organism.REG_COUNT,
        equal_flag=False,
        energy=100,
        age=0,
        genome=bytearray(8),
    )
    assert org.alive is True
    assert org.energy == 100
    assert len(org.regs) == 7
