"""布局常量、主题色板与字体规范"""

from __future__ import annotations

from pathlib import Path


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


# 初始窗口基准（用于 set_mode）
INIT_SCREEN_W: int = 1280
INIT_SCREEN_H: int = 720

# 布局比例
TOP_BAR_H: int = 40  # 顶栏高度（固定像素）
RIGHT_PANEL_RATIO: float = 0.33  # 右面板占窗口宽度比
TAB_BAR_H: int = 30  # Tab 栏高度（固定像素）

# Tab 名称
TAB_NAMES: list[str] = ["Stats", "Inspector", "Log"]

# 字号
FONT_SM: int = 14
FONT_MD: int = 16
FONT_LG: int = 18

# 主题 JSON 路径
THEME_JSON_PATH: str = str(Path(__file__).parent / "theme.json")
