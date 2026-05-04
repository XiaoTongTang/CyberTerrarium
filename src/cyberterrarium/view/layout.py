"""布局常量、主题色板与字体规范"""

from __future__ import annotations


class Theme:
    BG: tuple[int, int, int] = (30, 30, 30)  # #1E1E1E
    PANEL: tuple[int, int, int] = (37, 37, 38)  # #252526
    BORDER: tuple[int, int, int] = (60, 60, 60)  # #3C3C3C
    TEXT: tuple[int, int, int] = (212, 212, 212)  # #D4D4D4
    HIGHLIGHT: tuple[int, int, int] = (86, 156, 214)  # #569CD6
    WARNING: tuple[int, int, int] = (244, 71, 71)  # #F44747
    SUCCESS: tuple[int, int, int] = (106, 153, 85)  # #6A9955
    GREYED: tuple[int, int, int] = (90, 90, 90)  # 不可用控件灰显
    FONT_NAME: str = "consolas,couriernew,monospace"


# 屏幕基准
SCREEN_W: int = 1920
SCREEN_H: int = 1080

# 三区域拓扑 (x, y, w, h)
TOP_BAR: tuple[int, int, int, int] = (0, 0, 1920, 40)
LEFT_VIEWPORT: tuple[int, int, int, int] = (0, 40, 1280, 1040)
RIGHT_PANEL: tuple[int, int, int, int] = (1280, 40, 640, 1040)

# 右侧面板内部
TAB_BAR_H: int = 30
TAB_NAMES: list[str] = ["Stats", "Inspector", "Log"]

# 字号
FONT_SM: int = 14
FONT_MD: int = 16
FONT_LG: int = 18
