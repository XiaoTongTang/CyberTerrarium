"""仿真控制器测试 - 种植反应与酶衰减"""

import numpy as np

from cyberterrarium.model.config import ENZ_LIFE, NUTRIENT_LIFE
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World


def _make_controller(w: int = 10, h: int = 10) -> SimulationController:
    world = World(w, h)
    pop = Population(max_capacity=100)
    return SimulationController(world, pop)


class TestDilate4:
    def test_single_center(self) -> None:
        # 单个True在中心，膨胀后上下左右为True
        ctrl = _make_controller(5, 5)
        mask = np.zeros((5, 5), dtype=bool)
        mask[2, 2] = True
        result = ctrl._dilate_4(mask)
        assert result[2, 2] is np.True_
        assert result[1, 2] is np.True_
        assert result[3, 2] is np.True_
        assert result[2, 1] is np.True_
        assert result[2, 3] is np.True_
        # 对角线不应膨胀
        assert result[1, 1] is np.False_

    def test_empty(self) -> None:
        ctrl = _make_controller(5, 5)
        mask = np.zeros((5, 5), dtype=bool)
        result = ctrl._dilate_4(mask)
        assert not result.any()

    def test_wrap_around(self) -> None:
        # 环形边界：顶部行膨胀应到达底部行
        ctrl = _make_controller(5, 5)
        mask = np.zeros((5, 5), dtype=bool)
        mask[0, 2] = True
        result = ctrl._dilate_4(mask)
        assert result[4, 2] is np.True_  # 上方邻居环绕到底部


class TestDilate3x3:
    def test_single_center(self) -> None:
        ctrl = _make_controller(5, 5)
        mask = np.zeros((5, 5), dtype=bool)
        mask[2, 2] = True
        result = ctrl._dilate_3x3(mask)
        # 3×3全为True
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                assert result[2 + dy, 2 + dx] is np.True_
        # 外围为False
        assert result[0, 0] is np.False_
        assert result[4, 4] is np.False_

    def test_empty(self) -> None:
        ctrl = _make_controller(5, 5)
        mask = np.zeros((5, 5), dtype=bool)
        result = ctrl._dilate_3x3(mask)
        assert not result.any()


class TestPlantingReaction:
    def test_basic_reaction(self) -> None:
        # 酶旁边有营养 → 消耗酶，以营养为中心3×3生成新营养
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        # 营养在(2,2)，酶在(2,3)——4连通相邻
        grid[2, 2] = World.NUTRIENT
        ctrl.world.nutrient_life[2, 2] = NUTRIENT_LIFE
        grid[2, 3] = World.ENZYME
        ctrl.world.enzyme_life[2, 3] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 酶被消耗，且酶位(2,3)在营养(2,2)的3×3范围内，被新营养覆盖
        assert grid[2, 3] == World.NUTRIENT
        assert ctrl.world.enzyme_life[2, 3] == 0
        # 以营养(2,2)为中心3×3区域应有营养
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                assert grid[2 + dy, 2 + dx] == World.NUTRIENT

    def test_no_nutrient_no_reaction(self) -> None:
        # 酶旁边没有营养 → 不反应
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.ENZYME
        ctrl.world.enzyme_life[2, 2] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 酶仍存在（未被触发，由酶衰减处理）
        assert grid[2, 2] == World.ENZYME

    def test_toxin_blocks_expansion(self) -> None:
        # 毒素不可被营养覆盖
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.NUTRIENT
        ctrl.world.nutrient_life[2, 2] = NUTRIENT_LIFE
        grid[3, 2] = World.ENZYME
        ctrl.world.enzyme_life[3, 2] = ENZ_LIFE
        # 在3×3范围内放置毒素
        grid[1, 1] = World.TOXIN

        ctrl.execute_phase_1()

        # 毒素位不被覆盖
        assert grid[1, 1] == World.TOXIN

    def test_signal_blocks_expansion(self) -> None:
        # 信号不可被营养覆盖
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.NUTRIENT
        ctrl.world.nutrient_life[2, 2] = NUTRIENT_LIFE
        grid[3, 2] = World.ENZYME
        ctrl.world.enzyme_life[3, 2] = ENZ_LIFE
        grid[1, 1] = World.SIGNAL
        ctrl.world.signal_life[1, 1] = 50

        ctrl.execute_phase_1()

        assert grid[1, 1] == World.SIGNAL

    def test_enzyme_consumed_clears_life(self) -> None:
        # 酶被消耗后enzyme_life归零
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.NUTRIENT
        ctrl.world.nutrient_life[2, 2] = NUTRIENT_LIFE
        grid[2, 3] = World.ENZYME
        ctrl.world.enzyme_life[2, 3] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 酶被消耗，3×3覆盖后变为营养
        assert grid[2, 3] == World.NUTRIENT
        assert ctrl.world.enzyme_life[2, 3] == 0

    def test_new_nutrient_gets_life(self) -> None:
        # 新生成的营养获得完整NUTRIENT_LIFE
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.NUTRIENT
        ctrl.world.nutrient_life[2, 2] = NUTRIENT_LIFE
        grid[3, 2] = World.ENZYME
        ctrl.world.enzyme_life[3, 2] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 新营养（衰减后应为NUTRIENT_LIFE-1，因为先反应后衰减）
        assert ctrl.world.nutrient_life[1, 1] == NUTRIENT_LIFE - 1

    def test_multiple_enzymes_trigger(self) -> None:
        # 多个酶同时被触发
        ctrl = _make_controller(7, 7)
        grid = ctrl.world.grid
        # 两个营养相距较远，各有相邻的酶
        grid[1, 1] = World.NUTRIENT
        ctrl.world.nutrient_life[1, 1] = NUTRIENT_LIFE
        grid[1, 2] = World.ENZYME
        ctrl.world.enzyme_life[1, 2] = ENZ_LIFE
        grid[5, 5] = World.NUTRIENT
        ctrl.world.nutrient_life[5, 5] = NUTRIENT_LIFE
        grid[5, 4] = World.ENZYME
        ctrl.world.enzyme_life[5, 4] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 两个酶都被消耗（被3×3覆盖为营养）
        assert grid[1, 2] == World.NUTRIENT
        assert ctrl.world.enzyme_life[1, 2] == 0
        assert grid[5, 4] == World.NUTRIENT
        assert ctrl.world.enzyme_life[5, 4] == 0

    def test_ripple_expansion(self) -> None:
        # 验证"水波纹外推"：酶在营养对角线位置，只有相邻营养被触发
        ctrl = _make_controller(7, 7)
        grid = ctrl.world.grid
        # 营养在(3,3)，酶在(4,4)（对角线，非4连通）
        grid[3, 3] = World.NUTRIENT
        ctrl.world.nutrient_life[3, 3] = NUTRIENT_LIFE
        grid[4, 4] = World.ENZYME
        ctrl.world.enzyme_life[4, 4] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 酶(4,4)不在营养(3,3)的4连通范围内 → 不触发
        assert grid[4, 4] == World.ENZYME


class TestEnzymeDecay:
    def test_enzyme_decays(self) -> None:
        # 酶生命值递减
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.ENZYME
        ctrl.world.enzyme_life[2, 2] = 3

        ctrl.execute_phase_1()

        assert ctrl.world.enzyme_life[2, 2] == 2
        assert grid[2, 2] == World.ENZYME

    def test_enzyme_expires(self) -> None:
        # 酶生命值归零后变为空地
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.ENZYME
        ctrl.world.enzyme_life[2, 2] = 1

        ctrl.execute_phase_1()

        assert ctrl.world.enzyme_life[2, 2] == 0
        assert grid[2, 2] == World.EMPTY

    def test_enzyme_life_zero_not_counted(self) -> None:
        # enzyme_life=0的格子不应被衰减到负数
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.EMPTY
        ctrl.world.enzyme_life[2, 2] = 0

        ctrl.execute_phase_1()

        assert ctrl.world.enzyme_life[2, 2] == 0

    def test_multiple_enzymes_decay(self) -> None:
        # 多个酶同时衰减
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[1, 1] = World.ENZYME
        ctrl.world.enzyme_life[1, 1] = 2
        grid[3, 3] = World.ENZYME
        ctrl.world.enzyme_life[3, 3] = 1

        ctrl.execute_phase_1()

        assert ctrl.world.enzyme_life[1, 1] == 1
        assert grid[1, 1] == World.ENZYME
        assert ctrl.world.enzyme_life[3, 3] == 0
        assert grid[3, 3] == World.EMPTY


class TestPhase1Ordering:
    def test_planting_before_decay(self) -> None:
        # 种植反应在营养衰减之前执行：新生营养参与本Tick衰减
        ctrl = _make_controller(5, 5)
        grid = ctrl.world.grid
        grid[2, 2] = World.NUTRIENT
        ctrl.world.nutrient_life[2, 2] = NUTRIENT_LIFE
        grid[3, 2] = World.ENZYME
        ctrl.world.enzyme_life[3, 2] = ENZ_LIFE

        ctrl.execute_phase_1()

        # 新营养(1,1)先被种植反应设为NUTRIENT_LIFE，再被衰减-1
        assert ctrl.world.nutrient_life[1, 1] == NUTRIENT_LIFE - 1

    def test_enzyme_decay_after_planting(self) -> None:
        # 酶衰减在种植反应之后：未触发酶正常衰减
        ctrl = _make_controller(7, 7)
        grid = ctrl.world.grid
        grid[1, 1] = World.NUTRIENT
        ctrl.world.nutrient_life[1, 1] = NUTRIENT_LIFE
        # 触发酶（4连通相邻营养）
        grid[1, 2] = World.ENZYME
        ctrl.world.enzyme_life[1, 2] = ENZ_LIFE
        # 未触发酶（旁边无营养，且在3×3范围外）
        grid[5, 5] = World.ENZYME
        ctrl.world.enzyme_life[5, 5] = 1

        ctrl.execute_phase_1()

        # 触发酶被消耗（被新营养覆盖）
        assert grid[1, 2] == World.NUTRIENT
        assert ctrl.world.enzyme_life[1, 2] == 0
        # 未触发酶因衰减到期而消失
        assert grid[5, 5] == World.EMPTY
