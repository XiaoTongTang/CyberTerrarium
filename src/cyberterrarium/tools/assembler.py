"""Assembler - compile assembly source to VM bytecode.

Syntax:
    ; comment
    LABEL:
    MNEMONIC [operands...]

Register names: R0 R1 R2 R3 INV DP_X DP_Y
Material names: EMPTY NUTRIENT ENZYME TOXIN SIGNAL

Instruction set:
    NOP
    MOV Ra, Imm
    ADD Ra, Rb
    SUB Ra, Rb
    AND Ra, Rb
    OR  Ra, Rb
    NOT Ra
    READ_REL Imm_X, Imm_Y
    READ_ABS Rx, Ry
    EAT
    MAKE MaterialID
    EMIT Imm_X, Imm_Y
    MOVE_X Rx
    MOVE_Y Ry
    CMP Ra, Rb
    JZ  Label
    JNZ Label
    JMP Label
    SPLIT
"""

from __future__ import annotations

# --- opcode table ---
OPCODES: dict[str, int] = {
    "NOP": 0x00,
    "MOV": 0x01,
    "ADD": 0x02,
    "SUB": 0x03,
    "AND": 0x04,
    "OR": 0x05,
    "NOT": 0x06,
    "READ_REL": 0x09,
    "READ_ABS": 0x0A,
    "EAT": 0x0B,
    "MAKE": 0x0C,
    "EMIT": 0x0D,
    "MOVE_X": 0x0E,
    "MOVE_Y": 0x0F,
    "CMP": 0x10,
    "JZ": 0x11,
    "JNZ": 0x12,
    "JMP": 0x13,
    "SPLIT": 0x14,
}

# --- register name -> index ---
REGISTERS: dict[str, int] = {
    "R0": 0x00,
    "R1": 0x01,
    "R2": 0x02,
    "R3": 0x03,
    "INV": 0x04,
    "DP_X": 0x05,
    "DP_Y": 0x06,
}

# --- material name -> id ---
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
    if token not in REGISTERS:
        raise AssembleError(f"Unknown register: {token}")
    return REGISTERS[token]


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


def assemble(source: str) -> bytearray:
    """Assemble source text into bytecode. Two-pass: collect labels, then encode."""
    lines = _strip_source(source)

    # Pass 1: collect labels and compute instruction addresses
    labels: dict[str, int] = {}
    instructions: list[tuple[int, str, list[str]]] = []  # (line_no, mnemonic, operands)
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
    if mnemonic not in OPCODES:
        raise AssembleError(f"Line {line_no}: Unknown mnemonic '{mnemonic}'")

    opcode = OPCODES[mnemonic]

    # 0-operand instructions
    if mnemonic in ("NOP", "EAT", "SPLIT"):
        if operands:
            raise AssembleError(f"Line {line_no}: {mnemonic} takes no operands")
        return bytes([opcode, 0, 0, 0])

    # 1-register instructions
    if mnemonic == "NOT":
        if len(operands) != 1:
            raise AssembleError(f"Line {line_no}: NOT takes 1 operand")
        return bytes([opcode, _parse_reg(operands[0]), 0, 0])

    # MOV Ra, Imm
    if mnemonic == "MOV":
        if len(operands) != 2:
            raise AssembleError(f"Line {line_no}: MOV takes 2 operands")
        return bytes([opcode, _parse_reg(operands[0]), _parse_imm(operands[1]) & 0xFF, 0])

    # 2-register instructions: ADD SUB AND OR CMP
    if mnemonic in ("ADD", "SUB", "AND", "OR", "CMP"):
        if len(operands) != 2:
            raise AssembleError(f"Line {line_no}: {mnemonic} takes 2 operands")
        return bytes([opcode, _parse_reg(operands[0]), _parse_reg(operands[1]), 0])

    # READ_REL Imm_X, Imm_Y
    if mnemonic == "READ_REL":
        if len(operands) != 2:
            raise AssembleError(f"Line {line_no}: READ_REL takes 2 operands")
        return bytes([opcode, _parse_imm(operands[0]) & 0xFF, _parse_imm(operands[1]) & 0xFF, 0])

    # READ_ABS Rx, Ry
    if mnemonic == "READ_ABS":
        if len(operands) != 2:
            raise AssembleError(f"Line {line_no}: READ_ABS takes 2 operands")
        return bytes([opcode, _parse_reg(operands[0]), _parse_reg(operands[1]), 0])

    # MAKE MaterialID
    if mnemonic == "MAKE":
        if len(operands) != 1:
            raise AssembleError(f"Line {line_no}: MAKE takes 1 operand")
        return bytes([opcode, _parse_material_or_imm(operands[0]), 0, 0])

    # EMIT Imm_X, Imm_Y
    if mnemonic == "EMIT":
        if len(operands) != 2:
            raise AssembleError(f"Line {line_no}: EMIT takes 2 operands")
        return bytes([opcode, _parse_imm(operands[0]) & 0xFF, _parse_imm(operands[1]) & 0xFF, 0])

    # MOVE_X Rx / MOVE_Y Ry
    if mnemonic in ("MOVE_X", "MOVE_Y"):
        if len(operands) != 1:
            raise AssembleError(f"Line {line_no}: {mnemonic} takes 1 operand")
        return bytes([opcode, _parse_reg(operands[0]), 0, 0])

    # Jump instructions: JZ JNZ JMP
    if mnemonic in ("JZ", "JNZ", "JMP"):
        if len(operands) != 1:
            raise AssembleError(f"Line {line_no}: {mnemonic} takes 1 operand")
        target = operands[0]
        # Try as label first, then as raw offset
        if target.upper() in labels:
            target_pc = labels[target.upper()]
            # Compute relative offset in instructions (not bytes)
            rel = (target_pc - (current_pc + 4)) // 4
        else:
            rel = _parse_imm(target)
        return bytes([opcode, _encode_jump_offset(rel), 0, 0])

    raise AssembleError(f"Line {line_no}: Unhandled mnemonic '{mnemonic}'")
