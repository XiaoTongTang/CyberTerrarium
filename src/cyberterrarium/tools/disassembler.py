"""Disassembler - decode VM bytecode into human-readable assembly."""

from __future__ import annotations

from cyberterrarium.tools.assembler import MATERIALS, OPCODES, REGISTERS

# Reverse lookup tables
_OPCODE_NAME: dict[int, str] = {v: k for k, v in OPCODES.items()}
_REG_NAME: dict[int, str] = {v: k for k, v in REGISTERS.items()}
_MAT_NAME: dict[int, str] = {v: k for k, v in MATERIALS.items()}


def disassemble(genome: bytearray | bytes, base_offset: int = 0) -> list[str]:
    """Disassemble a genome into a list of assembly strings, one per instruction."""
    lines: list[str] = []
    for i in range(0, len(genome) - 3, 4):
        pc = base_offset + i
        bytecode = genome[i : i + 4]
        line = _decode_instruction(pc, bytecode[0], bytecode[1], bytecode[2], bytecode[3])
        lines.append(line)
    # Handle trailing bytes that don't form a complete instruction
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
        if opcode in (0x11, 0x12, 0x13):  # JZ JNZ JMP
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
    name = _OPCODE_NAME.get(opcode, f"0x{opcode:02X}")

    if opcode in (0x00, 0x0B, 0x14):  # NOP EAT SPLIT
        return f"0x{pc:04X}: {name}"

    if opcode == 0x06:  # NOT
        return f"0x{pc:04X}: {name} {_reg(p1)}"

    if opcode == 0x01:  # MOV
        return f"0x{pc:04X}: {name} {_reg(p1)}, {p2}"

    if opcode in (0x02, 0x03, 0x04, 0x05, 0x10):  # ADD SUB AND OR CMP
        return f"0x{pc:04X}: {name} {_reg(p1)}, {_reg(p2)}"

    if opcode == 0x09:  # READ_REL
        return f"0x{pc:04X}: {name} {p1}, {p2}"

    if opcode == 0x0A:  # READ_ABS
        return f"0x{pc:04X}: {name} {_reg(p1)}, {_reg(p2)}"

    if opcode == 0x0C:  # MAKE
        return f"0x{pc:04X}: {name} {_mat(p1)}"

    if opcode == 0x0D:  # EMIT
        return f"0x{pc:04X}: {name} {p1}, {p2}"

    if opcode in (0x0E, 0x0F):  # MOVE_X MOVE_Y
        return f"0x{pc:04X}: {name} {_reg(p1)}"

    if opcode in (0x11, 0x12, 0x13):  # JZ JNZ JMP
        offset = p1 if p1 < 128 else p1 - 256
        return f"0x{pc:04X}: {name} {offset:+d}"

    # Unknown opcode
    return f"0x{pc:04X}: DB 0x{opcode:02X} 0x{p1:02X} 0x{p2:02X} 0x{p3:02X}"


def _decode_instruction_labeled(
    pc: int, bytecode: bytes, label_map: dict[int, str]
) -> str:
    opcode = bytecode[0]
    p1 = bytecode[1]
    p2 = bytecode[2]
    p3 = bytecode[3]
    name = _OPCODE_NAME.get(opcode, f"0x{opcode:02X}")

    indent = "    "

    if opcode in (0x00, 0x0B, 0x14):
        return f"{indent}{name}"

    if opcode == 0x06:
        return f"{indent}{name} {_reg(p1)}"

    if opcode == 0x01:
        return f"{indent}{name} {_reg(p1)}, {p2}"

    if opcode in (0x02, 0x03, 0x04, 0x05, 0x10):
        return f"{indent}{name} {_reg(p1)}, {_reg(p2)}"

    if opcode == 0x09:
        return f"{indent}{name} {p1}, {p2}"

    if opcode == 0x0A:
        return f"{indent}{name} {_reg(p1)}, {_reg(p2)}"

    if opcode == 0x0C:
        return f"{indent}{name} {_mat(p1)}"

    if opcode == 0x0D:
        return f"{indent}{name} {p1}, {p2}"

    if opcode in (0x0E, 0x0F):
        return f"{indent}{name} {_reg(p1)}"

    if opcode in (0x11, 0x12, 0x13):
        offset = p1 if p1 < 128 else p1 - 256
        target_pc = pc + 4 + offset * 4
        if target_pc in label_map:
            return f"{indent}{name} {label_map[target_pc]}"
        return f"{indent}{name} {offset:+d}"

    return f"{indent}DB 0x{opcode:02X} 0x{p1:02X} 0x{p2:02X} 0x{p3:02X}"


def _reg(idx: int) -> str:
    return _REG_NAME.get(idx, f"R?{idx}")


def _mat(idx: int) -> str:
    return _MAT_NAME.get(idx, str(idx))
