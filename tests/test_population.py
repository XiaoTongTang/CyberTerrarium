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


def test_population_recycle() -> None:
    # 回收死亡生物后，槽位可被重新分配
    pop = Population(max_capacity=2)
    id1 = pop.spawn(bytearray(8), x=0, y=0)
    pop.spawn(bytearray(8), x=1, y=1)
    assert pop.is_full is True
    # 杀死一个生物并回收
    pop.pool[id1].alive = False
    pop.recycle(id1)
    assert pop.alive_count == 1
    assert pop.is_full is False
    # 槽位可复用
    id3 = pop.spawn(bytearray(8), x=2, y=2)
    assert id3 >= 0
    assert pop.alive_count == 2
    assert pop.is_full is True


def test_population_is_full_uses_alive_count() -> None:
    # is_full 基于存活数而非 free_ids：杀死所有生物后，is_full 应为 False
    pop = Population(max_capacity=3)
    id1 = pop.spawn(bytearray(8), x=0, y=0)
    pop.spawn(bytearray(8), x=1, y=1)
    pop.spawn(bytearray(8), x=2, y=2)
    assert pop.is_full is True
    # 杀死但不回收
    pop.pool[id1].alive = False
    assert pop.alive_count == 2
    assert pop.is_full is False
