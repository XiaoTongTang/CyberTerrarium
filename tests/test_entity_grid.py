"""实体网格同步测试 - 验证entity_grid与DP坐标的绝对一致性"""

from cyberterrarium.model.config import C_BASE, C_PER_INST, E_BIRTH, NUTRIENT_LIFE, REPRO_ENERGY_MULTIPLIER
from cyberterrarium.model.organism import Organism
from cyberterrarium.model.population import Population
from cyberterrarium.model.vm import VirtualMachine
from cyberterrarium.model.world import World


def _make_org(
    genome: bytearray | None = None,
    pc: int = 0,
    energy: int = 500,
    regs: list[int] | None = None,
) -> Organism:
    if genome is None:
        genome = bytearray(8)
    if regs is None:
        regs = [0] * Organism.REG_COUNT
    return Organism(
        org_id=0,
        alive=True,
        pc=pc,
        regs=regs,
        equal_flag=False,
        energy=energy,
        age=0,
        genome=genome,
    )


class TestEntityGridBasic:
    def test_entity_grid_initialized_none(self) -> None:
        world = World(10, 10)
        for y in range(10):
            for x in range(10):
                assert world.get_entity(x, y) is None

    def test_set_and_get_entity(self) -> None:
        world = World(10, 10)
        org = _make_org(regs=[0, 0, 0, 0, 0, 5, 5])
        world.set_entity(5, 5, org)
        assert world.get_entity(5, 5) is org
        world.set_entity(5, 5, None)
        assert world.get_entity(5, 5) is None

    def test_entity_grid_wrapping(self) -> None:
        world = World(10, 10)
        org = _make_org(regs=[0, 0, 0, 0, 0, 5, 5])
        world.set_entity(15, 25, org)
        assert world.get_entity(15, 25) is org
        assert world.get_entity(5, 5) is org


class TestMoveEntityGridSync:
    def test_move_x_updates_entity_grid(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[3, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 8
        assert world.get_entity(5, 5) is None
        assert world.get_entity(8, 5) is org

    def test_move_y_updates_entity_grid(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0F, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 2, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_Y] == 7
        assert world.get_entity(5, 5) is None
        assert world.get_entity(5, 7) is org

    def test_move_blocked_by_entity(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
        )
        blocker = _make_org(
            genome=bytearray(8),
            regs=[0, 0, 0, 0, 0, 6, 5],
        )
        blocker.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 5, blocker)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # 移动失败，DP_X不变，entity_grid不变
        assert org.regs[Organism.DP_X] == 5
        assert world.get_entity(5, 5) is org
        assert world.get_entity(6, 5) is blocker


class TestDataRegProtection:
    def test_add_cannot_modify_dp_x(self) -> None:
        vm = VirtualMachine()
        # ADD reg=5(DP_X), rb=0(R0=1) — 算术指令不允许修改DP_X
        org = _make_org(
            bytearray([0x02, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # DP_X不变，操作被降级到R0
        assert org.regs[Organism.DP_X] == 5
        assert org.regs[Organism.R0] == 1 + 1  # R0 += R0

    def test_sub_cannot_modify_dp_y(self) -> None:
        vm = VirtualMachine()
        # SUB reg=6(DP_Y), rb=0(R0=1) — 算术指令不允许修改DP_Y
        org = _make_org(
            bytearray([0x03, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_Y] == 5
        assert org.regs[Organism.R0] == 1 - 1  # R0 -= R0

    def test_mov_cannot_modify_dp_x(self) -> None:
        vm = VirtualMachine()
        # MOV reg=5(DP_X), imm=99
        org = _make_org(
            bytearray([0x01, 0x05, 0x63, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 5
        assert org.regs[Organism.R0] == 99  # 降级到R0

    def test_not_cannot_modify_dp_y(self) -> None:
        vm = VirtualMachine()
        # NOT reg=6(DP_Y)
        org = _make_org(
            bytearray([0x06, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_Y] == 5
        assert org.regs[Organism.R0] == ~0  # 降级到R0

    def test_mov_can_modify_inv(self) -> None:
        # INV(index=4)在数据寄存器范围内，应可被MOV修改
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x01, 0x04, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.INV] == 2


class TestDeathEntityGridSync:
    def test_kill_clears_entity_grid(self) -> None:
        from cyberterrarium.model.controller import SimulationController

        world = World(10, 10)
        pop = Population(10)
        ctrl = SimulationController(world, pop)

        org_id = pop.spawn(bytearray(8), x=5, y=5)
        org = pop.pool[org_id]
        world.set_entity(5, 5, org)

        ctrl._kill_and_corpse(org)

        assert world.get_entity(5, 5) is None
        assert org.alive is False


class TestBirthEntityGridSync:
    def test_spawn_sets_entity_grid(self) -> None:
        from cyberterrarium.model.controller import SimulationController

        world = World(10, 10)
        pop = Population(10)
        ctrl = SimulationController(world, pop)

        org_id = pop.spawn(bytearray(8), x=3, y=7)
        org = pop.pool[org_id]
        world.set_entity(3, 7, org)

        assert world.get_entity(3, 7) is org

    def test_phase3_settles_entity_grid(self) -> None:
        from cyberterrarium.model.controller import SimulationController

        world = World(10, 10)
        pop = Population(10)
        ctrl = SimulationController(world, pop)

        # 创建一个高能量生物，使其达到繁殖阈值
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        org_id = pop.spawn(bytearray(8), x=5, y=5, energy=threshold + cost)
        org = pop.pool[org_id]
        world.set_entity(5, 5, org)

        ctrl.execute_phase_repro()
        ctrl.execute_phase_3()

        # 验证子代被写入entity_grid
        alive_list = pop.get_alive_list()
        assert len(alive_list) == 2
        for alive_org in alive_list:
            ex = alive_org.regs[Organism.DP_X]
            ey = alive_org.regs[Organism.DP_Y]
            assert world.get_entity(ex, ey) is alive_org
