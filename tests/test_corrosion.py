"""腐蚀反应测试 - 毒素衰减、排放签名、免疫判定、腐蚀转化

坐标系约定：set_material(X, Y) → grid[Y, X] → toxin_life[Y, X]
"""

from cyberterrarium.model.config import (
    C_TOUCH_TOX,
    MOVE_BASE,
    MOVE_RATE,
    NUTRIENT_LIFE,
    TOX_LIFETIME,
)
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.organism import Organism
from cyberterrarium.model.population import Population
from cyberterrarium.model.vm import VirtualMachine
from cyberterrarium.model.world import World


def _make_org(
    genome: bytearray | None = None,
    pc: int = 0,
    energy: int = 500,
    regs: list[int] | None = None,
    gene_signature: int = 0,
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
        gene_signature=gene_signature,
    )


def _make_world(w: int = 10, h: int = 10) -> World:
    return World(w, h)


def _make_controller(w: int = 10, h: int = 10) -> SimulationController:
    world = World(w, h)
    pop = Population(max_capacity=100)
    return SimulationController(world, pop)


def _place_toxin(world: World, x: int, y: int, sig: int = 0) -> None:
    """在指定坐标放置毒素并设置生命和签名。"""
    world.set_material(x, y, World.TOXIN)
    world.toxin_life[y, x] = TOX_LIFETIME
    world.toxin_signature[y, x] = sig


# ── 毒素衰减 (Phase 1) ──


class TestToxinDecay:
    def test_toxin_decays(self) -> None:
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.TOXIN
        ctrl.world.toxin_life[2, 2] = 5

        ctrl.execute_phase_1()

        assert ctrl.world.toxin_life[2, 2] == 4
        assert grid[2, 2] == World.TOXIN

    def test_toxin_expires(self) -> None:
        ctrl = _make_controller(5, 5)
        ctrl.current_tick = 50  # 避免触发营养生成周期
        grid = ctrl.world.grid
        grid[2, 2] = World.TOXIN
        ctrl.world.toxin_life[2, 2] = 1

        ctrl.execute_phase_1()

        assert ctrl.world.toxin_life[2, 2] == 0
        assert grid[2, 2] == World.EMPTY

    def test_toxin_life_zero_not_decremented(self) -> None:
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.EMPTY
        ctrl.world.toxin_life[2, 2] = 0

        ctrl.execute_phase_1()

        assert ctrl.world.toxin_life[2, 2] == 0

    def test_multiple_toxins_decay(self) -> None:
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[1, 1] = World.TOXIN
        ctrl.world.toxin_life[1, 1] = 2
        grid[3, 3] = World.TOXIN
        ctrl.world.toxin_life[3, 3] = 1

        ctrl.execute_phase_1()

        assert ctrl.world.toxin_life[1, 1] == 1
        assert grid[1, 1] == World.TOXIN
        assert ctrl.world.toxin_life[3, 3] == 0
        assert grid[3, 3] == World.EMPTY


# ── 毒素排放签名 ──


class TestEmitToxinSignature:
    def test_emit_toxin_sets_signature(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0D, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, World.TOXIN, 5, 5],
            gene_signature=42,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        # EMIT 在当前 DP 位置 (5,5) 排放
        assert world.toxin_life[5, 5] == TOX_LIFETIME
        assert world.toxin_signature[5, 5] == 42

    def test_emit_bmap_toxin_sets_signature(self) -> None:
        vm = VirtualMachine()
        # Bit24 = (-2, -2) → (3, 3), Bit0 = (+2, +2) → (7, 7)
        bmap = (1 << 24) | (1 << 0)
        org = _make_org(
            bytearray([0x1A, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
            gene_signature=77,
        )
        world = _make_world()
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        # (5-2, 5-2) = (3, 3), (5+2, 5+2) = (7, 7)
        assert world.get_material(3, 3) == World.TOXIN
        assert world.toxin_life[3, 3] == TOX_LIFETIME
        assert world.toxin_signature[3, 3] == 77
        assert world.get_material(7, 7) == World.TOXIN
        assert world.toxin_life[7, 7] == TOX_LIFETIME
        assert world.toxin_signature[7, 7] == 77


# ── 腐蚀反应：中心格与邻居转化 ──


class TestCorrosionReaction:
    def test_center_toxin_becomes_empty(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)  # different → damage
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 5) == World.EMPTY
        assert world.toxin_life[5, 6] == 0

    def test_neighbor_toxin_becomes_nutrient(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)  # 中心
        _place_toxin(world, 7, 5, sig=99)  # 右侧邻居
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(7, 5) == World.NUTRIENT
        assert world.nutrient_life[5, 7] == NUTRIENT_LIFE
        assert world.toxin_life[5, 7] == 0

    def test_non_toxin_neighbor_unaffected(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)
        # 邻居为酶和信号 — 不应被转化
        world.set_material(6, 6, World.ENZYME)
        world.enzyme_life[6, 6] = 50
        world.set_material(5, 4, World.SIGNAL)
        world.signal_life[4, 5] = 30
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 6) == World.ENZYME
        assert world.enzyme_life[6, 6] == 50
        assert world.get_material(5, 4) == World.SIGNAL
        assert world.signal_life[4, 5] == 30

    def test_all_eight_neighbors_converted(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)  # 中心
        # Moore 8 邻居
        _place_toxin(world, 5, 4, sig=99)
        _place_toxin(world, 6, 4, sig=99)
        _place_toxin(world, 7, 4, sig=99)
        _place_toxin(world, 5, 5, sig=99)
        _place_toxin(world, 7, 5, sig=99)
        _place_toxin(world, 5, 6, sig=99)
        _place_toxin(world, 6, 6, sig=99)
        _place_toxin(world, 7, 6, sig=99)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (6 + dx) % 10
                ny = (5 + dy) % 10
                assert world.get_material(nx, ny) == World.NUTRIENT
                assert world.nutrient_life[ny, nx] == NUTRIENT_LIFE

    def test_no_neighbor_toxin_only_center_cleared(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)  # 孤立毒素
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 5) == World.EMPTY
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                assert world.get_material(6 + dx, 5 + dy) == World.EMPTY


# ── 免疫判定 ──


class TestImmuneCheck:
    def test_matching_signature_no_damage(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=42,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=42)  # matches org
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        move_cost = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 200 - move_cost  # no C_TOUCH_TOX

    def test_non_matching_signature_damage(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)  # different
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        move_cost = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 200 - C_TOUCH_TOX - move_cost

    def test_zero_toxin_signature_always_damages(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=77,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=0)  # uninitialized/wild
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        move_cost = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 200 - C_TOUCH_TOX - move_cost

    def test_zero_both_still_damages(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=0,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=0)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        move_cost = MOVE_BASE + MOVE_RATE * 1
        assert org.energy == 200 - C_TOUCH_TOX - move_cost

    def test_corrosion_still_occurs_when_immune(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=42,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=42)  # immune
        _place_toxin(world, 7, 5, sig=42)  # 邻居
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        # 中心清空
        assert world.get_material(6, 5) == World.EMPTY
        # 邻居转化为营养
        assert world.get_material(7, 5) == World.NUTRIENT
        assert world.nutrient_life[5, 7] == NUTRIENT_LIFE


# ── 移动触发腐蚀 ──


class TestMoveTriggersCorrosion:
    def test_move_x_triggers_corrosion(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 5, sig=99)
        _place_toxin(world, 6, 4, sig=99)  # 上方邻居
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 5) == World.EMPTY
        assert world.get_material(6, 4) == World.NUTRIENT

    def test_move_y_triggers_corrosion(self) -> None:
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0F, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[0, 1, 0, 0, 0, 5, 5],
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 5, 6, sig=99)
        _place_toxin(world, 4, 6, sig=99)  # 左侧邻居
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(5, 6) == World.EMPTY
        assert world.get_material(4, 6) == World.NUTRIENT

    def test_move_bmap_triggers_corrosion(self) -> None:
        vm = VirtualMachine()
        bmap = 1 << 6  # (+1, +1) → target (6, 6)
        org = _make_org(
            bytearray([0x15, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[bmap, 0, 0, 0, 0, 5, 5],
            energy=500,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 6, 6, sig=99)
        _place_toxin(world, 7, 6, sig=99)  # 右侧邻居
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(6, 6) == World.EMPTY
        assert world.get_material(7, 6) == World.NUTRIENT


# ── 边界包装 ──


class TestCorrosionWrapping:
    def test_corrosion_wraps_at_edges(self) -> None:
        # 从 (9, 9) 移动到 (0, 9)（右边界环绕到左边界）
        vm = VirtualMachine()
        org = _make_org(
            bytearray([0x0E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            regs=[1, 0, 0, 0, 0, 9, 9],  # dx=1 → (9+1)%10=0
            energy=200,
            gene_signature=10,
        )
        world = _make_world()
        _place_toxin(world, 0, 9, sig=99)  # 中心 target (0, 9)
        # Moore 邻居 (0-1, 9) = (9, 9) — 左侧邻居（环形）
        _place_toxin(world, 9, 9, sig=99)
        pop = Population(10)
        vm.execute_instruction(org, world, pop)

        assert world.get_material(0, 9) == World.EMPTY
        assert world.get_material(9, 9) == World.NUTRIENT
