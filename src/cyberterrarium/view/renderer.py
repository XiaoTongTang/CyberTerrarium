"""帧渲染器 - 物质LUT与能量Jet色带的零拷贝渲染管线"""

from __future__ import annotations

import numpy as np

from cyberterrarium.facade.api import ViewAPI

# 物质模式离散颜色查找表 (行索引=物质ID，列=RGB)
MATERIAL_LUT: np.ndarray = np.array([
    [10, 10, 15],  # 0: EMPTY
    [40, 180, 60],  # 1: NUTRIENT
    [240, 220, 50],  # 2: ENZYME
    [220, 50, 50],  # 3: TOXIN
    [60, 130, 220],  # 4: SIGNAL
], dtype=np.uint8)

# 生物本体色
ORG_COLOR: np.ndarray = np.array([255, 255, 255], dtype=np.uint8)

# 预计算 Jet 色带 (256级)
JET_COLORMAP: np.ndarray = np.zeros((256, 3), dtype=np.uint8)


def _build_jet_colormap() -> np.ndarray:
    """生成256级Jet伪彩色映射表。"""
    t = np.linspace(0, 1, 256)
    r = np.clip(1.5 - np.abs(4 * t - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * t - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * t - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


JET_COLORMAP = _build_jet_colormap()

# 能量上限（用于归一化）
_MAX_ENERGY: int = 1000


class FrameRenderer:
    """从ViewAPI零拷贝数据生成(W,H,3) uint8像素帧。"""

    def __init__(self, view_api: ViewAPI) -> None:
        self.view_api = view_api
        self.mode: str = "material"  # "material" | "energy"

    def render(self) -> np.ndarray:
        """返回(W, H, 3) uint8数组，供pygame.surfarray.make_surface使用。"""
        if self.mode == "energy":
            return self._render_energy()
        return self._render_material()

    def _render_material(self) -> np.ndarray:
        grid = self.view_api.get_chemical_grid_ref()  # (H, W) uint8
        positions = self.view_api.get_organism_positions_array()  # (N, 2) [Y, X]
        safe_grid = np.clip(grid, 0, len(MATERIAL_LUT) - 1)
        rgb = MATERIAL_LUT[safe_grid]  # (H, W, 3)
        if len(positions) > 0:
            rgb[positions[:, 0], positions[:, 1]] = ORG_COLOR
        # transpose到(W, H, 3)给pygame，.copy()确保C-contiguous
        return rgb.transpose(1, 0, 2).copy()

    def _render_energy(self) -> np.ndarray:
        grid = self.view_api.get_chemical_grid_ref()
        positions = self.view_api.get_organism_positions_array()
        energies = self.view_api.get_organism_energies_array()
        H, W = grid.shape
        safe_grid = np.clip(grid, 0, len(MATERIAL_LUT) - 1)

        # 暗化化学背景
        bg = (MATERIAL_LUT[safe_grid].astype(np.float32) * 0.3).astype(np.uint8)

        # 稀疏散点赋值
        energy_map = np.zeros((H, W), dtype=np.uint8)
        if len(positions) > 0 and len(energies) > 0:
            norm_e = np.clip(energies * 255 // _MAX_ENERGY, 0, 255).astype(np.uint8)
            energy_map[positions[:, 0], positions[:, 1]] = norm_e

        heat = JET_COLORMAP[energy_map]  # (H, W, 3)

        # 合成：有生物处用热力色，其余用暗化背景
        mask = energy_map > 0
        result = bg.copy()
        if mask.any():
            result[mask] = heat[mask]
        return result.transpose(1, 0, 2).copy()
