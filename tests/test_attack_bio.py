"""选择性攻击指令测试 - ATTACK_L / ATTACK_G"""

from cyberterrarium.model.bitmap import BMAP_OFFSETS
from cyberterrarium.model.config import (
    C_ATTACK_BASE,
    C_ATTACK_PER_BIT,
    C_DAMAGE_PER_HIT,
    C_LEECH_PER_HIT,
    C_SCAN_BIO,
)
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
    return Organism(
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


def _genome_a() -> bytearray:
    return bytearray([0x01, 0, 1, 0, 0x0B, 0, 0, 0, 0x10, 0, 1, 0, 0x12, 0xFC, 0, 0])


def _genome_b() -> bytearray:
    return bytearray([0x09, 0, 1, 0, 0x0C, 2, 0, 0, 0x0D, 0, 0, 0, 0x0B, 0, 0, 0])


# ── ATTACK_L (0x2C) ──


class TestAttackL:
    def test_attacks_different_species(self) -> None:
        # ATTACK_L R0, 128 (threshold≈0.5): 攻击异种(Jaccard≈0 < 0.5)
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert target.energy == 200 - C_DAMAGE_PER_HIT
        assert org.energy > 0  # 吸血恢复

    def test_does_not_attack_same_species(self) -> None:
        # ATTACK_L R0, 128 (threshold≈0.5): 同种Jaccard=1.0，不满足 < 0.5
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(_genome_a(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert target.energy == 200

    def test_writes_bitmap_to_rx(self) -> None:
        # ATTACK_L 同时写回位图
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # (+1,+1) = Bit6 应被置位
        assert org.regs[Organism.R0] & (1 << 6) != 0

    def test_self_excluded(self) -> None:
        # 自身位置(0,0) = Bit12 不应被攻击也不应置位
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        world = World(10, 10)
        world.set_entity(5, 5, org)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] & (1 << 12) == 0


# ── ATTACK_G (0x2D) ──


class TestAttackG:
    def test_attacks_same_species(self) -> None:
        # ATTACK_G R0, 128 (threshold≈0.5): 攻击同种(Jaccard=1.0 > 0.5)
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2D, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(_genome_a(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert target.energy == 200 - C_DAMAGE_PER_HIT

    def test_does_not_attack_different_species(self) -> None:
        # ATTACK_G R0, 128 (threshold≈0.5): 异种Jaccard≈0，不满足 > 0.5
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2D, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert target.energy == 200

    def test_writes_bitmap_to_rx(self) -> None:
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2D, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(_genome_a(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.R0] & (1 << 6) != 0


# ── 能量与成本 ──


class TestAttackBioEnergy:
    def test_energy_cost_is_scan_plus_attack(self) -> None:
        # 成本 = C_SCAN_BIO + C_ATTACK_BASE + popcount * C_ATTACK_PER_BIT
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        energy_before = org.energy
        vm.execute_instruction(org, world, pop)

        # 1格命中：scan成本 + attack基础 + 1*per_bit - 吸血恢复
        expected_cost = C_SCAN_BIO + C_ATTACK_BASE + 1 * C_ATTACK_PER_BIT
        leech = C_LEECH_PER_HIT
        assert org.energy == energy_before - expected_cost + leech

    def test_insufficient_energy_for_scan_no_op(self) -> None:
        # 能量不足以支付scan成本
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=C_SCAN_BIO - 1,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert target.energy == 200
        assert org.regs[Organism.R0] == 0

    def test_insufficient_energy_for_attack_after_scan(self) -> None:
        # 能量够scan但不够attack：scan成本被消耗，attack不执行
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        # 仅够scan，不够attack
        energy = C_SCAN_BIO + C_ATTACK_BASE - 1
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=energy,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        # scan已扣费，bitmap已写入，但attack未执行
        assert org.regs[Organism.R0] != 0  # scan写入位图
        assert target.energy == 200  # 未被攻击
        assert org.energy == energy - C_SCAN_BIO  # 仅扣了scan成本

    def test_leech_restores_energy(self) -> None:
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.energy == 500 - C_SCAN_BIO - C_ATTACK_BASE - C_ATTACK_PER_BIT + C_LEECH_PER_HIT


# ── 多目标与位图一致性 ──


class TestAttackBioMultiple:
    def test_attack_only_matching_targets(self) -> None:
        # ATTACK_L: 只攻击异种，不攻击同种
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        # ATTACK_L R0, 128 (threshold≈0.5)
        org = _make_org(
            bytearray([0x2C, 0x00, 0x80, 0x00]),
            energy=1000,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        # 同种在(+1,+1)=Bit6 — 不应被攻击
        same = _make_org(_genome_a(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_a)
        same.org_id = 1
        # 异种在(-1,+1)=Bit8 — 应被攻击
        diff = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 4, 6], fingerprint=fp_b)
        diff.org_id = 2
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, same)
        world.set_entity(4, 6, diff)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert same.energy == 200  # 未被攻击
        assert diff.energy == 200 - C_DAMAGE_PER_HIT  # 被攻击
        # 位图：仅Bit8置位
        assert org.regs[Organism.R0] & (1 << 6) == 0
        assert org.regs[Organism.R0] & (1 << 8) != 0

    def test_arith_target_protects_inv(self) -> None:
        # p1=4 → INV, 应被 _data_reg 降级为 R0
        vm = VirtualMachine()
        fp_a = compute_fingerprint(_genome_a())
        fp_b = compute_fingerprint(_genome_b())
        org = _make_org(
            bytearray([0x2C, 0x04, 0x80, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp_a,
        )
        target = _make_org(_genome_b(), energy=200, regs=[0, 0, 0, 0, 0, 6, 6], fingerprint=fp_b)
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert org.regs[Organism.INV] == 0
        assert org.regs[Organism.R0] != 0

    def test_empty_fingerprint_no_attack(self) -> None:
        # 空指纹 → sim=0, ATTACK_G threshold=0 → 不满足 sim>0
        vm = VirtualMachine()
        fp = compute_fingerprint(_genome_a())
        org = _make_org(
            bytearray([0x2D, 0x00, 0x00, 0x00]),
            energy=500,
            regs=[0, 0, 0, 0, 0, 5, 5],
            fingerprint=fp,
        )
        target = _make_org(
            bytearray([0x01, 0, 1, 0]),
            energy=200,
            regs=[0, 0, 0, 0, 0, 6, 6],
            fingerprint=set(),
        )
        target.org_id = 1
        world = World(10, 10)
        world.set_entity(5, 5, org)
        world.set_entity(6, 6, target)
        pop = Population(10)

        vm.execute_instruction(org, world, pop)

        assert target.energy == 200
