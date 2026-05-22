"""SCAN_BIO指令测试"""

from cyberterrarium.model.bitmap import BMAP_OFFSETS
from cyberterrarium.model.config import C_SCAN_BIO
from cyberterrarium.model.fingerprint import compute_fingerprint
from cyberterrarium.model.organism import Organism
from cyberterrarium.model.population import Population
from cyberterrarium.model.vm import VirtualMachine
from cyberterrarium.model.world import World


def _make_org(
    genome: bytearray | None = None,
    pc: int = 0,
    energy: int = 500,
    regs: list[int] | None = None,
    fingerprint: set[int] | None = None,
) -> Organism:
    if genome is None:
        genome = bytearray(8)
    if regs is None:
        regs = [0] * Organism.REG_COUNT
    org = Organism(
        org_id=0,
        alive=True,
        pc=pc,
        regs=regs,
        equal_flag=False,
        energy=energy,
        age=0,
        genome=genome,
        fingerprint=fingerprint,
    )
    return org


def _genome_a() -> bytearray:
    # 4条指令的基因组，用于构造指纹
    return bytearray([0x01, 0, 1, 0, 0x0B, 0, 0, 0, 0x10, 0, 1, 0, 0x12, 0xFC, 0, 0])


def _genome_b() -> bytearray:
    # 不同的opcode序列
    return bytearray([0x09, 0, 1, 0, 0x0C, 2, 0, 0, 0x0D, 0, 0, 0, 0x0B, 0, 0, 0])


# ── SCAN_BIO_G (0x2A) ──


class TestScanBioG:
    def test_detects_identical_species(self) -> None:
        # 相同基因组 → Jaccard=1.0 > 0.5
        vm = VirtualMachine()
        genome = _genome_a()
        fp = compute_fingerprint(genome)
        # SCAN_BIO_G R0, 64 (threshold = 64/127 ≈ 0.504)
        org = _make_org(
            bytearray([0x2A, 0x00, 0x40, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(genome, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # (+1,+1) = Bit6
        assert org.regs[Organism.R0] & (1 << 6) != 0

    def test_ignores_different_species(self) -> None:
        # 不同基因组 → Jaccard≈0，不满足 > 0.9
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        # SCAN_BIO_G R0, 114 (threshold ≈ 0.898)
        org = _make_org(
            bytearray([0x2A, 0x00, 0x72, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == 0

    def test_self_excluded(self) -> None:
        # 自身位置(0,0) = Bit12 应被跳过
        vm = VirtualMachine()
        genome = _genome_a()
        fp = compute_fingerprint(genome)
        # SCAN_BIO_G R0, 0 (threshold=0, 任何Jaccard>0都匹配)
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # Bit12 (自身位置) 不应被置位
        assert org.regs[Organism.R0] & (1 << 12) == 0

    def test_empty_cell_skipped(self) -> None:
        # 无生物的格子不应被置位
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == 0

    def test_energy_cost_deducted(self) -> None:
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            energy=500,
            fingerprint=fp,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.energy == 500 - C_SCAN_BIO

    def test_insufficient_energy_no_op(self) -> None:
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            energy=C_SCAN_BIO - 1,
            fingerprint=fp,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        target = _make_org(_genome_a(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == 0
        assert org.energy == C_SCAN_BIO - 1

    def test_arith_target_protects_inv(self) -> None:
        # p1=4 → INV, 应被 _data_reg 降级为 R0
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2A, 0x04, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(_genome_a(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.INV] == 0
        assert org.regs[Organism.R0] != 0

    def test_empty_fingerprint_treated_as_zero_similarity(self) -> None:
        # 空指纹 → sim=0，不满足 > 0
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        # SCAN_BIO_G R0, 0 (threshold=0, sim>0才匹配)
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        # 短基因组 → 空指纹
        target = _make_org(
            bytearray([0x01, 0, 1, 0]),
            regs=[0, 0, 0, 0, 0, 6, 6],
            fingerprint=set(),
        )
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # sim=0, 不满足 > 0
        assert org.regs[Organism.R0] & (1 << 6) == 0

    def test_none_fingerprint_treated_as_zero_similarity(self) -> None:
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        # 未计算指纹 → None
        target = _make_org(
            bytearray([0x01, 0, 1, 0]),
            regs=[0, 0, 0, 0, 0, 6, 6],
            fingerprint=None,
        )
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] & (1 << 6) == 0

    def test_multiple_targets(self) -> None:
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        # SCAN_BIO_G R0, 64 (threshold ≈ 0.504)
        org = _make_org(
            bytearray([0x2A, 0x00, 0x40, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        # 同种在(+1,+1)=Bit6
        same = _make_org(_genome_a(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        same.org_id = 1
        # 异种在(-1,+1)=Bit8
        diff = _make_org(_genome_b(), regs=[0, 0, 0, 0, 0, 4, 6], fingerprint=fp_b)
        diff.org_id = 2
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, same)
        world.set_entity(4, 6, diff)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # 同种(Bit6)应匹配，异种(Bit8)不应匹配
        assert org.regs[Organism.R0] & (1 << 6) != 0
        assert org.regs[Organism.R0] & (1 << 8) == 0


# ── SCAN_BIO_L (0x2B) ──


class TestScanBioL:
    def test_detects_different_species(self) -> None:
        # 不同基因组 → Jaccard≈0 < 0.5
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        # SCAN_BIO_L R0, 64 (threshold ≈ 0.504)
        org = _make_org(
            bytearray([0x2B, 0x00, 0x40, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] & (1 << 6) != 0

    def test_ignores_identical_species(self) -> None:
        # 相同基因组 → Jaccard=1.0，不满足 < 0.5
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        # SCAN_BIO_L R0, 64 (threshold ≈ 0.504)
        org = _make_org(
            bytearray([0x2B, 0x00, 0x40, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(_genome_a(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == 0

    def test_zero_threshold_never_matches(self) -> None:
        # SCAN_BIO_L R0, 0 → threshold=0, Jaccard ≥ 0 → sim < 0 永不成立
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2B, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] == 0

    def test_full_threshold_matches_low_similarity(self) -> None:
        # SCAN_BIO_L R0, 127 → threshold=1.0, sim=0 < 1.0 匹配
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2B, 0x00, 0x7F, 0x00]),
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] & (1 << 6) != 0


# ── 位图一致性验证 ──


class TestScanBioBitmap:
    def test_bitmap_matches_bmap_offsets(self) -> None:
        # 验证SCAN_BIO_G输出的位图与BMAP_OFFSETS一致
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        # SCAN_BIO_G R0, 0 (threshold=0, 任何sim>0匹配)
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00]),
            regs=[0, 0, 0, 0, 0, 10, 10],
            fingerprint=fp,
        )
        world = World(20, 20)
        world.set_entity(10, 10, org)
        # 在所有25个5×5位置放同种生物
        expected_bits = set()
        for bit_idx, (dx, dy) in enumerate(BMAP_OFFSETS):
            if dx == 0 and dy == 0:
                continue  # 自身位置跳过
            tx, ty = 10 + dx, 10 + dy
            t = _make_org(_genome_a(), regs=[0, 0, 0, 0, 0, tx, ty], fingerprint=fp)
            t.org_id = bit_idx + 10
            world.set_entity(tx, ty, t)
            expected_bits.add(bit_idx)
        pop = Population(50)

        vm.execute_instruction(org, world, pop)

        result = org.regs[Organism.R0]
        for bit_idx in expected_bits:
            assert result & (1 << bit_idx) != 0, f"Bit{bit_idx} should be set"
        assert result & (1 << 12) == 0, "Bit12 (self) should not be set"

    def test_pc_advances(self) -> None:
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2A, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
            pc=0,
            fingerprint=fp,
            regs=[0, 0, 0, 0, 0, 5, 5],
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.pc == 4
