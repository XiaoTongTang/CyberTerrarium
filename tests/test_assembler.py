"""Assembler and disassembler tests."""

from cyberterrarium.tools.assembler import AssembleError, assemble
from cyberterrarium.tools.disassembler import disassemble, disassemble_with_labels


class TestAssembler:
    def test_nop(self) -> None:
        code = assemble("NOP")
        assert code == bytearray([0x00, 0x00, 0x00, 0x00])

    def test_mov(self) -> None:
        code = assemble("MOV R0, 10")
        assert code == bytearray([0x01, 0x00, 0x0A, 0x00])

    def test_add(self) -> None:
        code = assemble("ADD R1, R2")
        assert code == bytearray([0x02, 0x01, 0x02, 0x00])

    def test_not(self) -> None:
        code = assemble("NOT R3")
        assert code == bytearray([0x06, 0x03, 0x00, 0x00])

    def test_read_rel(self) -> None:
        code = assemble("READ_REL 1, -1")
        assert code == bytearray([0x09, 0x01, 0xFF, 0x00])

    def test_eat(self) -> None:
        code = assemble("EAT")
        assert code == bytearray([0x0B, 0x00, 0x00, 0x00])

    def test_make_material_name(self) -> None:
        code = assemble("MAKE ENZYME")
        assert code == bytearray([0x0C, 0x02, 0x00, 0x00])

    def test_make_immediate(self) -> None:
        code = assemble("MAKE 3")
        assert code == bytearray([0x0C, 0x03, 0x00, 0x00])

    def test_emit(self) -> None:
        code = assemble("EMIT 0, 1")
        assert code == bytearray([0x0D, 0x00, 0x01, 0x00])

    def test_move_x(self) -> None:
        code = assemble("MOVE_X R0")
        assert code == bytearray([0x0E, 0x00, 0x00, 0x00])

    def test_cmp(self) -> None:
        code = assemble("CMP R0, R1")
        assert code == bytearray([0x10, 0x00, 0x01, 0x00])

    def test_split(self) -> None:
        code = assemble("SPLIT")
        assert code == bytearray([0x14, 0x00, 0x00, 0x00])

    def test_label_and_jump(self) -> None:
        source = "\n".join([
            "LOOP:",
            "    MOV R0, 1",
            "    CMP R0, R1",
            "    JNZ LOOP",
        ])
        code = assemble(source)
        # LOOP is at PC=0, JNZ at PC=8, target=0, rel=(0-12)//4=-3
        assert code[0:4] == bytearray([0x01, 0x00, 0x01, 0x00])  # MOV
        assert code[4:8] == bytearray([0x10, 0x00, 0x01, 0x00])  # CMP
        assert code[8:12] == bytearray([0x12, 0xFD, 0x00, 0x00])  # JNZ -3

    def test_comment_and_blank_lines(self) -> None:
        source = "; this is a comment\n\n  NOP  ; inline\n"
        code = assemble(source)
        assert code == bytearray([0x00, 0x00, 0x00, 0x00])

    def test_unknown_mnemonic_raises(self) -> None:
        raised = False
        try:
            assemble("FOO R0")
        except AssembleError:
            raised = True
        assert raised

    def test_multiple_instructions(self) -> None:
        source = "MOV R0, 0\nREAD_REL 0, 0\nEAT"
        code = assemble(source)
        assert len(code) == 12
        assert code[0:4] == bytearray([0x01, 0x00, 0x00, 0x00])
        assert code[4:8] == bytearray([0x09, 0x00, 0x00, 0x00])
        assert code[8:12] == bytearray([0x0B, 0x00, 0x00, 0x00])

    def test_hex_immediate(self) -> None:
        code = assemble("MOV R0, 0xFF")
        assert code == bytearray([0x01, 0x00, 0xFF, 0x00])


class TestDisassembler:
    def test_nop(self) -> None:
        genome = bytearray([0x00, 0x00, 0x00, 0x00])
        lines = disassemble(genome)
        assert len(lines) == 1
        assert "NOP" in lines[0]

    def test_mov(self) -> None:
        genome = bytearray([0x01, 0x00, 0x0A, 0x00])
        lines = disassemble(genome)
        assert "MOV" in lines[0]
        assert "R0" in lines[0]

    def test_make_material_name(self) -> None:
        genome = bytearray([0x0C, 0x02, 0x00, 0x00])
        lines = disassemble(genome)
        assert "MAKE" in lines[0]
        assert "ENZYME" in lines[0]

    def test_roundtrip(self) -> None:
        """Assemble then disassemble should produce consistent output."""
        source = "MOV R0, 10\nADD R0, R1\nEAT\nSPLIT"
        code = assemble(source)
        lines = disassemble(code)
        assert len(lines) == 4
        assert "MOV" in lines[0]
        assert "ADD" in lines[1]
        assert "EAT" in lines[2]
        assert "SPLIT" in lines[3]

    def test_with_labels(self) -> None:
        genome = bytearray([
            0x01, 0x00, 0x01, 0x00,  # MOV R0, 1
            0x10, 0x00, 0x01, 0x00,  # CMP R0, R1
            0x12, 0xFD, 0x00, 0x00,  # JNZ -3
        ])
        lines = disassemble_with_labels(genome)
        # Should contain a label at PC=0 and a jump to it
        assert any(line.startswith("L") and line.endswith(":") for line in lines)
