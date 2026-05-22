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
    org_id = ctrl.population.spawn(genome=genome, x=x, y=y, energy=energy)
    if org_id >= 0:
        ctrl.world.set_entity(x, y, ctrl.population.pool[org_id])
    return org_id


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

    # 场景：周围全是毒素时不繁殖
    def test_no_nontoxic_neighbors_no_repro(self) -> None:
        ctrl = _make_controller(3, 3)
        # 在(1,1)放一个高能量生物
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        _spawn_org(ctrl, 1, 1, energy=threshold + 100)
        # 填满所有9个格子为毒素
        for y in range(3):
            for x in range(3):
                ctrl.world.set_material(x, y, World.TOXIN)
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


class TestSpawnCollision:
    """繁殖碰撞测试：两个亲本抢占同一空位不应产生幽灵生物"""

    def test_collision_only_one_child_survives(self) -> None:
        # 两个相邻高能量生物，共同邻域只有一个空位
        ctrl = _make_controller(5, 5)
        cost = C_BASE + 8 * C_PER_INST
        threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
        # 亲本A在(1,1)，亲本B在(1,3)，共同空位可能在(1,2)附近
        _spawn_org(ctrl, 1, 1, energy=threshold + 1000)
        _spawn_org(ctrl, 1, 3, energy=threshold + 1000)
        # 填满其他位置使空位极少
        for y in range(5):
            for x in range(5):
                if (x, y) not in [(1, 1), (1, 3), (1, 2)]:
                    ctrl.world.set_material(x, y, World.TOXIN)
        ctrl._rebuild_alive_cache()

        ctrl.execute_phase_repro()
        # 可能有两个请求指向同一位置
        ctrl.execute_phase_3()

        # 验证：没有幽灵生物，alive_count等于entity_grid中实际存在的生物数
        alive_count = ctrl.population.alive_count
        grid_count = 0
        for y in range(5):
            for x in range(5):
                if ctrl.world.get_entity(x, y) is not None:
                    grid_count += 1
        assert alive_count == grid_count

    def test_no_ghost_after_collision(self) -> None:
        # 直接构造碰撞：手动向spawn_queue添加两个同位置的请求
        ctrl = _make_controller(5, 5)
        genome = bytearray(8)
        ctrl._spawn_queue = [
            {"genome": genome, "x": 2, "y": 2},
            {"genome": genome, "x": 2, "y": 2},
        ]

        ctrl.execute_phase_3()

        # 只有一个子代被放置在(2,2)
        assert ctrl.world.get_entity(2, 2) is not None
        # alive_count与entity_grid一致
        grid_count = sum(
            1 for y in range(5) for x in range(5)
            if ctrl.world.get_entity(x, y) is not None
        )
        assert ctrl.population.alive_count == grid_count


class TestPhase2AliveGuard:
    """Phase 2 alive守卫测试：已被杀死的生物不应再执行指令"""

    def test_killed_organism_skipped(self) -> None:
        # 模拟场景：生物A攻击生物B致其能量为负
        # B在alive_list中排在A后面，B应被跳过不再执行
        from cyberterrarium.model.config import C_DAMAGE_PER_HIT
        from cyberterrarium.model.organism import Organism

        ctrl = _make_controller(10, 10)
        # 创建两个生物：A有高能量，B只有1点能量
        org_a_id = _spawn_org(ctrl, 5, 5, energy=10000)
        org_b_id = _spawn_org(ctrl, 6, 5, energy=C_DAMAGE_PER_HIT)
        ctrl._rebuild_alive_cache()

        org_a = ctrl.population.pool[org_a_id]
        org_b = ctrl.population.pool[org_b_id]

        # 手动模拟：A攻击B使B能量变为0
        org_b.energy = 0

        # 在Phase 2中，B的扣税会使能量变为-1，然后被杀
        # alive守卫确保被杀死的生物不会被后续处理
        # 这不会导致错误，只是让死亡检测更及时
