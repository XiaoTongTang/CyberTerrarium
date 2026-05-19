"""突变引擎测试 - 归一化逻辑 + 基础功能"""

from cyberterrarium.model import mutation
from cyberterrarium.model.isa import (
    DATA_REG_COUNT,
    LEGAL_OPCODES,
    OPCODE_BY_CODE,
    REG_COUNT,
    OperandType,
)
from cyberterrarium.model.mutation import (
    _normalize_instruction,
    _normalize_operand,
    apply_mutations,
)


def test_no_mutation_when_disabled() -> None:
    original = mutation.MUTATION_ENABLED
    mutation.MUTATION_ENABLED = False
    try:
        genome = bytearray([0x00, 0x00, 0x00, 0x00] * 4)
        result = apply_mutations(genome)
        assert result == genome
    finally:
        mutation.MUTATION_ENABLED = original


# ── Opcode 归一化 ──


class TestNormalizeOpcode:
    def test_legal_opcode_unchanged(self) -> None:
        for opcode in LEGAL_OPCODES:
            op, _, _, _ = _normalize_instruction(opcode, 0, 0, 0)
            assert op == opcode

    def test_illegal_opcode_mapped_to_legal(self) -> None:
        for opcode in range(256):
            op, _, _, _ = _normalize_instruction(opcode, 0, 0, 0)
            assert op in OPCODE_BY_CODE

    def test_gap_0x07_maps_to_legal(self) -> None:
        op, _, _, _ = _normalize_instruction(0x07, 0, 0, 0)
        assert op == LEGAL_OPCODES[0x07 % len(LEGAL_OPCODES)]

    def test_gap_0x08_maps_to_legal(self) -> None:
        op, _, _, _ = _normalize_instruction(0x08, 0, 0, 0)
        assert op == LEGAL_OPCODES[0x08 % len(LEGAL_OPCODES)]

    def test_0xff_maps_to_legal(self) -> None:
        op, _, _, _ = _normalize_instruction(0xFF, 0, 0, 0)
        assert op == LEGAL_OPCODES[0xFF % len(LEGAL_OPCODES)]


# ── REG 操作数归一化 ──


class TestNormalizeReg:
    def test_legal_reg_unchanged(self) -> None:
        for i in range(REG_COUNT):
            result = _normalize_operand(i, OperandType.REG, is_arith_target=False)
            assert result == i

    def test_out_of_range_reg_wraps(self) -> None:
        for v in range(REG_COUNT, 256):
            result = _normalize_operand(v, OperandType.REG, is_arith_target=False)
            assert result == v % REG_COUNT

    def test_arith_target_maps_to_data_reg(self) -> None:
        for v in range(256):
            result = _normalize_operand(v, OperandType.REG, is_arith_target=True)
            assert 0 <= result < DATA_REG_COUNT

    def test_arith_target_cannot_write_inv(self) -> None:
        result = _normalize_operand(4, OperandType.REG, is_arith_target=True)
        assert result != 4  # INV index=4, must be redirected

    def test_arith_target_cannot_write_dp_x(self) -> None:
        result = _normalize_operand(5, OperandType.REG, is_arith_target=True)
        assert result != 5

    def test_arith_target_cannot_write_dp_y(self) -> None:
        result = _normalize_operand(6, OperandType.REG, is_arith_target=True)
        assert result != 6

    def test_arith_target_uniform_distribution(self) -> None:
        counts = [0] * DATA_REG_COUNT
        for v in range(256):
            r = _normalize_operand(v, OperandType.REG, is_arith_target=True)
            counts[r] += 1
        for count in counts:
            assert count == 64  # 256 / 4 = 64 exactly


# ── MAT 操作数归一化 ──


class TestNormalizeMat:
    def test_legal_mat_unchanged(self) -> None:
        for v in [1, 2, 3, 4]:
            result = _normalize_operand(v, OperandType.MAT, is_arith_target=False)
            assert result == v

    def test_zero_maps_to_valid(self) -> None:
        result = _normalize_operand(0, OperandType.MAT, is_arith_target=False)
        assert 1 <= result <= 4

    def test_out_of_range_maps_to_valid(self) -> None:
        for v in [5, 6, 7, 250, 255]:
            result = _normalize_operand(v, OperandType.MAT, is_arith_target=False)
            assert 1 <= result <= 4

    def test_mat_always_in_1_to_4(self) -> None:
        for v in range(256):
            result = _normalize_operand(v, OperandType.MAT, is_arith_target=False)
            assert 1 <= result <= 4


# ── IMM / OFFSET / NONE 不归一化 ──


class TestNormalizePassthrough:
    def test_imm_not_normalized(self) -> None:
        for v in [0, 1, 127, 200, 255]:
            assert _normalize_operand(v, OperandType.IMM, False) == v

    def test_offset_not_normalized(self) -> None:
        for v in [0, 1, 127, 200, 255]:
            assert _normalize_operand(v, OperandType.OFFSET, False) == v

    def test_none_not_normalized(self) -> None:
        for v in [0, 42, 255]:
            assert _normalize_operand(v, OperandType.NONE, False) == v


# ── 指令级归一化集成 ──


class TestNormalizeInstruction:
    def test_legal_instruction_unchanged(self) -> None:
        # NOP: opcode=0x00, p1=0(NONE), p2=0(NONE), p3=0(NONE)
        op, p1, p2, p3 = _normalize_instruction(0x00, 0, 0, 0)
        assert (op, p1, p2, p3) == (0x00, 0, 0, 0)

    def test_mov_with_legal_operands(self) -> None:
        # MOV R1, 42 → opcode=0x01, p1=1, p2=42
        op, p1, p2, _ = _normalize_instruction(0x01, 1, 42, 0)
        assert (op, p1, p2) == (0x01, 1, 42)

    def test_mov_arith_target_inv_redirected(self) -> None:
        # MOV INV, 99 → p1=4 should be redirected to R0
        op, p1, p2, _ = _normalize_instruction(0x01, 4, 99, 0)
        assert op == 0x01
        assert p1 == 0  # INV(4) % DATA_REG_COUNT(4) = 0 → R0
        assert p2 == 99

    def test_add_arith_target_dp_x_redirected(self) -> None:
        # ADD DP_X, R0 → p1=5 should be redirected
        op, p1, p2, _ = _normalize_instruction(0x02, 5, 0, 0)
        assert op == 0x02
        assert p1 == 1  # DP_X(5) % 4 = 1 → R1

    def test_read_rel_source_reg_not_redirected(self) -> None:
        # READ_REL is not arith_target, so p1=IMM, p2=IMM
        op, p1, p2, _ = _normalize_instruction(0x09, 3, 255, 0)
        assert (op, p1, p2) == (0x09, 3, 255)

    def test_make_mat_operand_normalized(self) -> None:
        # MAKE with mat=0 should be normalized to valid range
        op, p1, p2, _ = _normalize_instruction(0x0C, 0, 0, 0)
        assert op == 0x0C
        assert 1 <= p1 <= 4

    def test_illegal_opcode_with_bad_operands(self) -> None:
        # Opcode 0x07 (gap) + arith target reg=6(DP_Y)
        op, p1, p2, _ = _normalize_instruction(0x07, 6, 0, 0)
        assert op in OPCODE_BY_CODE
        # After opcode normalization, check if the new opcode is arith_target
        opdef = OPCODE_BY_CODE[op]
        if opdef.arith_target:
            assert p1 < DATA_REG_COUNT

    def test_wlo_p3_normalized_as_imm(self) -> None:
        # WLO: p1=REG, p2=IMM, p3=IMM — p3 should pass through
        op, p1, p2, p3 = _normalize_instruction(0x1B, 0, 0x12, 0x34)
        assert op == 0x1B
        assert p1 == 0  # R0
        assert p2 == 0x12
        assert p3 == 0x34
