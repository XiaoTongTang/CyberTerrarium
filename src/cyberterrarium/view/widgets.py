"""UI组件 - 顶栏、右侧面板（统计/检查/日志）"""

from __future__ import annotations

from collections import deque

import pygame

from cyberterrarium.facade.api import ViewAPI
from cyberterrarium.model.organism import Organism
from cyberterrarium.tools.disassembler import disassemble_with_labels
from cyberterrarium.view.layout import (
    RIGHT_PANEL,
    SCREEN_W,
    TAB_BAR_H,
    TAB_NAMES,
    Theme,
)
from cyberterrarium.view.renderer import MATERIAL_LUT


class TopBar:
    """顶部工具栏：状态指示、控制按键、速度滑块、视图切换、系统信息。"""

    def __init__(self) -> None:
        self.font: pygame.font.Font | None = None
        self.font_sm: pygame.font.Font | None = None
        self.ticks_per_frame: int = 1
        self.view_mode: str = "material"  # "material" | "energy"
        self._slider_dragging: bool = False

    def init_fonts(self, font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
        self.font = font_md
        self.font_sm = font_sm

    def handle_click(self, mx: int, my: int, screen_w: int) -> None:
        """处理顶栏区域的鼠标点击。返回是否消费了事件。"""
        _, _, _, bar_h = (0, 0, SCREEN_W, 40)
        if my > bar_h:
            return
        # 速度滑块区域 (大致在 x=600~750)
        slider_x0 = 600
        slider_x1 = 750
        if slider_x0 <= mx <= slider_x1:
            ratio = (mx - slider_x0) / (slider_x1 - slider_x0)
            self.ticks_per_frame = max(1, min(50, int(ratio * 50) + 1))
            self._slider_dragging = True
        # 视图模式切换 (大致在 x=800~950)
        mode_x0 = 800
        btn_w = 70
        if mode_x0 <= mx <= mode_x0 + btn_w:
            self.view_mode = "material"
        elif mode_x0 + btn_w + 5 <= mx <= mode_x0 + 2 * btn_w + 5:
            self.view_mode = "energy"

    def handle_drag(self, mx: int) -> None:
        if self._slider_dragging:
            slider_x0 = 600
            slider_x1 = 750
            ratio = max(0.0, min(1.0, (mx - slider_x0) / (slider_x1 - slider_x0)))
            self.ticks_per_frame = max(1, min(50, int(ratio * 50) + 1))

    def handle_release(self) -> None:
        self._slider_dragging = False

    def render(
        self,
        surface: pygame.Surface,
        mode: str,
        is_paused: bool,
        fps: float,
        tick: int,
        alive: int,
        cap: int,
    ) -> None:
        assert self.font is not None and self.font_sm is not None
        # 背景
        pygame.draw.rect(surface, Theme.PANEL, (0, 0, SCREEN_W, 40))
        pygame.draw.line(surface, Theme.BORDER, (0, 39), (SCREEN_W, 39))

        x = 10
        # 状态指示灯
        if mode == "CONTINUOUS" and not is_paused:
            color = Theme.SUCCESS
            label = "Running"
        elif mode == "DEBUG":
            color = Theme.HIGHLIGHT
            label = "Debug"
        else:
            color = (200, 200, 60)
            label = "Paused"
        pygame.draw.circle(surface, color, (x + 6, 20), 6)
        txt = self.font.render(label, True, Theme.TEXT)
        surface.blit(txt, (x + 16, 11))
        x += 16 + txt.get_width() + 15

        # 控制按键标签
        debug_active = mode == "DEBUG"
        keys_info = [
            ("[Space] Play/Pause", True),
            ("[F1] Physics", debug_active),
            ("[F2] Life", debug_active),
            ("[F3] Repro", debug_active),
            ("[F5] FullTick", debug_active),
        ]
        for text, active in keys_info:
            c = Theme.TEXT if active else Theme.GREYED
            txt = self.font_sm.render(text, True, c)
            surface.blit(txt, (x, 13))
            x += txt.get_width() + 10

        # 速度滑块
        x = 600
        txt = self.font_sm.render("Speed:", True, Theme.TEXT)
        surface.blit(txt, (x, 13))
        x += txt.get_width() + 5
        slider_w = 150
        pygame.draw.rect(surface, Theme.BORDER, (x, 16, slider_w, 8))
        ratio = (self.ticks_per_frame - 1) / 49.0
        knob_x = x + int(ratio * slider_w)
        pygame.draw.circle(surface, Theme.HIGHLIGHT, (knob_x, 20), 6)
        x += slider_w + 5
        val_txt = self.font_sm.render(f"{self.ticks_per_frame} T/F", True, Theme.TEXT)
        surface.blit(val_txt, (x, 13))

        # 视图模式切换
        x = 800
        for mode_name in ["Material", "Energy"]:
            is_active = self.view_mode == mode_name.lower()
            c = Theme.HIGHLIGHT if is_active else Theme.GREYED
            btn_w = 70
            pygame.draw.rect(surface, c, (x, 10, btn_w, 20), 2 if not is_active else 0)
            txt = self.font_sm.render(mode_name, True, Theme.TEXT if is_active else Theme.GREYED)
            surface.blit(txt, (x + (btn_w - txt.get_width()) // 2, 13))
            x += btn_w + 5

        # 右侧系统信息
        info = f"FPS: {fps:.0f}  Tick: {tick}  Pop: {alive}/{cap}"
        txt = self.font_sm.render(info, True, Theme.TEXT)
        surface.blit(txt, (SCREEN_W - txt.get_width() - 10, 13))


class StatsTab:
    """统计折线图Tab。"""

    def __init__(self) -> None:
        self.population_history: deque[int] = deque(maxlen=1000)
        self.energy_history: deque[float] = deque(maxlen=1000)
        self.font: pygame.font.Font | None = None

    def init_fonts(self, font_sm: pygame.font.Font) -> None:
        self.font = font_sm

    def update(self, alive: int, avg_energy: float) -> None:
        self.population_history.append(alive)
        self.energy_history.append(avg_energy)

    def render(self, surface: pygame.Surface, rect: tuple[int, int, int, int]) -> None:
        assert self.font is not None
        x, y, w, h = rect
        pygame.draw.rect(surface, Theme.PANEL, rect)
        # 图例
        lx = x + 10
        ly = y + 5
        pygame.draw.rect(surface, Theme.TEXT, (lx, ly + 2, 10, 10))
        surface.blit(self.font.render("Population", True, Theme.TEXT), (lx + 14, ly))
        lx += 110
        pygame.draw.rect(surface, (200, 200, 60), (lx, ly + 2, 10, 10))
        surface.blit(self.font.render("Avg Energy", True, (200, 200, 60)), (lx + 14, ly))

        # 绘图区
        chart_x = x + 10
        chart_y = y + 30
        chart_w = w - 20
        chart_h = h - 40
        pygame.draw.rect(surface, (20, 20, 25), (chart_x, chart_y, chart_w, chart_h))

        self._draw_line(
            surface, self.population_history,
            chart_x, chart_y, chart_w, chart_h, Theme.TEXT,
        )
        self._draw_line(
            surface, self.energy_history,
            chart_x, chart_y, chart_w, chart_h, (200, 200, 60),
        )

    def _draw_line(
        self,
        surface: pygame.Surface,
        data: deque,
        cx: int, cy: int, cw: int, ch: int,
        color: tuple[int, int, int],
    ) -> None:
        if len(data) < 2:
            return
        max_val = max(max(data), 1)
        points = []
        n = len(data)
        for i, val in enumerate(data):
            px = cx + int(i * cw / max(n - 1, 1))
            py = cy + ch - int(val / max_val * ch * 0.9)
            points.append((px, py))
        if len(points) >= 2:
            pygame.draw.lines(surface, color, False, points, 1)


class InspectorTab:
    """生物检查器Tab：元数据、反汇编、局部环境。"""

    def __init__(self, view_api: ViewAPI) -> None:
        self.view_api = view_api
        self.font: pygame.font.Font | None = None
        self.font_sm: pygame.font.Font | None = None
        self.scroll_offset: int = 0

    def init_fonts(self, font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
        self.font = font_md
        self.font_sm = font_sm

    def render(
        self,
        surface: pygame.Surface,
        rect: tuple[int, int, int, int],
        selected_org_id: int | None,
    ) -> None:
        assert self.font is not None and self.font_sm is not None
        x, y, w, h = rect
        pygame.draw.rect(surface, Theme.PANEL, rect)

        if selected_org_id is None:
            txt = self.font.render("Click an organism to inspect", True, Theme.GREYED)
            surface.blit(txt, (x + (w - txt.get_width()) // 2, y + h // 2))
            return

        detail = self.view_api.get_organism_detail_safe(selected_org_id)
        if detail is None:
            txt = self.font.render("Organism no longer alive", True, Theme.WARNING)
            surface.blit(txt, (x + 10, y + 10))
            return

        # 元数据区
        my = y + 8
        mx = x + 10
        col_w = w // 2 - 10
        meta = [
            (f"ID: {detail['id']}", f"Age: {detail['age']}"),
            (f"Energy: {detail['energy']}", f"Len: {len(detail['genome_bytes'])}B"),
            (
                f"Pos: ({detail['regs'][Organism.DP_X]}, {detail['regs'][Organism.DP_Y]})",
                "Status: ALIVE",
            ),
        ]
        for left, right in meta:
            surface.blit(self.font_sm.render(left, True, Theme.TEXT), (mx, my))
            surface.blit(self.font_sm.render(right, True, Theme.TEXT), (mx + col_w, my))
            my += 18
        my += 5
        pygame.draw.line(surface, Theme.BORDER, (x + 5, my), (x + w - 5, my))
        my += 5

        # 反汇编视图
        genome = detail["genome_bytes"]
        pc = detail["pc"]
        lines = disassemble_with_labels(genome)
        line_h = 16
        visible_lines = min((h - (my - y) - 220) // line_h, len(lines))
        end = min(len(lines), self.scroll_offset + visible_lines)
        for i in range(max(0, self.scroll_offset), end):
            line_text = lines[i]
            inst_offset = i * 4
            is_pc_line = inst_offset <= pc < inst_offset + 4
            if is_pc_line:
                pygame.draw.rect(surface, (40, 60, 90), (x, my, w, line_h))
            txt = self.font_sm.render(line_text, True, Theme.TEXT)
            surface.blit(txt, (x + 10, my))
            my += line_h

        # 局部环境 9x9
        env_y = y + h - 210
        pygame.draw.line(surface, Theme.BORDER, (x + 5, env_y - 5), (x + w - 5, env_y - 5))
        grid = self.view_api.get_chemical_grid_ref()
        gy = detail["regs"][Organism.DP_Y]
        gx = detail["regs"][Organism.DP_X]
        grid_h, grid_w = grid.shape
        cell_size = min((w - 20) // 9, 22)
        env_x0 = x + (w - 9 * cell_size) // 2
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                wy = (gy + dy) % grid_h
                wx = (gx + dx) % grid_w
                mat_id = int(grid[wy, wx])
                color = tuple(MATERIAL_LUT[mat_id])
                rx = env_x0 + (dx + 4) * cell_size
                ry = env_y + (dy + 4) * cell_size
                pygame.draw.rect(surface, color, (rx, ry, cell_size - 1, cell_size - 1))
        # 中心标记
        cx = env_x0 + 4 * cell_size
        cy = env_y + 4 * cell_size
        pygame.draw.rect(surface, Theme.HIGHLIGHT, (cx, cy, cell_size - 1, cell_size - 1), 2)


class LogTab:
    """事件日志Tab。"""

    def __init__(self) -> None:
        self.entries: deque[tuple[str, tuple[int, int, int]]] = deque(maxlen=200)
        self.font: pygame.font.Font | None = None
        self.filter: str = "all"  # "all" | "birth" | "death"

    def init_fonts(self, font_sm: pygame.font.Font) -> None:
        self.font = font_sm

    def add_event(self, event_type: str, data: dict) -> None:
        color = Theme.SUCCESS if event_type == "birth" else Theme.WARNING
        tick = data.get("tick", 0)
        org_id = data.get("org_id", "?")
        ex, ey = data.get("x", "?"), data.get("y", "?")
        text = f"[Tick:{tick}] [{event_type.upper()}] Org #{org_id} at ({ex},{ey})"
        self.entries.append((text, color))

    def render(self, surface: pygame.Surface, rect: tuple[int, int, int, int]) -> None:
        assert self.font is not None
        x, y, w, h = rect
        pygame.draw.rect(surface, Theme.PANEL, rect)

        # 过滤栏
        fx = x + 5
        fy = y + 5
        for name in ["All", "Birth", "Death"]:
            is_active = self.filter == name.lower()
            c = Theme.HIGHLIGHT if is_active else Theme.GREYED
            btn_w = 50
            pygame.draw.rect(surface, c, (fx, fy, btn_w, 18), 0 if is_active else 1)
            txt = self.font.render(name, True, Theme.TEXT if is_active else Theme.GREYED)
            surface.blit(txt, (fx + (btn_w - txt.get_width()) // 2, fy + 1))
            fx += btn_w + 5

        # 日志文本
        ly = fy + 25
        line_h = 16
        max_lines = (h - (ly - y) - 5) // line_h
        shown = 0
        for text, color in reversed(self.entries):
            if self.filter != "all":
                event_tag = f"[{self.filter.upper()}]"
                if event_tag not in text:
                    continue
            if shown >= max_lines:
                break
            txt = self.font.render(text, True, color)
            surface.blit(txt, (x + 5, ly))
            ly += line_h
            shown += 1

    def handle_click(self, mx: int, my: int, rect: tuple[int, int, int, int]) -> None:
        x, y, _, _ = rect
        fy = y + 5
        if not (fy <= my <= fy + 18):
            return
        fx = x + 5
        for name in ["all", "birth", "death"]:
            btn_w = 50
            if fx <= mx <= fx + btn_w:
                self.filter = name
                return
            fx += btn_w + 5


class RightPanel:
    """右侧面板：Tab栏 + 3个Tab内容区。"""

    def __init__(self, view_api: ViewAPI) -> None:
        self.stats = StatsTab()
        self.inspector = InspectorTab(view_api)
        self.log = LogTab()
        self.active_tab: int = 0
        self.font: pygame.font.Font | None = None
        self.font_sm: pygame.font.Font | None = None

    def init_fonts(self, font_sm: pygame.font.Font, font_md: pygame.font.Font) -> None:
        self.font = font_md
        self.font_sm = font_sm
        self.stats.init_fonts(font_sm)
        self.inspector.init_fonts(font_sm, font_md)
        self.log.init_fonts(font_sm)

    def handle_click(self, mx: int, my: int) -> None:
        """处理右侧面板区域的鼠标点击。"""
        px, py, pw, _ = RIGHT_PANEL
        if mx < px or mx > px + pw:
            return
        # Tab栏点击
        if py <= my <= py + TAB_BAR_H:
            tab_w = pw // len(TAB_NAMES)
            idx = (mx - px) // tab_w
            if 0 <= idx < len(TAB_NAMES):
                self.active_tab = idx
            return
        # Log Tab过滤栏
        if self.active_tab == 2:
            content_rect = self._content_rect()
            self.log.handle_click(mx, my, content_rect)

    def _content_rect(self) -> tuple[int, int, int, int]:
        px, py, pw, ph = RIGHT_PANEL
        return (px, py + TAB_BAR_H, pw, ph - TAB_BAR_H)

    def render(
        self,
        surface: pygame.Surface,
        selected_org_id: int | None,
    ) -> None:
        assert self.font is not None
        px, py, pw, ph = RIGHT_PANEL
        # 背景
        pygame.draw.rect(surface, Theme.PANEL, RIGHT_PANEL)
        # Tab栏
        tab_w = pw // len(TAB_NAMES)
        for i, name in enumerate(TAB_NAMES):
            is_active = i == self.active_tab
            c = Theme.HIGHLIGHT if is_active else Theme.BORDER
            rect = (px + i * tab_w, py, tab_w, TAB_BAR_H)
            pygame.draw.rect(surface, c, rect, 0 if is_active else 1)
            txt = self.font.render(name, True, Theme.TEXT if is_active else Theme.GREYED)
            surface.blit(txt, (px + i * tab_w + (tab_w - txt.get_width()) // 2, py + 6))
        # 内容
        content_rect = self._content_rect()
        if self.active_tab == 0:
            self.stats.render(surface, content_rect)
        elif self.active_tab == 1:
            self.inspector.render(surface, content_rect, selected_org_id)
        elif self.active_tab == 2:
            self.log.render(surface, content_rect)
