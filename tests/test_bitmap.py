"""位图映射协议指令测试"""

from cyberterrarium.model.bitmap import BMAP_MASK
from cyberterrarium.model.config import (
    C_ATTACK_BASE,
    C_ATTACK_PER_BIT,
    C_DAMAGE_PER_HIT,
    C_EMIT_ENZ,
    C_EMIT_TOX,
    C_LEECH_PER_HIT,
    C_TOUCH_TOX,
    MOVE_BASE,
    MOVE_RATE,
    MOVE_SPRINT,
)
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


# ── MOVE_BMAP (0x15) ──


class TestMoveBmap:
    def test_single_bit_right_down(self) -> None:
        # Bit0 → (+2, +2)：向右2格、向下2格
        vm = VirtualMachine()
        bmap = 1 << 0  # Bit0 = (+2,+2)
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert world.get_entity(5, 5) is None
        assert world.get_entity(7, 7) is org
        assert org.regs[Organism.DP_X] == 7
        assert org.regs[Organism.DP_Y] == 7

    def test_vector_sum_clamp(self) -> None:
        # 多个bit累加后clamp到[-2, +2]
        # Bit0(+2,+2) + Bit24(-2,-2) + Bit7(0,+1) = Sum(0, +1) → Move(0, 1)
        vm = VirtualMachine()
        bmap = (1 << 0) | (1 << 24) | (1 << 7)
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 5
        assert org.regs[Organism.DP_Y] == 6

    def test_zero_displacement_no_move(self) -> None:
        # 中心bit (Bit12 → (0,0)) 产生零位移
        vm = VirtualMachine()
        bmap = 1 << 12  # (0, 0)
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 5
        assert org.regs[Organism.DP_Y] == 5

    def test_collision_blocks_move(self) -> None:
        # 目标位置有生物 → 移动失败
        vm = VirtualMachine()
        bmap = 1 << 0  # (+2, +2)
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
        )
        blocker = _make_org(regs=[0, 0, 0, 0, 0, 7, 7])
        blocker.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(7, 7, blocker)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 5
        assert org.regs[Organism.DP_Y] == 5
        assert world.get_entity(7, 7) is blocker

    def test_toxin_detected_on_move(self) -> None:
        vm = VirtualMachine()
        bmap = 1 << 6  # (+1, +1)
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_material(6, 6, World.TOXIN)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 6
        assert org.regs[Organism.DP_Y] == 6
        # d=2: cost = MOVE_BASE + MOVE_RATE*2 + MOVE_SPRINT*2*1/2
        move_cost = MOVE_BASE + MOVE_RATE * 2 + MOVE_SPRINT * 2 * 1 // 2
        assert org.energy == 500 - C_TOUCH_TOX - move_cost
        assert world.get_material(6, 6) == World.EMPTY

    def test_empty_bmap_no_move(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.DP_X] == 5
        assert org.regs[Organism.DP_Y] == 5


# ── ATTACK_BMAP (0x16) ──


class TestAttackBmap:
    def test_hit_damages_and_leeches(self) -> None:
        vm = VirtualMachine()
        # Bit12 = (0, 0) — 攻击自身位置(但自身在entity_grid上)
        # 用 Bit6 = (+1, +1) 攻击右下邻居
        bmap = 1 << 6  # (+1, +1)
        org = _make_org(
            bytearray([0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        target = _make_org(regs=[0, 0, 0, 0, 0, 6, 6], energy=200)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        popcount = 1
        expected_cost = C_ATTACK_BASE + popcount * C_ATTACK_PER_BIT
        assert org.energy == 500 - expected_cost + C_LEECH_PER_HIT
        assert target.energy == 200 - C_DAMAGE_PER_HIT

    def test_insufficient_energy_fails(self) -> None:
        vm = VirtualMachine()
        bmap = 0x01FFFFFF  # 全25位 = popcount 25
        org = _make_org(
            bytearray([0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=5,  # 远不够
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.energy == 5  # 未扣费

    def test_empty_cell_no_effect(self) -> None:
        vm = VirtualMachine()
        bmap = 1 << 0  # (+2, +2) — 空格子
        org = _make_org(
            bytearray([0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        popcount = 1
        expected_cost = C_ATTACK_BASE + popcount * C_ATTACK_PER_BIT
        assert org.energy == 500 - expected_cost  # 只扣攻击成本，无吸血

    def test_high_bits_masked(self) -> None:
        # 高7位应被掩码为0（0xFE000000 与 BMAP_MASK 无重叠）
        vm = VirtualMachine()
        bmap = 0xFE000000  # Bit25~31，低25位全0
        org = _make_org(
            bytearray([0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # popcount = 0, cost = C_ATTACK_BASE
        assert org.energy == 500 - C_ATTACK_BASE


# ── SCAN_NUT / SCAN_TOX / SCAN_EMP (0x17/0x18/0x19) ──


class TestScanNut:
    def test_detects_nutrient(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        # 在 (+1, +1) 位置放营养 → Bit6
        world.set_material(6, 6, World.NUTRIENT)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == (1 << 6)

    def test_empty_area_returns_zero(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x17, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == 0

    def test_arith_target_protects_inv(self) -> None:
        vm = VirtualMachine()
        # p1=4 → INV, 应被 _data_reg 降级为 R0
        org = _make_org(
            bytearray([0x17, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_material(6, 6, World.NUTRIENT)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.INV] == 0  # INV 未被修改
        assert org.regs[Organism.R0] != 0  # 结果写入 R0


class TestScanTox:
    def test_detects_toxin(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x18, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_material(4, 4, World.TOXIN)  # (-1, -1) → Bit18
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == (1 << 18)


class TestScanEmp:
    def test_detects_empty(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x19, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        # 全空世界，25格都应匹配
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == BMAP_MASK  # 低25位全1

    def test_non_empty_excluded(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x19, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_material(6, 6, World.NUTRIENT)  # (+1, +1) → Bit6 非空
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] & (1 << 6) == 0  # Bit6 不应为1
        assert org.regs[Organism.R0] != 0  # 其他空格仍为1


# ── EMIT_BMAP (0x1A) ──


class TestEmitBmap:
    def test_emit_toxin_to_cells(self) -> None:
        vm = VirtualMachine()
        bmap = (1 << 6) | (1 << 8)  # (+1,+1) 和 (-1,+1)
        org = _make_org(
            bytearray([0x1A, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 6) == World.TOXIN
        assert world.get_material(4, 6) == World.TOXIN
        expected_cost = 2 * C_EMIT_TOX
        assert org.energy == 500 - expected_cost

    def test_emit_signal_sets_life(self) -> None:
        vm = VirtualMachine()
        bmap = 1 << 6  # (+1, +1)
        org = _make_org(
            bytearray([0x1A, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 6) == World.SIGNAL
        assert world.signal_life[6, 6] == 50

    def test_insufficient_energy_fails(self) -> None:
        vm = VirtualMachine()
        bmap = 0x01FFFFFF  # 全25位
        org = _make_org(
            bytearray([0x1A, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=5,  # 不够
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.energy == 5  # 未扣费

    def test_invalid_material_rejected(self) -> None:
        vm = VirtualMachine()
        bmap = 1 << 6
        org = _make_org(
            bytearray([0x1A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # p2=0 → EMPTY, 无效材料ID
        assert world.get_material(6, 6) == World.EMPTY
        assert org.energy == 500  # 未扣费

    def test_emit_enzyme_cost(self) -> None:
        vm = VirtualMachine()
        bmap = (1 << 6) | (1 << 8)  # 2格
        org = _make_org(
            bytearray([0x1A, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 6) == World.ENZYME
        assert world.get_material(4, 6) == World.ENZYME
        assert org.energy == 500 - int(2 * C_EMIT_ENZ)
