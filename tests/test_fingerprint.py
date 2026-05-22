"""Winnowing指纹提取模块测试"""

from cyberterrarium.model.fingerprint import compute_fingerprint


class TestComputeFingerprint:
    def test_identical_genomes_same_fingerprint(self) -> None:
        genome = bytearray([0x01, 0x00, 0x01, 0x00, 0x10, 0x00, 0x01, 0x00,
                            0x13, 0xFE, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00])
        assert compute_fingerprint(genome) == compute_fingerprint(genome)

    def test_different_opcodes_different_fingerprint(self) -> None:
        g1 = bytearray([0x01, 0, 1, 0, 0x0B, 0, 0, 0, 0x13, 0xFE, 0, 0, 0x0B, 0, 0, 0])
        g2 = bytearray([0x09, 0, 1, 0, 0x0C, 2, 0, 0, 0x0D, 0, 0, 0, 0x0B, 0, 0, 0])
        assert compute_fingerprint(g1) != compute_fingerprint(g2)

    def test_operands_ignored(self) -> None:
        # 相同opcode序列，不同操作数 → 指纹相同
        g1 = bytearray([0x01, 0x00, 0x05, 0x00, 0x10, 0x00, 0x01, 0x00,
                         0x12, 0xFC, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00])
        g2 = bytearray([0x01, 0x03, 0xFF, 0x00, 0x10, 0x02, 0x03, 0x00,
                         0x12, 0x01, 0x00, 0x00, 0x0B, 0x00, 0x00, 0x00])
        assert compute_fingerprint(g1) == compute_fingerprint(g2)

    def test_empty_genome_returns_empty_set(self) -> None:
        assert compute_fingerprint(bytearray()) == set()

    def test_single_instruction_returns_empty_set(self) -> None:
        # 1条指令 → opcodes长度1 < k=2 → 空指纹
        assert compute_fingerprint(bytearray([0x01, 0, 1, 0])) == set()

    def test_two_instructions_hash_list_shorter_than_window(self) -> None:
        # 2条指令 → 1个k-gram哈希 → hash_list长度1 < w=3 → 取min
        genome = bytearray([0x01, 0, 1, 0, 0x0B, 0, 0, 0])
        fp = compute_fingerprint(genome)
        assert len(fp) == 1

    def test_sufficient_instructions_produces_fingerprint(self) -> None:
        # 4条指令 → 3个k-gram → 1个窗口 → 至少1个指纹
        genome = bytearray([0x01, 0, 1, 0, 0x0B, 0, 0, 0, 0x10, 0, 1, 0, 0x12, 0xFC, 0, 0])
        fp = compute_fingerprint(genome)
        assert len(fp) >= 1

    def test_insertion_tolerant(self) -> None:
        # Winnowing应容忍小量插入：长基因组中插入一条NOP后指纹应有重叠
        base = bytearray()
        for op in [0x01, 0x0B, 0x10, 0x12, 0x13, 0x0C, 0x0D, 0x15, 0x17, 0x0B]:
            base.extend([op, 0, 0, 0])
        # 在中间插入一条NOP
        inserted = bytearray(base[:16]) + bytearray([0x00, 0, 0, 0]) + bytearray(base[16:])
        fp_orig = compute_fingerprint(base)
        fp_ins = compute_fingerprint(inserted)
        # 长基因组中单条插入不会改变所有指纹，应有重叠
        assert len(fp_orig & fp_ins) > 0

    def test_fingerprint_deterministic(self) -> None:
        genome = bytearray([0x0B, 0, 0, 0, 0x0C, 2, 0, 0, 0x0D, 1, 0, 0,
                            0x15, 1, 0, 0, 0x17, 0, 0, 0, 0x0B, 0, 0, 0])
        results = [compute_fingerprint(genome) for _ in range(10)]
        assert all(r == results[0] for r in results)
