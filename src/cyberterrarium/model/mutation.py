"""突变引擎 - 基因变异逻辑 + 指令归一化"""

import random

from cyberterrarium.model.config import (
    MAX_GENOME_LENGTH,
    MIN_GENOME_LENGTH,
    MUTATION_ENABLED,
    POINT_MUTATION_RATE,
    STRUCT_DELETION_RATE,
    STRUCT_INSERTION_RATE,
)
from cyberterrarium.model.isa import (
    DATA_REG_COUNT,
    LEGAL_OPCODES,
    OPCODE_BY_CODE,
    REG_COUNT,
    OperandType,
)


def _normalize_operand(
    value: int, op_type: OperandType, is_arith_target: bool
) -> int:
    """归一化单个操作数。"""
    if op_type == OperandType.REG:
        if is_arith_target:
            return value % DATA_REG_COUNT  # 映射到 R0~R3
        return value % REG_COUNT
    if op_type == OperandType.MAT:
        if value < 1 or value > 4:
            return ((value - 1) % 4) + 1
        return value
    # NONE / IMM / OFFSET — 无需归一化
    return value


def _normalize_instruction(opcode: int, p1: int, p2: int) -> tuple[int, int, int]:
    """将一条指令归一化为合法的 opcode + 操作数组合。"""
    # Opcode 归一化
    if opcode not in OPCODE_BY_CODE:
        opcode = LEGAL_OPCODES[opcode % len(LEGAL_OPCODES)]

    opdef = OPCODE_BY_CODE[opcode]

    # 操作数归一化
    p1 = _normalize_operand(p1, opdef.p1_type, opdef.arith_target)
    p2 = _normalize_operand(p2, opdef.p2_type, False)

    return opcode, p1, p2


def apply_mutations(genome: bytearray) -> bytearray:
    """对子代基因组施加突变（点突变 + 结构突变 + 归一化）。"""
    if not MUTATION_ENABLED:
        return genome

    child = bytearray(genome)

    # 点突变：按指令遍历
    for i in range(0, len(child), 4):
        if random.random() < POINT_MUTATION_RATE:
            byte_idx = i + random.randint(0, 3)
            bit_idx = random.randint(0, 7)
            child[byte_idx] ^= 1 << bit_idx
            # 归一化受影响的指令
            op, p1, p2 = child[i], child[i + 1], child[i + 2]
            op, p1, p2 = _normalize_instruction(op, p1, p2)
            child[i], child[i + 1], child[i + 2] = op, p1, p2

    # 结构突变：按整个基因组计算概率
    r = random.random()
    if r < STRUCT_INSERTION_RATE:
        # 片段插入
        if len(child) + 4 <= MAX_GENOME_LENGTH:
            pos = random.randrange(0, max(len(child) // 4, 1)) * 4
            child[pos:pos] = child[pos : pos + 4]
    elif r < STRUCT_INSERTION_RATE + STRUCT_DELETION_RATE and len(child) - 4 >= MIN_GENOME_LENGTH:
        pos = random.randrange(0, max(len(child) // 4, 1)) * 4
        del child[pos : pos + 4]

    # 边界截断
    if len(child) > MAX_GENOME_LENGTH:
        child = child[:MAX_GENOME_LENGTH]
    if len(child) < MIN_GENOME_LENGTH:
        return bytearray(genome)  # 死胎，返回原始

    return child
