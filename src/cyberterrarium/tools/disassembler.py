"""Disassembler - decode VM bytecode into human-readable assembly."""

from __future__ import annotations

from cyberterrarium.model.isa import (
    OPCODE_BY_CODE,
    REG_BY_INDEX,
    OperandType,
)
from cyberterrarium.tools.assembler import MATERIALS

# Material reverse lookup
_MAT_NAME: dict[int, str] = {v: k for k, v in MATERIALS.items()}

# Jump opcode set for label detection
_JUMP_OPCODES: set[int] = {
    op.opcode for op in OPCODE_BY_CODE.values()
    if op.p1_type == OperandType.OFFSET
}


def _format_operand(value: int, op_type: OperandType) -> str:
    """根据操作数类型格式化单个操作数。"""
    if op_type == OperandType.REG:
        reg = REG_BY_INDEX.get(value)
        return reg.name if reg is not None else f"R?{value}"
    if op_type == OperandType.MAT:
        return _MAT_NAME.get(value, str(value))
    if op_type == OperandType.OFFSET:
        signed = value if value < 128 else value - 256
        return f"{signed:+d}"
    # IMM
    return str(value)


def disassemble(genome: bytearray | bytes, base_offset: int = 0) -> list[str]:
    """Disassemble a genome into a list of assembly strings, one per instruction."""
    lines: list[str] = []
    for i in range(0, len(genome) - 3, 4):
        pc = base_offset + i
        bytecode = genome[i : i + 4]
        line = _decode_instruction(pc, bytecode[0], bytecode[1], bytecode[2], bytecode[3])
        lines.append(line)
    # Handle trailing bytes
    remainder = len(genome) % 4
    if remainder:
        trailing = genome[len(genome) - remainder :]
        hex_bytes = " ".join(f"0x{b:02X}" for b in trailing)
        lines.append(f"0x{len(genome) - remainder:04X}: DB {hex_bytes}")
    return lines


def disassemble_with_labels(genome: bytearray | bytes) -> list[str]:
    """Disassemble with auto-generated jump labels."""
    # First pass: find jump targets
    targets: set[int] = set()
    for i in range(0, len(genome) - 3, 4):
        opcode = genome[i]
        if opcode in _JUMP_OPCODES:
            offset = genome[i + 1]
            if offset >= 128:
                offset -= 256
            target_pc = (i + 4) + offset * 4
            if 0 <= target_pc < len(genome):
                targets.add(target_pc)

    label_map: dict[int, str] = {}
    for idx, t in enumerate(sorted(targets), start=1):
        label_map[t] = f"L{idx}"

    # Second pass: generate lines with labels
    lines: list[str] = []
    for i in range(0, len(genome) - 3, 4):
        if i in label_map:
            lines.append(f"{label_map[i]}:")
        bytecode = genome[i : i + 4]
        line = _decode_instruction_labeled(i, bytecode, label_map)
        lines.append(line)

    return lines


def _decode_instruction(pc: int, opcode: int, p1: int, p2: int, p3: int) -> str:
    opdef = OPCODE_BY_CODE.get(opcode)
    if opdef is None:
        return f"0x{pc:04X}: DB 0x{opcode:02X} 0x{p1:02X} 0x{p2:02X} 0x{p3:02X}"

    parts = [opdef.mnemonic]
    if opdef.p1_type != OperandType.NONE:
        parts.append(_format_operand(p1, opdef.p1_type))
    if opdef.p2_type != OperandType.NONE:
        parts.append(_format_operand(p2, opdef.p2_type))
    if opdef.p3_type != OperandType.NONE:
        parts.append(_format_operand(p3, opdef.p3_type))
    return f"0x{pc:04X}: " + " ".join(parts)


def _decode_instruction_labeled(
    pc: int, bytecode: bytes, label_map: dict[int, str]
) -> str:
    opcode = bytecode[0]
    p1 = bytecode[1]
    p2 = bytecode[2]
    opdef = OPCODE_BY_CODE.get(opcode)

    indent = "    "

    if opdef is None:
        return f"{indent}DB 0x{opcode:02X} 0x{p1:02X} 0x{p2:02X} 0x{bytecode[3]:02X}"

    parts = [opdef.mnemonic]

    # 跳转指令：优先显示标签
    if opdef.p1_type == OperandType.OFFSET:
        offset = p1 if p1 < 128 else p1 - 256
        target_pc = pc + 4 + offset * 4
        if target_pc in label_map:
            parts.append(label_map[target_pc])
        else:
            parts.append(f"{offset:+d}")
    else:
        if opdef.p1_type != OperandType.NONE:
            parts.append(_format_operand(p1, opdef.p1_type))
        if opdef.p2_type != OperandType.NONE:
            parts.append(_format_operand(p2, opdef.p2_type))
        if opdef.p3_type != OperandType.NONE:
            parts.append(_format_operand(bytecode[3], opdef.p3_type))

    return f"{indent}" + " ".join(parts)
