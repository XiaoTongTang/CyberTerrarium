"""Winnowing指纹提取 - 基于OpCode的基因控制流指纹"""

from __future__ import annotations

# Winnowing参数
_K: int = 2   # k-gram长度
_W: int = 3   # 滑动窗口大小
_BASE: int = 31  # 多项式哈希基数
_MASK: int = 0xFFFFFFFFFFFFFFFF  # 64位取模掩码


def compute_fingerprint(genome: bytearray | bytes) -> set[int]:
    """从基因组中提取Winnowing指纹集合。

    仅提取每条指令的OpCode（每4字节第0字节），忽略操作数。
    """
    # 提取opcode序列
    opcodes: list[int] = []
    for i in range(0, len(genome) - 3, 4):
        opcodes.append(genome[i])

    if len(opcodes) < _K:
        return set()

    # 计算k-gram哈希序列
    hash_list: list[int] = []
    for i in range(len(opcodes) - _K + 1):
        h = 0
        for j in range(_K):
            h = (h * _BASE + opcodes[i + j]) & _MASK
        hash_list.append(h)

    if len(hash_list) < _W:
        # 窗口不够大，直接取所有哈希的最小值
        return {min(hash_list)} if hash_list else set()

    # Winnowing: 滑动窗口选最小哈希，平局取最右侧
    fingerprint: set[int] = set()
    for i in range(len(hash_list) - _W + 1):
        window = hash_list[i : i + _W]
        min_val = min(window)
        for j in range(_W - 1, -1, -1):
            if window[j] == min_val:
                fingerprint.add(hash_list[i + j])
                break

    return fingerprint
