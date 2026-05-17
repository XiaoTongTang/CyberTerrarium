"""虚拟机指令执行引擎测试"""

from cyberterrarium.model.config import (
    C_MAKE_ENZ,
    C_MAKE_SIG,
    C_MAKE_TOX,
    C_TOUCH_TOX,
    E_ENZ_EAT,
    E_NUT,
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
    equal_flag: bool = False,
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
        equal_flag=equal_flag,
        energy=energy,
        age=0,
        genome=genome,
    )


def _make_world(w: int = 10, h: int = 10) -> World:
    return World(w, h)


class TestNOP:
    def test_nop(self) -> None:
        # 场景：执行NOP指令，验证无任何副作用，PC正常推进，能量不变
        vm = VirtualMachine()
        org = _make_org(bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
        world = _make_world()
        pop = Population(10)
        result = vm.execute_instruction(org, world, pop)
        assert result == []
        assert org.pc == 4
        assert org.energy == 500


class TestMOV:
    def test_mov_imm(self) -> None:
        # 场景：MOV R0, 10 — 将立即数10写入R0，验证R0被正确赋值
        vm = VirtualMachine()
        org = _make_org(bytearray([0x01, 0x00, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00]))
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 10

    def test_mov_to_r3(self) -> None:
        # 场景：MOV R3, 255 — 写入非R0寄存器与最大立即数值，验证R3正确接收
        vm = VirtualMachine()
        org = _make_org(bytearray([0x01, 0x03, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00]))
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R3] == 255


class TestADD:
    def test_add(self) -> None:
        # 场景：ADD R0, R1 — R0=10, R1=20，验证R0 = 10+20 = 30
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x02, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[10, 20, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 30


class TestSUB:
    def test_sub(self) -> None:
        # 场景：SUB R0, R1 — R0=50, R1=20，验证R0 = 50-20 = 30
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x03, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[50, 20, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 30


class TestAND:
    def test_and(self) -> None:
        # 场景：AND R0, R1 — R0=0xFF, R1=0x0F，验证按位与结果R0 = 0x0F
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x04, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0xFF, 0x0F, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 0x0F


class TestOR:
    def test_or(self) -> None:
        # 场景：OR R0, R1 — R0=0xF0, R1=0x0F，验证按位或结果R0 = 0xFF
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x05, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0xF0, 0x0F, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 0xFF


class TestNOT:
    def test_not(self) -> None:
        # 场景：NOT R0 — R0=0，验证按位取反后R0 = ~0（全1）
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == ~0

    def test_not_nonzero(self) -> None:
        # 场景：NOT R1 — R1=0x0F，验证非零值取反后R1 = ~0x0F
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x06, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0x0F, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R1] == ~0x0F


class TestSafeReg:
    def test_out_of_bounds_reg_maps_to_r0(self) -> None:
        # 场景：MOV R99, 5 — 寄存器索引99超出REG_COUNT(7)范围，
        # 验证safe_reg将其降级为R0，值写入R0
        vm = VirtualMachine()
        org = _make_org(bytearray([0x01, 0x63, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00]))
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 5

    def test_negative_reg_maps_to_r0(self) -> None:
        # 场景：MOV R0xFF, 5 — 字节值0xFF=255作为寄存器索引，
        # 超出REG_COUNT(7)，验证safe_reg降级为R0
        vm = VirtualMachine()
        org = _make_org(bytearray([0x01, 0xFF, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00]))
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == 5


class TestReadRel:
    def test_read_rel_nutrient(self) -> None:
        # 场景：READ_REL 1, 0 — 生物位于(5,5)，读取(6,5)处的营养，
        # 验证R0被赋值为NUTRIENT
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x09, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = _make_world()
        world.set_material(6, 5, World.NUTRIENT)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == World.NUTRIENT

    def test_read_rel_wrapping(self) -> None:
        # 场景：READ_REL 0xFF, 0 — 生物位于(0,5)，偏移0xFF=255，
        # 坐标取模(0+255)%10=5，读取(5,5)处的空格，验证R0=EMPTY
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x09, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 0, 5],
        )
        world = _make_world(10, 10)
        world.set_material(9, 5, World.TOXIN)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == World.EMPTY


class TestReadAbs:
    def test_read_abs(self) -> None:
        # 场景：READ_ABS R0, R1 — R0=3, R1=7，读取(3,7)处的酶，
        # 验证R0被赋值为ENZYME
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0A, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[3, 7, 0, 0, 0, 0, 0],
        )
        world = _make_world(10, 10)
        world.set_material(3, 7, World.ENZYME)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == World.ENZYME

    def test_read_abs_wrapping(self) -> None:
        # 场景：READ_ABS R0, R1 — R0=15, R1=12，坐标超界，
        # 取模后(15%10=5, 12%10=2)，读取(5,2)处的信号，验证R0=SIGNAL
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0A, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[15, 12, 0, 0, 0, 0, 0],
        )
        world = _make_world(10, 10)
        world.set_material(5, 2, World.SIGNAL)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.R0] == World.SIGNAL


class TestEat:
    def test_eat_nutrient_no_enzyme(self) -> None:
        # 场景：EAT — 脚下(5,5)为营养，INV为空（无酶），
        # 验证获得基础能量E_NUT，脚下变空，INV清零
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0B, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            energy=100,
        )
        world = _make_world()
        world.set_material(5, 5, World.NUTRIENT)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.energy == 100 + E_NUT
        assert world.get_material(5, 5) == World.EMPTY
        assert org.regs[Organism.INV] == 0

    def test_eat_nutrient_with_enzyme(self) -> None:
        # 场景：EAT — 脚下(5,5)为营养，INV=ENZYME（有酶），
        # 验证获得4倍能量E_ENZ_EAT，脚下变空，INV清零
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0B, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, World.ENZYME, 5, 5],
            energy=100,
        )
        world = _make_world()
        world.set_material(5, 5, World.NUTRIENT)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.energy == 100 + E_ENZ_EAT
        assert world.get_material(5, 5) == World.EMPTY
        assert org.regs[Organism.INV] == 0

    def test_eat_empty_cell(self) -> None:
        # 场景：EAT — 脚下(5,5)为空格，验证无能量增加，不产生副作用
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0B, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            energy=100,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.energy == 100


class TestMake:
    def test_make_enzyme(self) -> None:
        # 场景：MAKE ENZYME(mat_id=2) — 合成酶，验证INV=ENZYME，扣除C_MAKE_ENZ
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0C, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            energy=100,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.INV] == World.ENZYME
        assert org.energy == 100 - C_MAKE_ENZ

    def test_make_toxin(self) -> None:
        # 场景：MAKE TOXIN(mat_id=3) — 合成毒素，验证INV=TOXIN，扣除C_MAKE_TOX
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0C, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            energy=100,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.INV] == World.TOXIN
        assert org.energy == 100 - C_MAKE_TOX

    def test_make_signal(self) -> None:
        # 场景：MAKE SIGNAL(mat_id=4) — 合成信号，验证INV=SIGNAL，扣除C_MAKE_SIG
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0C, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            energy=100,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.INV] == World.SIGNAL
        assert org.energy == 100 - C_MAKE_SIG

    def test_make_invalid_penalty(self) -> None:
        # 场景：MAKE 9(mat_id=9) — 合成非法物质，验证代谢失误惩罚：
        # 扣除C_MAKE_ENZ作为罚金，INV保持不变（仍为EMPTY）
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0C, 0x09, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            energy=100,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.energy == 100 - C_MAKE_ENZ
        assert org.regs[Organism.INV] == 0


class TestEmit:
    def test_emit_signal_sets_life(self) -> None:
        # 场景：EMIT 1, 0 — 生物在(5,5)，INV=SIGNAL，向(6,5)排放信号，
        # 验证(6,5)变为SIGNAL，signal_life设为50，INV清空
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0D, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, World.SIGNAL, 5, 5],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert world.get_material(6, 5) == World.SIGNAL
        assert world.signal_life[5, 6] == 50
        assert org.regs[Organism.INV] == World.EMPTY

    def test_emit_toxin(self) -> None:
        # 场景：EMIT 0, 0 — 生物在(5,5)，INV=TOXIN，向自身脚下排放毒素，
        # 验证(5,5)变为TOXIN，INV清空
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, World.TOXIN, 5, 5],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert world.get_material(5, 5) == World.TOXIN
        assert org.regs[Organism.INV] == World.EMPTY

    def test_emit_out_of_range_rejected(self) -> None:
        # 场景：EMIT 2, 0 — 曼哈顿距离|2|+|0|=2>1，超出3x3写权限，
        # 验证写操作被拒绝，INV保持不变
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0D, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, World.TOXIN, 5, 5],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.INV] == World.TOXIN

    def test_emit_empty_inv_rejected(self) -> None:
        # 场景：EMIT 0, 0 — INV=EMPTY（背包为空），验证排放被拒绝，
        # 目标格子保持为空
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, World.EMPTY, 5, 5],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert world.get_material(5, 5) == World.EMPTY


class TestMoveX:
    def test_move_x_positive(self) -> None:
        # 场景：MOVE_X R0 — DP_X=5, R0=3，验证DP_X = (5+3)%10 = 8
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[3, 0, 0, 0, 0, 5, 5],
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_X] == 8

    def test_move_x_wrapping(self) -> None:
        # 场景：MOVE_X R0 — DP_X=8, R0=5，验证DP_X = (8+5)%10 = 3（边界环绕）
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[5, 0, 0, 0, 0, 8, 5],
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_X] == (8 + 5) % 10

    def test_move_x_into_toxin(self) -> None:
        # 场景：MOVE_X R0 — 目标格(6,5)为毒素，验证：扣C_TOUCH_TOX能量，
        # 毒素被清除变空，生物仍移动到该位置
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
        )
        world = _make_world(10, 10)
        world.set_material(6, 5, World.TOXIN)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_X] == 6
        move_cost = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 200 - C_TOUCH_TOX - move_cost
        assert world.get_material(6, 5) == World.EMPTY


class TestMoveY:
    def test_move_y_positive(self) -> None:
        # 场景：MOVE_Y R1 — DP_Y=5, R1=2，验证DP_Y = (5+2)%10 = 7
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0F, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 2, 0, 0, 0, 5, 5],
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_Y] == 7

    def test_move_y_into_toxin(self) -> None:
        # 场景：MOVE_Y R1 — 目标格(5,6)为毒素，验证：扣C_TOUCH_TOX能量，
        # 毒素被清除变空，生物仍移动到该位置
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0F, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 1, 0, 0, 0, 5, 5],
            energy=200,
        )
        world = _make_world(10, 10)
        world.set_material(5, 6, World.TOXIN)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_Y] == 6
        move_cost = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 200 - C_TOUCH_TOX - move_cost
        assert world.get_material(5, 6) == World.EMPTY


class TestMoveCost:
    def test_move_cost_formula_d1(self) -> None:
        # d=1: cost = MOVE_BASE + MOVE_RATE*1 + MOVE_SPRINT*1*0/2
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=100,
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        expected = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 100 - expected

    def test_move_cost_formula_d3(self) -> None:
        # d=3: cost = MOVE_BASE + MOVE_RATE*3 + MOVE_SPRINT*3*2/2
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[3, 0, 0, 0, 0, 5, 5],
            energy=200,
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        d = 3
        expected = MOVE_BASE + MOVE_RATE * d + MOVE_SPRINT * d * (d - 1) // 2
        assert org.energy == 200 - expected

    def test_move_zero_cost_free(self) -> None:
        # d=0: 原地不动免费
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            energy=100,
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.energy == 100

    def test_insufficient_energy_blocks_move(self) -> None:
        # 能量不足 → 移动失败
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[3, 0, 0, 0, 0, 5, 5],
            energy=1,  # 远不够
        )
        world = _make_world(10, 10)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_X] == 5  # 未移动
        assert org.energy == 1  # 未扣费

    def test_collision_no_cost(self) -> None:
        # 碰撞失败时移动成本也不扣
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=100,
        )
        blocker = _make_org(regs=[0, 0, 0, 0, 0, 6, 5])
        blocker.org_id = 1
        world = _make_world(10, 10)
        world.set_entity(6, 5, blocker)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.regs[Organism.DP_X] == 5
        assert org.energy == 100  # 碰撞不扣费


class TestCMP:
    def test_cmp_equal(self) -> None:
        # 场景：CMP R0, R1 — R0=42, R1=42，两值相等，验证equal_flag=True
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x10, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[42, 42, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.equal_flag is True

    def test_cmp_not_equal(self) -> None:
        # 场景：CMP R0, R1 — R0=1, R1=2，两值不等，验证equal_flag=False
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x10, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 2, 0, 0, 0, 0, 0],
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.equal_flag is False


class TestJZ:
    def test_jz_taken(self) -> None:
        # 场景：JZ -1（offset=0xFF）在pc=8处执行，equal_flag=True，
        # 验证跳转命中：PC = 8 + (-1)*4 = 4
        vm = VirtualMachine()
        genome = bytearray([
            0x00, 0x00, 0x00, 0x00,  # pc=0: NOP
            0x00, 0x00, 0x00, 0x00,  # pc=4: NOP
            0x11, 0xFF, 0x00, 0x00,  # pc=8: JZ -1
            0x00, 0x00, 0x00, 0x00,  # pc=12: NOP
        ])
        org = _make_org(genome, pc=8, equal_flag=True)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4

    def test_jz_not_taken(self) -> None:
        # 场景：JZ -1（offset=0xFF）在pc=0处执行，equal_flag=False，
        # 验证跳转未命中：PC = (0+4)%8 = 4（正常推进）
        vm = VirtualMachine()
        genome = bytearray([0x11, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=0, equal_flag=False)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4


class TestJNZ:
    def test_jnz_taken(self) -> None:
        # 场景：JNZ -1（offset=0xFF）在pc=4处执行，equal_flag=False，
        # 验证跳转命中：PC = 4 + (-1)*4 = 0（回跳到首条指令）
        vm = VirtualMachine()
        genome = bytearray([
            0x00, 0x00, 0x00, 0x00,  # pc=0: NOP
            0x12, 0xFF, 0x00, 0x00,  # pc=4: JNZ -1
            0x00, 0x00, 0x00, 0x00,  # pc=8: NOP
            0x00, 0x00, 0x00, 0x00,  # pc=12: NOP
        ])
        org = _make_org(genome, pc=4, equal_flag=False)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 0

    def test_jnz_not_taken(self) -> None:
        # 场景：JNZ -3（offset=0xFD）在pc=0处执行，equal_flag=True，
        # 验证跳转未命中：PC = (0+4)%8 = 4（正常推进）
        vm = VirtualMachine()
        genome = bytearray([0x12, 0xFD, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=0, equal_flag=True)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4


class TestJMP:
    def test_jmp_forward(self) -> None:
        # 场景：JMP +1（offset=1）在pc=0处执行，验证无条件前跳：PC = 0+1*4 = 4
        vm = VirtualMachine()
        genome = bytearray([0x13, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=0)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4

    def test_jmp_backward(self) -> None:
        # 场景：JMP -2（offset=0xFE=254 signed=-2）在pc=8处执行，
        # 验证无条件后跳：PC = 8+(-2)*4 = 0
        vm = VirtualMachine()
        genome = bytearray([
            0x00, 0x00, 0x00, 0x00,  # pc=0: NOP
            0x00, 0x00, 0x00, 0x00,  # pc=4: NOP
            0x13, 0xFE, 0x00, 0x00,  # pc=8: JMP -2
            0x00, 0x00, 0x00, 0x00,  # pc=12: NOP
        ])
        org = _make_org(genome, pc=8)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 0


class TestPCAdvance:
    def test_normal_pc_advance(self) -> None:
        # 场景：执行NOP后，验证PC默认从0推进到4
        vm = VirtualMachine()
        genome = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=0)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4

    def test_pc_wraps_at_end(self) -> None:
        # 场景：PC在末条指令(pc=4)执行后，验证环绕回到基因组起点PC=0
        vm = VirtualMachine()
        genome = bytearray([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=4)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 0

    def test_jump_opcode_no_double_advance(self) -> None:
        # 场景：JMP +1内部已设置PC=4，验证execute_instruction不会
        # 对跳转指令再次推进PC（不会变成8）
        vm = VirtualMachine()
        genome = bytearray([0x13, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=0)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4


class TestSplit:
    def test_split_is_now_nop(self) -> None:
        # 场景：SPLIT(0x14)已废弃，执行效果等同NOP，不再产生spawn request
        vm = VirtualMachine()
        genome = bytearray([0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(
            genome,
            energy=1000,
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = _make_world(10, 10)
        pop = Population(10)
        result = vm.execute_instruction(org, world, pop)
        assert result == []
        assert org.energy == 1000  # 不扣繁殖成本

    def test_split_pc_still_advances(self) -> None:
        # 场景：SPLIT废弃后PC仍正常推进
        vm = VirtualMachine()
        genome = bytearray([0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        org = _make_org(genome, pc=0, energy=1000)
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)
        assert org.pc == 4


class TestTruncatedBytecode:
    def test_truncated_genome_resets_pc(self) -> None:
        # 场景：基因组仅3字节，不足4字节构成一条完整指令，
        # 验证PC被重置为0，返回空繁衍列表
        vm = VirtualMachine()
        org = _make_org(bytearray([0x01, 0x00, 0x05]), pc=0)
        world = _make_world()
        pop = Population(10)
        result = vm.execute_instruction(org, world, pop)
        assert result == []
        assert org.pc == 0


class TestUnknownOpcode:
    def test_unknown_opcode_treated_as_nop(self) -> None:
        # 场景：遇到未定义的opcode 0xFF，验证按容错降级规则当作NOP处理：
        # PC正常推进，无任何副作用，能量不变
        vm = VirtualMachine()
        org = _make_org(bytearray([0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]))
        world = _make_world()
        pop = Population(10)
        result = vm.execute_instruction(org, world, pop)
        assert result == []
        assert org.pc == 4
        assert org.energy == 500
