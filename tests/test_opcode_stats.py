"""基因组指令统计测试 - opcode 频次与覆盖广度"""

from cyberterrarium.model.config import OPCODE_SAMPLE_INTERVAL
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.isa import LEGAL_OPCODES
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World


def _make_controller(w: int = 10, h: int = 10) -> SimulationController:
    world = World(w, h)
    pop = Population(max_capacity=100)
    return SimulationController(world, pop)


def _spawn_org(ctrl: SimulationController, x: int, y: int, genome: bytearray, energy: int = 500) -> int:
    org_id = ctrl.population.spawn(genome=genome, x=x, y=y, energy=energy)
    if org_id >= 0:
        ctrl.world.set_entity(x, y, ctrl.population.pool[org_id])
    return org_id


# ═══════════════════════════════════════════
# 采样周期
# ═══════════════════════════════════════════


class TestSampleInterval:
    def test_first_sample_triggers(self) -> None:
        """首次调用时 _last_sample_tick 初始值远小于 current_tick，触发采样。"""
        ctrl = _make_controller()
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._maybe_sample_opcode_stats()
        assert ctrl._last_sample_tick == OPCODE_SAMPLE_INTERVAL

    def test_skip_within_interval(self) -> None:
        """在采样间隔内不更新快照。"""
        ctrl = _make_controller()
        ctrl._last_sample_tick = 100
        ctrl.current_tick = 100 + OPCODE_SAMPLE_INTERVAL - 1
        # 弄脏快照以验证不会被覆盖
        ctrl._opcode_total_counts = {0xFF: 999}
        ctrl._opcode_org_counts = {0xFF: 999}
        ctrl._maybe_sample_opcode_stats()
        assert ctrl._opcode_total_counts == {0xFF: 999}
        assert ctrl._last_sample_tick == 100

    def test_sample_at_or_beyond_interval(self) -> None:
        """差值 >= interval 时触发采样。"""
        ctrl = _make_controller()
        ctrl._last_sample_tick = 100
        ctrl.current_tick = 100 + OPCODE_SAMPLE_INTERVAL
        ctrl._maybe_sample_opcode_stats()
        assert ctrl._last_sample_tick == 100 + OPCODE_SAMPLE_INTERVAL


# ═══════════════════════════════════════════
# 空种群
# ═══════════════════════════════════════════


class TestEmptyPopulation:
    def test_all_zero_counts(self) -> None:
        """空种群时所有 opcode 计数为 0。"""
        ctrl = _make_controller()
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()
        for op in LEGAL_OPCODES:
            assert ctrl._opcode_total_counts[op] == 0
            assert ctrl._opcode_org_counts[op] == 0

    def test_all_legal_opcodes_present_in_result(self) -> None:
        """结果字典包含所有合法 opcode 的键（即使计数为0）。"""
        ctrl = _make_controller()
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._maybe_sample_opcode_stats()
        for op in LEGAL_OPCODES:
            assert op in ctrl._opcode_total_counts
            assert op in ctrl._opcode_org_counts
        assert len(ctrl._opcode_total_counts) == len(LEGAL_OPCODES)
        assert len(ctrl._opcode_org_counts) == len(LEGAL_OPCODES)


# ═══════════════════════════════════════════
# 单生物
# ═══════════════════════════════════════════


class TestSingleOrganism:
    def test_single_opcode_count(self) -> None:
        """基因组中每条指令被计为一次 total，org 计数为 1。"""
        ctrl = _make_controller()
        # MOV 0x04, ATTACK 0x0A, SCAN_NUT 0x14 — 各一条，共3条指令=12字节
        genome = bytearray([
            0x04, 0x00, 0x00, 0x00,   # MOV
            0x0A, 0x00, 0x00, 0x00,   # ATTACK
            0x14, 0x00, 0x00, 0x00,   # SCAN_NUT
        ])
        _spawn_org(ctrl, 0, 0, genome)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        assert ctrl._opcode_total_counts[0x04] == 1
        assert ctrl._opcode_total_counts[0x0A] == 1
        assert ctrl._opcode_total_counts[0x14] == 1
        assert ctrl._opcode_org_counts[0x04] == 1
        assert ctrl._opcode_org_counts[0x0A] == 1
        assert ctrl._opcode_org_counts[0x14] == 1
        # 其余 opcode 均为 0
        for op in LEGAL_OPCODES:
            if op not in (0x04, 0x0A, 0x14):
                assert ctrl._opcode_total_counts[op] == 0

    def test_duplicate_opcode_in_genome(self) -> None:
        """同一指令多次出现：total 计数每次出现，org 计数仅 1。"""
        ctrl = _make_controller()
        # MOV 出现 3 次
        genome = bytearray([
            0x04, 0x00, 0x00, 0x00,
            0x04, 0x01, 0x02, 0x03,
            0x04, 0x0A, 0x0B, 0x0C,
        ])
        _spawn_org(ctrl, 0, 0, genome)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        assert ctrl._opcode_total_counts[0x04] == 3
        assert ctrl._opcode_org_counts[0x04] == 1


# ═══════════════════════════════════════════
# 多生物
# ═══════════════════════════════════════════


class TestMultipleOrganisms:
    def test_total_sums_across_organisms(self) -> None:
        """total 计数是所有生物 genomic 中出现次数的总和。"""
        ctrl = _make_controller()
        # 生物1: MOV × 2
        g1 = bytearray([0x04, 0, 0, 0, 0x04, 0, 0, 0])
        # 生物2: MOV × 1, ATTACK × 1
        g2 = bytearray([0x04, 0, 0, 0, 0x0A, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, g1)
        _spawn_org(ctrl, 1, 1, g2)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        assert ctrl._opcode_total_counts[0x04] == 3  # 2 + 1
        assert ctrl._opcode_total_counts[0x0A] == 1

    def test_org_counts_unique_per_organism(self) -> None:
        """org 计数每个生物仅计一次，即使同一指令在基因组中出现多次。"""
        ctrl = _make_controller()
        # 生物1: MOV × 3
        g1 = bytearray([0x04, 0, 0, 0, 0x04, 0, 0, 0, 0x04, 0, 0, 0])
        # 生物2: MOV × 1
        g2 = bytearray([0x04, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, g1)
        _spawn_org(ctrl, 1, 1, g2)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        assert ctrl._opcode_org_counts[0x04] == 2  # 2 个生物都有 MOV

    def test_shared_and_unique_opcodes(self) -> None:
        """两种生物共享指令和独有指令分别正确计数。"""
        ctrl = _make_controller()
        # 生物1: MOV + ATTACK
        g1 = bytearray([0x04, 0, 0, 0, 0x0A, 0, 0, 0])
        # 生物2: MOV + SCAN_NUT
        g2 = bytearray([0x04, 0, 0, 0, 0x14, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, g1)
        _spawn_org(ctrl, 1, 1, g2)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        # MOV 两个生物都有
        assert ctrl._opcode_total_counts[0x04] == 2
        assert ctrl._opcode_org_counts[0x04] == 2
        # ATTACK 仅生物1
        assert ctrl._opcode_total_counts[0x0A] == 1
        assert ctrl._opcode_org_counts[0x0A] == 1
        # SCAN_NUT 仅生物2
        assert ctrl._opcode_total_counts[0x14] == 1
        assert ctrl._opcode_org_counts[0x14] == 1


# ═══════════════════════════════════════════
# 死亡生物
# ═══════════════════════════════════════════


class TestDeadOrganismsExcluded:
    def test_dead_org_not_counted(self) -> None:
        """alive=False 的生物不计入统计。"""
        ctrl = _make_controller()
        # 存活生物: MOV
        g1 = bytearray([0x04, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, g1)
        # 死亡生物: ATTACK（不应计入）
        g2 = bytearray([0x0A, 0, 0, 0])
        dead_id = _spawn_org(ctrl, 1, 1, g2)
        ctrl.population.pool[dead_id].alive = False
        ctrl.world.set_entity(1, 1, None)

        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        # MOV 被计，ATTACK 不计
        assert ctrl._opcode_org_counts[0x04] == 1
        assert ctrl._opcode_org_counts[0x0A] == 0
        assert ctrl._opcode_total_counts[0x0A] == 0


# ═══════════════════════════════════════════
# 非法 opcode
# ═══════════════════════════════════════════


class TestInvalidOpcodes:
    def test_illegal_opcode_ignored(self) -> None:
        """不在 LEGAL_OPCODES 中的 opcode 被跳过。"""
        ctrl = _make_controller()
        # 0xFF 不是合法指令
        genome = bytearray([0xFF, 0, 0, 0, 0x04, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, genome)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        # 0xFF 不在字典中，不影响结果
        assert ctrl._opcode_total_counts[0x04] == 1
        assert 0xFF not in ctrl._opcode_total_counts

    def test_all_illegal_genome(self) -> None:
        """基因组全为非法 opcode 时不会崩溃，所有计数为 0。"""
        ctrl = _make_controller()
        genome = bytearray([0xFE, 0, 0, 0, 0xFD, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, genome)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        for op in LEGAL_OPCODES:
            assert ctrl._opcode_total_counts[op] == 0
            assert ctrl._opcode_org_counts[op] == 0


# ═══════════════════════════════════════════
# 重置行为
# ═══════════════════════════════════════════


class TestResetPerSample:
    def test_counts_reset_each_sample(self) -> None:
        """每次采样都先清零再统计，不会累积跨采样周期的计数。"""
        ctrl = _make_controller()
        # 第一次采样——有生物
        genome = bytearray([0x04, 0, 0, 0])
        _spawn_org(ctrl, 0, 0, genome)
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()
        assert ctrl._opcode_total_counts[0x04] == 1

        # 杀死所有生物，第二次采样
        for org in ctrl.population.get_alive_list():
            org.alive = False
            ctrl.world.set_entity(org.regs[5], org.regs[6], None)
        assert ctrl.population.alive_count == 0
        ctrl.current_tick = OPCODE_SAMPLE_INTERVAL * 2
        ctrl._rebuild_alive_cache()
        ctrl._maybe_sample_opcode_stats()

        # 应该重置为 0，而不是保留上一次的计数
        assert ctrl._opcode_total_counts[0x04] == 0
        assert ctrl._opcode_org_counts[0x04] == 0


# ═══════════════════════════════════════════
# ViewAPI 接口
# ═══════════════════════════════════════════


class TestViewAPI:
    def test_get_opcode_total_counts(self) -> None:
        """ViewAPI 零拷贝返回控制器的 _opcode_total_counts。"""
        from cyberterrarium.facade.api import ViewAPI
        ctrl = _make_controller()
        ctrl._opcode_total_counts = {0x04: 5, 0x0A: 3}
        api = ViewAPI(ctrl)
        assert api.get_opcode_total_counts() == {0x04: 5, 0x0A: 3}

    def test_get_opcode_org_counts(self) -> None:
        """ViewAPI 零拷贝返回控制器的 _opcode_org_counts。"""
        from cyberterrarium.facade.api import ViewAPI
        ctrl = _make_controller()
        ctrl._opcode_org_counts = {0x04: 2, 0x0A: 1}
        api = ViewAPI(ctrl)
        assert api.get_opcode_org_counts() == {0x04: 2, 0x0A: 1}

    def test_empty_dict_for_uninitialized_stats(self) -> None:
        """未采样时返回空字典。"""
        from cyberterrarium.facade.api import ViewAPI
        ctrl = _make_controller()
        api = ViewAPI(ctrl)
        assert api.get_opcode_total_counts() == {}
        assert api.get_opcode_org_counts() == {}
