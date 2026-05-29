"""基因组相似度比对 CLI — 基于 Winnowing 指纹 + Jaccard 相似度"""

import argparse
import sys

from cyberterrarium.model.fingerprint import compute_fingerprint, jaccard_similarity
from cyberterrarium.tools.assembler import assemble


def _format_fingerprint(fp: set[int], limit: int = 20) -> str:
    """格式化指纹集合用于显示（截断过长的集合）。"""
    items = sorted(fp)
    if len(items) <= limit:
        return str(items)
    return str(items[:limit])[:-1] + f", ... ({len(items)} hashes total)]"


def _normalize(source: str) -> str:
    """将字面量 \\n 转为真正的换行符。

    兼容 bash/cmd 等 shell 不展开转义序列的场景。
    assembly 语法中不存在字面量 \\n，不会误伤合法输入。
    """
    return source.replace("\\n", "\n")


def compare(raw_a: str, raw_b: str) -> dict:
    """比对两个 assembly 字符串的基因相似度。

    Returns:
        dict with keys: jaccard, fp_a, fp_b, intersection, union,
                        bytecode_a, bytecode_b, error_a, error_b
    """
    result: dict = {
        "jaccard": 0.0,
        "fp_a": set[int](),
        "fp_b": set[int](),
        "intersection": 0,
        "union": 0,
        "bytecode_a": bytearray(),
        "bytecode_b": bytearray(),
        "error_a": None,
        "error_b": None,
    }

    try:
        result["bytecode_a"] = assemble(_normalize(raw_a))
    except Exception as e:
        result["error_a"] = str(e)
    try:
        result["bytecode_b"] = assemble(_normalize(raw_b))
    except Exception as e:
        result["error_b"] = str(e)

    if result["error_a"] or result["error_b"]:
        return result

    # 指纹
    result["fp_a"] = compute_fingerprint(result["bytecode_a"])
    result["fp_b"] = compute_fingerprint(result["bytecode_b"])

    # 相似度
    result["jaccard"] = jaccard_similarity(result["fp_a"], result["fp_b"])
    result["intersection"] = len(result["fp_a"] & result["fp_b"]) if result["fp_a"] and result["fp_b"] else 0
    result["union"] = len(result["fp_a"] | result["fp_b"]) if result["fp_a"] or result["fp_b"] else 0

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compare-genomes",
        description="比对两个 CyberTerrarium 基因组的 Winnowing 指纹相似度",
    )
    parser.add_argument(
        "assembly_a",
        help="第一个基因组的 assembly 字符串",
    )
    parser.add_argument(
        "assembly_b",
        help="第二个基因组的 assembly 字符串",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示指纹详情",
    )

    args = parser.parse_args(argv)
    result = compare(args.assembly_a, args.assembly_b)

    # 错误处理
    if result["error_a"]:
        print(f"[ERROR] 基因组 A 汇编失败: {result['error_a']}", file=sys.stderr)
    if result["error_b"]:
        print(f"[ERROR] 基因组 B 汇编失败: {result['error_b']}", file=sys.stderr)
    if result["error_a"] or result["error_b"]:
        return 1

    # 输出
    print(f"基因组 A: {len(result['bytecode_a'])} bytes ({len(result['bytecode_a']) // 4} 指令)")
    print(f"基因组 B: {len(result['bytecode_b'])} bytes ({len(result['bytecode_b']) // 4} 指令)")
    print()
    print(f"Jaccard 相似度: {result['jaccard']:.4f}")
    print(f"指纹交集: {result['intersection']}")
    print(f"指纹并集: {result['union']}")

    if args.verbose:
        print()
        print(f"指纹 A: {_format_fingerprint(result['fp_a'])}")
        print(f"指纹 B: {_format_fingerprint(result['fp_b'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
