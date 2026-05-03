"""种群管理 - 预分配对象池"""

from cyberterrarium.model.config import E_BIRTH, MAX_POP
from cyberterrarium.model.organism import Organism


class Population:
    """预分配固定大小的对象池，通过alive标志位管理生物生命周期。"""

    def __init__(self, max_capacity: int = MAX_POP) -> None:
        self.max_cap = max_capacity
        self.pool: list[Organism | None] = [None] * max_capacity
        self.free_ids = list(range(max_capacity - 1, -1, -1))

    def spawn(self, genome: bytearray, x: int, y: int, energy: int = E_BIRTH) -> int:
        if not self.free_ids:
            return -1
        org_id = self.free_ids.pop()
        org = Organism(
            org_id=org_id,
            alive=True,
            pc=0,
            regs=[0] * Organism.REG_COUNT,
            equal_flag=False,
            energy=energy,
            age=0,
            genome=genome,
        )
        org.regs[Organism.DP_X] = x
        org.regs[Organism.DP_Y] = y
        self.pool[org_id] = org
        return org_id

    def get_alive_list(self) -> list[Organism]:
        return [org for org in self.pool if org is not None and org.alive]

    @property
    def alive_count(self) -> int:
        return sum(1 for org in self.pool if org is not None and org.alive)

    @property
    def is_full(self) -> bool:
        return len(self.free_ids) == 0
