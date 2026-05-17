"""指令集架构定义 - 指令与寄存器的唯一定义源"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# ═══════════════════════════════════════════
# 寄存器描述表
# ═══════════════════════════════════════════


@dataclass(frozen=True)
class RegDef:
    name: str  # 寄存器名
    index: int  # 在 regs[] 数组中的索引
    arith_writable: bool  # 是否允许算术指令写入


REG_TABLE: list[RegDef] = [
    RegDef("R0", 0, True),
    RegDef("R1", 1, True),
    RegDef("R2", 2, True),
    RegDef("R3", 3, True),
    RegDef("INV", 4, False),
    RegDef("DP_X", 5, False),
    RegDef("DP_Y", 6, False),
]

# 派生
REG_COUNT: int = len(REG_TABLE)
REG_BY_NAME: dict[str, RegDef] = {r.name: r for r in REG_TABLE}
REG_BY_INDEX: dict[int, RegDef] = {r.index: r for r in REG_TABLE}
REG_NAMES: list[str] = [r.name for r in sorted(REG_TABLE, key=lambda r: r.index)]
ARITH_WRITABLE_MAX: int = max(r.index for r in REG_TABLE if r.arith_writable)
DATA_REG_COUNT: int = sum(1 for r in REG_TABLE if r.arith_writable)


# ═══════════════════════════════════════════
# 操作数类型
# ═══════════════════════════════════════════


class OperandType(Enum):
    NONE = "none"  # 无操作数
    REG = "reg"  # 寄存器索引
    IMM = "imm"  # 立即数
    MAT = "mat"  # 材料ID（汇编时支持名称）
    OFFSET = "offset"  # 跳转偏移（有符号）


# ═══════════════════════════════════════════
# 指令描述表
# ═══════════════════════════════════════════


@dataclass(frozen=True)
class OpcodeDef:
    opcode: int  # 操作码
    mnemonic: str  # 助记符
    p1_type: OperandType  # 第1操作数类型
    p2_type: OperandType  # 第2操作数类型
    handler_method: str  # VM中对应的处理方法名
    advances_pc: bool = True  # 是否默认推进PC（跳转指令为False）
    returns_spawn: bool = False  # 是否返回spawn_requests
    arith_target: bool = False  # p1是否为算术目标寄存器（不可写INV/DP_X/DP_Y）


OPCODE_TABLE: list[OpcodeDef] = [
    # 算术
    OpcodeDef(0x00, "NOP", OperandType.NONE, OperandType.NONE, "_op_nop"),
    OpcodeDef(0x01, "MOV", OperandType.REG, OperandType.IMM, "_op_mov", arith_target=True),
    OpcodeDef(0x02, "ADD", OperandType.REG, OperandType.REG, "_op_add", arith_target=True),
    OpcodeDef(0x03, "SUB", OperandType.REG, OperandType.REG, "_op_sub", arith_target=True),
    OpcodeDef(0x04, "AND", OperandType.REG, OperandType.REG, "_op_and", arith_target=True),
    OpcodeDef(0x05, "OR", OperandType.REG, OperandType.REG, "_op_or", arith_target=True),
    OpcodeDef(0x06, "NOT", OperandType.REG, OperandType.NONE, "_op_not", arith_target=True),
    # 传感
    OpcodeDef(0x09, "READ_REL", OperandType.IMM, OperandType.IMM, "_op_read_rel"),
    OpcodeDef(0x0A, "READ_ABS", OperandType.REG, OperandType.REG, "_op_read_abs"),
    # 代谢
    OpcodeDef(0x0B, "EAT", OperandType.NONE, OperandType.NONE, "_op_eat"),
    OpcodeDef(0x0C, "MAKE", OperandType.MAT, OperandType.NONE, "_op_make"),
    OpcodeDef(0x0D, "EMIT", OperandType.IMM, OperandType.IMM, "_op_emit"),
    # 运动
    OpcodeDef(0x0E, "MOVE_X", OperandType.REG, OperandType.NONE, "_op_move_x"),
    OpcodeDef(0x0F, "MOVE_Y", OperandType.REG, OperandType.NONE, "_op_move_y"),
    # 控制
    OpcodeDef(0x10, "CMP", OperandType.REG, OperandType.REG, "_op_cmp"),
    OpcodeDef(0x11, "JZ", OperandType.OFFSET, OperandType.NONE, "_op_jz", advances_pc=False),
    OpcodeDef(0x12, "JNZ", OperandType.OFFSET, OperandType.NONE, "_op_jnz", advances_pc=False),
    OpcodeDef(0x13, "JMP", OperandType.OFFSET, OperandType.NONE, "_op_jmp", advances_pc=False),
    # 废弃
    OpcodeDef(0x14, "SPLIT", OperandType.NONE, OperandType.NONE, "_op_split"),
    # 位图映射
    OpcodeDef(0x15, "MOVE_BMAP", OperandType.REG, OperandType.NONE, "_op_move_bmap"),
    OpcodeDef(0x16, "ATTACK_BMAP", OperandType.REG, OperandType.NONE, "_op_attack_bmap"),
    OpcodeDef(
        0x17, "SCAN_NUT", OperandType.REG, OperandType.NONE, "_op_scan_nut", arith_target=True),
    OpcodeDef(
        0x18, "SCAN_TOX", OperandType.REG, OperandType.NONE, "_op_scan_tox", arith_target=True),
    OpcodeDef(
        0x19, "SCAN_EMP", OperandType.REG, OperandType.NONE, "_op_scan_emp", arith_target=True),
    OpcodeDef(0x1A, "EMIT_BMAP", OperandType.REG, OperandType.MAT, "_op_emit_bmap"),
]

# 派生
OPCODE_BY_CODE: dict[int, OpcodeDef] = {op.opcode: op for op in OPCODE_TABLE}
OPCODE_BY_NAME: dict[str, OpcodeDef] = {op.mnemonic: op for op in OPCODE_TABLE}
MNEMONIC_BY_CODE: dict[int, str] = {op.opcode: op.mnemonic for op in OPCODE_TABLE}
PC_ADVANCE_EXEMPT: set[int] = {op.opcode for op in OPCODE_TABLE if not op.advances_pc}
LEGAL_OPCODES: list[int] = sorted(OPCODE_BY_CODE.keys())
