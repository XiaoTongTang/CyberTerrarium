"""自动繁殖阶段测试"""

from cyberterrarium.model.config import (
    C_BASE,
    C_PER_INST,
    REPRO_ENERGY_MULTIPLIER,
)
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World


def _make_controller(world_w: int = 20, world_h: int = 20) -> SimulationController:
    world = World(world_w, world_h)
    pop = Population()
    return SimulationController(world, pop)


def _spawn_org(ctrl: SimulationController, x: int, y: int, energy: int) -> int:
    genome = bytearray(8)  # 8 bytes = 2 instructions, minimum length
    return ctrl.population.spawn(genome=genome, x=x, y=y, energy=energy)


class TestAutoRepro:
    # 场景：能量未达繁殖阈值，不繁殖
    def test_below_threshold_no_repro(self) -> None:
        ctrl = _make_controller()
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        _spawn_org(ctrl, 5, 5, energy=threshold - 1)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        assert ctrl.population.alive_count == 1
        assert len(ctrl._spawn_queue) == 0

    # 场景：能量达到繁殖阈值，触发繁殖
    def test_at_threshold_triggers_repro(self) -> None:
        ctrl = _make_controller()
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        _spawn_org(ctrl, 5, 5, energy=threshold)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        assert len(ctrl._spawn_queue) == 1

    # 场景：繁殖后父代能量正确扣除
    def test_parent_energy_deducted(self) -> None:
        ctrl = _make_controller()
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        org_id = _spawn_org(ctrl, 5, 5, energy=threshold + 50)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        org = ctrl.population.pool[org_id]
        assert org.energy == threshold + 50 - cost

    # 场景：种群满时不繁殖
    def test_population_full_no_repro(self) -> None:
        world = World(5, 5)
        pop = Population(max_capacity=2)
        ctrl = SimulationController(world, pop)
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        # 填满种群（2个生物，容量为2）
        _spawn_org(ctrl, 1, 1, energy=threshold)
        _spawn_org(ctrl, 3, 3, energy=threshold)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        assert len(ctrl._spawn_queue) == 0

    # 场景：周围无空格时不繁殖
    def test_no_empty_neighbors_no_repro(self) -> None:
        ctrl = _make_controller(3, 3)
        # 在(1,1)放一个高能量生物
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        _spawn_org(ctrl, 1, 1, energy=threshold + 100)
        # 填满所有9个格子为营养
        for y in range(3):
            for x in range(3):
                ctrl.world.set_material(x, y, World.NUTRIENT)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        assert len(ctrl._spawn_queue) == 0

    # 场景：多个生物可同时繁殖
    def test_multiple_organisms_repro(self) -> None:
        ctrl = _make_controller(50, 50)
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        _spawn_org(ctrl, 5, 5, energy=threshold)
        _spawn_org(ctrl, 25, 25, energy=threshold)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        assert len(ctrl._spawn_queue) == 2

    # 场景：Phase 3 结算后子代成功注入种群
    def test_phase3_settles_children(self) -> None:
        ctrl = _make_controller()
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        _spawn_org(ctrl, 5, 5, energy=threshold)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        ctrl.execute_phase_3()
        # 父代 + 1 个子代
        assert ctrl.population.alive_count == 2

    # 场景：SPLIT 指令不再产生 spawn request
    def test_split_no_longer_spawns(self) -> None:
        ctrl = _make_controller()
        # 创建一个基因组包含 SPLIT(0x14) 的生物
        genome = bytearray([0x14, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        ctrl.population.spawn(genome=genome, x=5, y=5, energy=10000)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_2()
        # Phase 2 不再收集 SPLIT 的 spawn request
        assert len(ctrl._spawn_queue) == 0
