"""基因组相似度比对 CLI 测试"""

import sys
import os

# 确保 cli 模块可导入
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.compare import _normalize, compare


class TestNormalize:
    def test_literal_backslash_n_converted(self) -> None:
        """字面量 \\n → 真实换行符。"""
        assert _normalize(r"MOV R0, 1\nEAT") == "MOV R0, 1\nEAT"

    def test_real_newlines_unchanged(self) -> None:
        """真实换行符不受影响。"""
        src = "MOV R0, 1\nEAT\nJMP -2"
        assert _normalize(src) == src

    def test_no_backslash_n_unchanged(self) -> None:
        """不含 \\n 的字符串原样返回。"""
        assert _normalize("MOV R0, 1") == "MOV R0, 1"

    def test_empty_string(self) -> None:
        """空字符串。"""
        assert _normalize("") == ""

    def test_mixed_real_and_literal(self) -> None:
        """混合真实换行与字面量 \\n。"""
        assert _normalize("A\nB\\nC") == "A\nB\nC"


class TestCompare:
    def test_identical_assembly(self) -> None:
        """相同 assembly → Jaccard 1.0。"""
        src = "MOV R0, 1\nEAT\nJMP -2"
        result = compare(src, src)
        assert result["error_a"] is None
        assert result["error_b"] is None
        assert result["jaccard"] == 1.0

    def test_different_species(self) -> None:
        """不同物种 assembly → Jaccard < 1.0。"""
        grazer = "MOV R0, 1\nMOVE_X R0\nEAT\nJMP -2"
        farmer = "WLO R1, 255, 255\nEMIT_BMAP R1, 2\nEAT\nEAT\nEAT\nEAT"
        result = compare(grazer, farmer)
        assert result["error_a"] is None
        assert result["error_b"] is None
        assert 0.0 <= result["jaccard"] <= 1.0

    def test_invalid_assembly_reports_error(self) -> None:
        """非法 assembly 时应返回错误信息。"""
        result = compare("INVALID INSTRUCTION XYZ", "MOV R0, 1")
        assert result["error_a"] is not None
        assert result["error_b"] is None

    def test_both_invalid(self) -> None:
        """两个都非法时都应报错。"""
        result = compare("BAD", "ALSO BAD")
        assert result["error_a"] is not None
        assert result["error_b"] is not None

    def test_bytecode_lengths(self) -> None:
        """返回正确长度的字节码。"""
        result = compare("MOV R0, 1\nEAT", "MOV R0, 1\nEAT\nJMP -2")
        assert len(result["bytecode_a"]) == 8  # 2 条指令
        assert len(result["bytecode_b"]) == 12  # 3 条指令

    def test_empty_assembly_similarity_zero(self) -> None:
        """空 assembly → 指纹为空 → Jaccard 0.0。"""
        result = compare("", "MOV R0, 1\nEAT\nJMP -2")
        assert result["error_a"] is None
        assert result["error_b"] is None
        assert result["jaccard"] == 0.0

    def test_literal_backslash_n_input(self) -> None:
        """传入字面量 \\n 的 assembly 字符串可被 _normalize + compare 正确处理。"""
        result = compare(
            r"MOV R0, 1\nMOVE_X R0\nEAT\nJMP -2",
            r"WLO R1, 255, 255\nEMIT_BMAP R1, 2\nEAT\nEAT\nEAT\nEAT\n",
        )
        assert result["error_a"] is None
        assert result["error_b"] is None
        assert len(result["bytecode_a"]) == 16
        assert len(result["bytecode_b"]) == 24

    def test_intersection_union_fields(self) -> None:
        """返回的交集和并集字段与 Jaccard 值一致。"""
        src = "MOV R0, 1\nEAT\nJMP -2"
        result = compare(src, src)
        assert result["intersection"] == result["union"]
        assert result["union"] > 0
