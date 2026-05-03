"""世界状态基础测试"""

import numpy as np

from cyberterrarium.model.world import World


def test_world_creation() -> None:
    world = World(100, 100)
    assert world.w == 100
    assert world.h == 100
    assert world.grid.shape == (100, 100)
    assert world.grid.dtype == np.uint8


def test_world_get_set() -> None:
    world = World(10, 10)
    world.set_material(5, 5, World.NUTRIENT)
    assert world.get_material(5, 5) == World.NUTRIENT
