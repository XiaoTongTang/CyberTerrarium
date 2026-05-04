"""相机 - 视口缩放、平移与坐标变换"""

from __future__ import annotations


class Camera:
    """管理世界视口的缩放与平移状态。"""

    MIN_ZOOM: float = 1.0
    MAX_ZOOM: float = 20.0

    def __init__(self, grid_h: int, grid_w: int) -> None:
        self.grid_h = grid_h
        self.grid_w = grid_w
        self.cam_x: float = 0.0
        self.cam_y: float = 0.0
        self.zoom: float = 5.0

    def zoom_at(self, screen_x: int, screen_y: int, factor: float) -> None:
        """以屏幕坐标(screen_x, screen_y)为中心缩放，保持该点对应的世界格子不动。"""
        wx = (screen_x + self.cam_x) / self.zoom
        wy = (screen_y + self.cam_y) / self.zoom
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
        self.cam_x = wx * self.zoom - screen_x
        self.cam_y = wy * self.zoom - screen_y

    def pan(self, dx: int, dy: int) -> None:
        """按屏幕像素偏移量平移相机。"""
        self.cam_x += dx
        self.cam_y += dy

    def screen_to_grid(self, sx: int, sy: int) -> tuple[int, int]:
        """将视口内屏幕坐标转换为网格 (gy, gx)，支持环绕取模。"""
        gx = int((sx + self.cam_x) / self.zoom)
        gy = int((sy + self.cam_y) / self.zoom)
        return gy % self.grid_h, gx % self.grid_w
