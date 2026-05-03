"""突变引擎 - 基因变异逻辑"""

import random

from cyberterrarium.model.config import (
    MAX_GENOME_LENGTH,
    MIN_GENOME_LENGTH,
    MUTATION_ENABLED,
    POINT_MUTATION_RATE,
    STRUCT_DELETION_RATE,
    STRUCT_INSERTION_RATE,
)


def apply_mutations(genome: bytearray) -> bytearray:
    """对子代基因组施加突变（点突变 + 结构突变）。"""
    if not MUTATION_ENABLED:
        return genome

    child = bytearray(genome)

    # 点突变：按指令遍历
    for i in range(0, len(child), 4):
        if random.random() < POINT_MUTATION_RATE:
            byte_idx = i + random.randint(0, 3)
            bit_idx = random.randint(0, 7)
            child[byte_idx] ^= 1 << bit_idx

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
