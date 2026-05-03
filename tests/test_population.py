"""Population tests."""

from cyberterrarium.model.organism import Organism
from cyberterrarium.model.population import Population


def test_population_spawn() -> None:
    pop = Population(max_capacity=10)
    org_id = pop.spawn(bytearray(8), x=5, y=5)
    assert org_id >= 0
    assert pop.alive_count == 1
    org = pop.pool[org_id]
    assert org is not None
    assert org.regs[Organism.DP_X] == 5
    assert org.regs[Organism.DP_Y] == 5


def test_population_full() -> None:
    pop = Population(max_capacity=2)
    pop.spawn(bytearray(8), x=0, y=0)
    pop.spawn(bytearray(8), x=1, y=1)
    assert pop.is_full is True
    result = pop.spawn(bytearray(8), x=2, y=2)
    assert result == -1
