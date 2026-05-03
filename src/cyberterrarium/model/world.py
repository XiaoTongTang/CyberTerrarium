"""世界状态 - 2D化学物质网格"""

import numpy as np


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

    def get_material(self, x: int, y: int) -> int:
        return int(self.grid[y % self.h, x % self.w])

    def set_material(self, x: int, y: int, material_id: int) -> None:
        self.grid[y % self.h, x % self.w] = material_id
