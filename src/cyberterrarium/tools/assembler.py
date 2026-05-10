"""Assembler - compile assembly source to VM bytecode.

Syntax:
    ; comment
    LABEL:
    MNEMONIC [operands...]

Register names: R0 R1 R2 R3 INV DP_X DP_Y
Material names: EMPTY NUTRIENT ENZYME TOXIN SIGNAL

Instruction set is defined in isa.py — this module reads OPCODE_TABLE / REG_TABLE.
"""

from __future__ import annotations

from cyberterrarium.model.isa import (
    OPCODE_BY_NAME,
    REG_BY_NAME,
    OperandType,
)

# Material name -> id
MATERIALS: dict[str, int] = {
    "EMPTY": 0,
    "NUTRIENT": 1,
    "ENZYME": 2,
    "TOXIN": 3,
    "SIGNAL": 4,
}


class AssembleError(Exception):
    pass


def _parse_reg(token: str) -> int:
    token = token.upper()
    if token not in REG_BY_NAME:
        raise AssembleError(f"Unknown register: {token}")
    return REG_BY_NAME[token].index


def _parse_imm(token: str) -> int:
    try:
        return int(token, 0)
    except ValueError:
        raise AssembleError(f"Invalid immediate value: {token}") from None


def _parse_material_or_imm(token: str) -> int:
    upper = token.upper()
    if upper in MATERIALS:
        return MATERIALS[upper]
    return _parse_imm(token)


def _encode_jump_offset(offset: int) -> int:
    if not (-128 <= offset <= 127):
        raise AssembleError(f"Jump offset out of range (-128..127): {offset}")
    return offset if offset >= 0 else offset + 256


def _parse_operand(token: str, op_type: OperandType) -> int:
    """根据操作数类型解析单个操作数。"""
    if op_type == OperandType.NONE:
        return 0
    if op_type == OperandType.REG:
        return _parse_reg(token)
    if op_type in (OperandType.IMM, OperandType.OFFSET):
        return _parse_imm(token) & 0xFF
    if op_type == OperandType.MAT:
        return _parse_material_or_imm(token) & 0xFF
    raise AssembleError(f"Unsupported operand type: {op_type}")


def _expected_operand_count(opdef) -> int:
    """计算期望的操作数数量。"""
    count = 0
    if opdef.p1_type != OperandType.NONE:
        count += 1
    if opdef.p2_type != OperandType.NONE:
        count += 1
    return count


def assemble(source: str) -> bytearray:
    """Assemble source text into bytecode. Two-pass: collect labels, then encode."""
    lines = _strip_source(source)

    # Pass 1: collect labels and compute instruction addresses
    labels: dict[str, int] = {}
    instructions: list[tuple[int, str, list[str]]] = []
    pc = 0
    for line_no, text in lines:
        if text.endswith(":"):
            label = text[:-1].strip()
            if label in labels:
                raise AssembleError(f"Line {line_no}: Duplicate label '{label}'")
            labels[label] = pc
        else:
            parts = text.replace(",", " ").split()
            mnemonic = parts[0].upper()
            operands = parts[1:]
            instructions.append((line_no, mnemonic, operands))
            pc += 4

    # Pass 2: encode each instruction
    result = bytearray()
    for idx, (line_no, mnemonic, operands) in enumerate(instructions):
        current_pc = idx * 4
        inst = _encode_instruction(line_no, mnemonic, operands, current_pc, labels)
        result.extend(inst)

    return result


def _strip_source(source: str) -> list[tuple[int, str]]:
    """Return (line_number, stripped_text) for non-empty, non-comment lines."""
    result: list[tuple[int, str]] = []
    for i, raw_line in enumerate(source.splitlines(), start=1):
        line = raw_line.split(";")[0].strip()
        if line:
            result.append((i, line))
    return result


def _encode_instruction(
    line_no: int,
    mnemonic: str,
    operands: list[str],
    current_pc: int,
    labels: dict[str, int],
) -> bytes:
    opdef = OPCODE_BY_NAME.get(mnemonic)
    if opdef is None:
        raise AssembleError(f"Line {line_no}: Unknown mnemonic '{mnemonic}'")

    expected = _expected_operand_count(opdef)
    if len(operands) != expected:
        raise AssembleError(
            f"Line {line_no}: {mnemonic} takes {expected} operand(s), got {len(operands)}"
        )

    opcode = opdef.opcode

    # 解析p1
    if opdef.p1_type == OperandType.OFFSET:
        # 跳转偏移：先尝试标签，再尝试原始偏移
        target = operands[0]
        if target.upper() in labels:
            target_pc = labels[target.upper()]
            rel = (target_pc - (current_pc + 4)) // 4
        else:
            rel = _parse_imm(target)
        p1 = _encode_jump_offset(rel)
    else:
        p1 = _parse_operand(operands[0], opdef.p1_type) if operands else 0

    # 解析p2
    if opdef.p2_type != OperandType.NONE and len(operands) >= 2:
        p2 = _parse_operand(operands[1], opdef.p2_type)
    else:
        p2 = 0

    return bytes([opcode, p1, p2, 0])
