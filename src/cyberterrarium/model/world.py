"""世界状态 - 2D化学物质网格 + 实体网格"""

from __future__ import annotations

import numpy as np

from cyberterrarium.model.organism import Organism


class World:
    """虚拟机全局共享内存环境。"""

    # 化学物质ID常量
    EMPTY: int = 0
    NUTRIENT: int = 1
    ENZYME: int = 2
    TOXIN: int = 3
    SIGNAL: int = 4

    def __init__(self, width: int, height: int) -> None:
        self.w = width
        self.h = height
        self.grid = np.zeros((height, width), dtype=np.uint8)
        self.signal_life = np.zeros((height, width), dtype=np.int8)
        self.nutrient_life = np.zeros((height, width), dtype=np.int8)
        self.enzyme_life = np.zeros((height, width), dtype=np.int8)
        # 实体网格：存储生物对象引用，无生物则为 None
        self.entity_grid: list[list[Organism | None]] = [
            [None for _ in range(width)] for _ in range(height)
        ]

    def get_material(self, x: int, y: int) -> int:
        return int(self.grid[y % self.h, x % self.w])

    def set_material(self, x: int, y: int, material_id: int) -> None:
        self.grid[y % self.h, x % self.w] = material_id

    def get_entity(self, x: int, y: int) -> Organism | None:
        return self.entity_grid[y % self.h][x % self.w]

    def set_entity(self, x: int, y: int, org: Organism | None) -> None:
        self.entity_grid[y % self.h][x % self.w] = org
