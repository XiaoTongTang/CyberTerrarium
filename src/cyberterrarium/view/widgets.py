"""UI组件 - pygame_gui 版顶栏、右侧面板（统计/检查/日志）"""

from __future__ import annotations

import html as html_mod
from collections import deque

import numpy as np
import pygame
import pygame_gui

from cyberterrarium.facade.api import ViewAPI
from cyberterrarium.model.isa import REG_NAMES
from cyberterrarium.model.organism import Organism
from cyberterrarium.tools.disassembler import disassemble_with_labels
from cyberterrarium.view.layout import (
    INIT_SCREEN_H,
    INIT_SCREEN_W,
    RIGHT_PANEL_RATIO,
    TAB_BAR_H,
    TAB_NAMES,
    TOP_BAR_H,
    Theme,
)
from cyberterrarium.view.renderer import MATERIAL_LUT


def _escape(text: str) -> str:
    """HTML 转义。"""
    return html_mod.escape(text)


def _genome_hex_dump(genome: bytearray | bytes) -> list[str]:
    """将基因组转为十六进制转储行列表，每4字节一条指令。"""
    lines: list[str] = []
    for i in range(0, len(genome) - 3, 4):
        chunk = genome[i : i + 4]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        lines.append(f"{i:04X}: {hex_str}")
    remainder = len(genome) % 4
    if remainder:
        trailing = genome[len(genome) - remainder :]
        hex_str = " ".join(f"{b:02X}" for b in trailing)
        lines.append(f"{len(genome) - remainder:04X}: {hex_str}")
    return lines


def _hex_to_html(hex_lines: list[str], pc: int) -> str:
    """将十六进制转储行转为 HTML，PC 行高亮。"""
    parts: list[str] = []
    for i, line in enumerate(hex_lines):
        inst_offset = i * 4
        if inst_offset <= pc < inst_offset + 4:
            parts.append(f'<font color="#569CD6"><b>{_escape(line)}</b></font><br>')
        else:
            parts.append(f"{_escape(line)}<br>")
    return "".join(parts)


def _asm_to_html(asm_lines: list[str], pc: int) -> str:
    """将汇编行转为 HTML，PC 行高亮。"""
    parts: list[str] = []
    for i, line in enumerate(asm_lines):
        inst_offset = i * 4
        if inst_offset <= pc < inst_offset + 4:
            parts.append(f'<font color="#569CD6"><b>{_escape(line)}</b></font><br>')
        else:
            parts.append(f"{_escape(line)}<br>")
    return "".join(parts)


def _render_env_grid(
    view_api: ViewAPI, regs: list[int], cell_size: int = 20
) -> pygame.Surface:
    """渲染 9x9 局部环境网格到 Surface。"""
    grid = view_api.get_chemical_grid_ref()
    gy = regs[Organism.DP_Y]
    gx = regs[Organism.DP_X]
    grid_h, grid_w = grid.shape
    size = 9 * cell_size
    surface = pygame.Surface((size, size))
    surface.fill(Theme.BG)
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            wy = (gy + dy) % grid_h
            wx = (gx + dx) % grid_w
            mat_id = int(np.clip(grid[wy, wx], 0, 4))
            color = tuple(MATERIAL_LUT[mat_id])
            erx = (dx + 4) * cell_size
            ery = (dy + 4) * cell_size
            pygame.draw.rect(surface, color, (erx, ery, cell_size - 1, cell_size - 1))
    # 中心标记
    cx = 4 * cell_size
    cy = 4 * cell_size
    pygame.draw.rect(surface, Theme.HIGHLIGHT, (cx, cy, cell_size - 1, cell_size - 1), 2)
    return surface


def _render_stats_chart(
    population_history: deque[int],
    energy_history: deque[float],
    opcode_total_history: dict[int, deque[int]] | None,
    opcode_org_history: dict[int, deque[int]] | None,
    opcode_colors: dict[int, tuple[int, int, int]] | None,
    mnemonic_by_code: dict[int, str] | None,
    legal_opcodes: list[int] | None,
    sub_index: int,
    w: int,
    h: int,
) -> pygame.Surface:
    """渲染统计折线图到 Surface，按 sub_index 只渲染选定的图表。"""
    surface = pygame.Surface((w, h))
    surface.fill((20, 20, 25))
    font = pygame.font.SysFont("consolas,couriernew,monospace", 12)

    chart_x = 10
    chart_y = 22
    chart_w = w - 20
    chart_h = h - 30

    has_opcode = (
        opcode_total_history is not None
        and opcode_org_history is not None
        and opcode_colors is not None
        and mnemonic_by_code is not None
        and legal_opcodes is not None
    )

    if sub_index == 0:
        # ── 图表1：种群与能量 ──
        pygame.draw.rect(surface, Theme.TEXT, (10, 7, 10, 10))
        surface.blit(font.render("Population", True, Theme.TEXT), (24, 5))
        pygame.draw.rect(surface, (200, 200, 60), (120, 7, 10, 10))
        surface.blit(font.render("Avg Energy", True, (200, 200, 60)), (134, 5))
        _draw_line(surface, population_history, chart_x, chart_y, chart_w, chart_h, Theme.TEXT)
        _draw_line(
            surface, energy_history, chart_x, chart_y, chart_w, chart_h, (200, 200, 60)
        )

    elif sub_index == 1 and has_opcode:
        # ── 图表2：基因组指令频次 ──
        surface.blit(font.render("Opcode Total Count", True, Theme.TEXT), (10, 5))
        _render_opcode_chart(
            surface, font, opcode_total_history, opcode_colors, mnemonic_by_code,
            legal_opcodes, chart_x, chart_y, chart_w, chart_h,
        )

    elif sub_index == 2 and has_opcode:
        # ── 图表3：基因组指令覆盖广度 ──
        surface.blit(font.render("Opcode Organism Count", True, Theme.TEXT), (10, 5))
        _render_opcode_chart(
            surface, font, opcode_org_history, opcode_colors, mnemonic_by_code,
            legal_opcodes, chart_x, chart_y, chart_w, chart_h,
        )

    return surface


def _render_opcode_chart(
    surface: pygame.Surface,
    font: pygame.font.Font,
    history: dict[int, deque[int]],
    colors: dict[int, tuple[int, int, int]],
    mnemonic_by_code: dict[int, str],
    legal_opcodes: list[int],
    cx: int,
    cy: int,
    cw: int,
    ch: int,
) -> None:
    """在指定区域绘制指令统计折线图 + 数据区。"""
    # 分区：左侧 70% 绘图，右侧 30% 数据
    plot_w = int(cw * 0.7)
    data_x = cx + plot_w + 5

    # 绘图
    for op in legal_opcodes:
        d = history.get(op)
        if d is not None and len(d) >= 2:
            _draw_line(surface, d, cx, cy, plot_w, ch, colors[op])

    # 数据区
    line_h = 14
    max_lines = max(ch // line_h, 1)
    shown = legal_opcodes[:max_lines]
    for i, op in enumerate(shown):
        d = history.get(op)
        val = d[-1] if d and len(d) > 0 else 0
        name = mnemonic_by_code.get(op, f"0x{op:02X}")
        color = colors.get(op, Theme.TEXT)
        ly = cy + i * line_h
        pygame.draw.rect(surface, color, (data_x, ly + 2, 8, 8))
        txt = f"{name}:{val}"
        surface.blit(font.render(txt, True, color), (data_x + 10, ly))


def _hsv_to_rgb(h: int, s: float, v: float) -> tuple[int, int, int]:
    """HSV → RGB，h 为 0-359，s/v 为 0.0-1.0。"""
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def _draw_line(
    surface: pygame.Surface,
    data: deque,
    cx: int,
    cy: int,
    cw: int,
    ch: int,
    color: tuple[int, int, int],
) -> None:
    """在指定区域绘制折线。"""
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


class TopBar:
    """顶部工具栏：状态指示、控制按键标签、速度滑块、视图切换、系统信息。"""

    def __init__(self, manager: pygame_gui.UIManager) -> None:
        self.manager = manager
        self.ticks_per_frame: int = 1
        self.view_mode: str = "material"  # "material" | "energy"

        # 顶栏面板
        self.panel = pygame_gui.elements.UIPanel(
            relative_rect=pygame.Rect(0, 0, INIT_SCREEN_W, TOP_BAR_H),
            manager=manager,
            anchors={"left": "left", "right": "right", "top": "top", "bottom": "top"},
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#top_bar_panel"),
        )

        # 状态指示标签
        self._status_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(10, 10, 110, 20),
            text="● Running",
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#status_label"),
        )

        # 控制按键标签
        self._key_labels: list[pygame_gui.elements.UILabel] = []
        key_texts = [
            "[Space] Play/Pause",
            "[F1] Physics",
            "[F2] Life",
            "[F3] Repro+Settle",
            "[F5] FullTick",
        ]
        kx = 130
        for text in key_texts:
            lbl = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect(kx, 12, -1, 16),
                text=text,
                manager=manager,
                container=self.panel,
                object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#key_label"),
            )
            self._key_labels.append(lbl)
            kx += lbl.rect.width + 10

        # 速度标签
        self._speed_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(580, 12, -1, 16),
            text="Speed:",
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#key_label"),
        )

        # 速度滑块
        self._speed_slider = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect(630, 14, 150, 14),
            start_value=1,
            value_range=(1, 50),
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#speed_slider"),
        )

        # 速度值标签
        self._speed_val_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(785, 12, -1, 16),
            text="1 T/F",
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#key_label"),
        )

        # 视图模式按钮
        self._material_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(850, 8, 70, 22),
            text="Material",
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#view_mode_button"
            ),
        )
        self._energy_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(925, 8, 70, 22),
            text="Energy",
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#view_mode_button"
            ),
        )

        # 系统信息标签（右对齐）
        self._sysinfo_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(-300, 12, 280, 16),
            text="FPS: 0  Tick: 0  Pop: 0/0",
            manager=manager,
            container=self.panel,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#sysinfo_label"),
            anchors={"right": "right", "left": "right", "top": "top", "bottom": "top"},
        )

    def handle_button(self, ui_element: pygame_gui.core.UIElement) -> None:
        """处理按钮点击事件。"""
        if ui_element == self._material_btn:
            self.view_mode = "material"
        elif ui_element == self._energy_btn:
            self.view_mode = "energy"

    def handle_slider(self, ui_element: pygame_gui.core.UIElement, value: float) -> None:
        """处理滑块值变化事件。"""
        if ui_element == self._speed_slider:
            self.ticks_per_frame = max(1, int(value))
            self._speed_val_label.set_text(f"{self.ticks_per_frame} T/F")

    def update_info(
        self,
        mode: str,
        is_paused: bool,
        fps: float,
        tick: int,
        alive: int,
        cap: int,
    ) -> None:
        """更新顶栏显示信息。"""
        # 状态指示
        if mode == "CONTINUOUS" and not is_paused:
            self._status_label.set_text("● Running")
        elif mode == "DEBUG":
            self._status_label.set_text("● Debug")
        else:
            self._status_label.set_text("● Paused")

        # 系统信息
        self._sysinfo_label.set_text(f"FPS: {fps:.0f}  Tick: {tick}  Pop: {alive}/{cap}")


class RightPanel:
    """右侧面板：Tab 栏 + 3 个 Tab 内容区。"""

    # 日志显示上限：UITextBox 只渲染最近这么多条，避免 HTML 解析过慢
    _LOG_DISPLAY_LIMIT: int = 50

    def __init__(self, manager: pygame_gui.UIManager, view_api: ViewAPI) -> None:
        self.manager = manager
        self.view_api = view_api
        self.active_tab: int = 0
        self._last_org_id: int | None = None

        # 统计数据
        self._population_history: deque[int] = deque(maxlen=1000)
        self._energy_history: deque[float] = deque(maxlen=1000)
        # 指令统计历史
        from cyberterrarium.model.isa import LEGAL_OPCODES, MNEMONIC_BY_CODE
        self._legal_opcodes: list[int] = LEGAL_OPCODES
        self._mnemonic_by_code: dict[int, str] = MNEMONIC_BY_CODE
        self._opcode_colors: dict[int, tuple[int, int, int]] = {}
        n = len(LEGAL_OPCODES)
        for i, op in enumerate(LEGAL_OPCODES):
            hue = int(i * 360 / max(n, 1)) % 360
            self._opcode_colors[op] = _hsv_to_rgb(hue, 0.8, 0.9)
        self._opcode_total_history: dict[int, deque[int]] = {
            op: deque(maxlen=1000) for op in LEGAL_OPCODES
        }
        self._opcode_org_history: dict[int, deque[int]] = {
            op: deque(maxlen=1000) for op in LEGAL_OPCODES
        }

        # 日志数据
        self._log_entries: deque[tuple[str, tuple[int, int, int]]] = deque(maxlen=200)
        self._log_filter: str = "all"
        self._log_dirty: bool = False

        # 计算右面板位置
        panel_w = int(INIT_SCREEN_W * RIGHT_PANEL_RATIO)
        panel_h = INIT_SCREEN_H - TOP_BAR_H
        panel_rect = pygame.Rect(INIT_SCREEN_W - panel_w, TOP_BAR_H, panel_w, panel_h)

        # 面板容器
        self._panel = pygame_gui.elements.UIPanel(
            relative_rect=panel_rect,
            manager=manager,
            anchors={"left": "left", "right": "right", "top": "top", "bottom": "bottom"},
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#right_panel"),
        )

        # Tab 栏按钮
        self._tab_buttons: list[pygame_gui.elements.UIButton] = []
        tab_w = panel_w // len(TAB_NAMES)
        for i, name in enumerate(TAB_NAMES):
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(i * tab_w, 0, tab_w, TAB_BAR_H),
                text=name,
                manager=manager,
                container=self._panel,
                object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#tab_button"),
            )
            self._tab_buttons.append(btn)

        # 内容容器（Tab 栏下方）
        content_rect = pygame.Rect(0, TAB_BAR_H, panel_w, panel_h - TAB_BAR_H)
        self._content_container = pygame_gui.elements.UIPanel(
            relative_rect=content_rect,
            manager=manager,
            container=self._panel,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#right_panel"),
        )

        # ── Stats Tab 内容 ──
        self._stats_chart: pygame_gui.elements.UIImage | None = None
        self._stats_sub_index: int = 0  # 0=种群能量, 1=指令频次, 2=指令覆盖广度
        self._stats_sub_names: list[str] = ["Pop/Energy", "Opcode Freq", "Opcode Range"]
        self._stats_sub_buttons: list[pygame_gui.elements.UIButton] = []
        self._create_stats_tab(panel_w, panel_h)

        # ── Inspector Tab 内容 ──
        self._inspector_built: bool = False
        self._inspector_elements: list[pygame_gui.core.UIElement] = []
        self._placeholder_label: pygame_gui.elements.UILabel | None = None
        self._meta_labels: list[pygame_gui.elements.UILabel] = []
        self._reg_label: pygame_gui.elements.UILabel | None = None
        self._eq_flag_label: pygame_gui.elements.UILabel | None = None
        self._hex_box: pygame_gui.elements.UITextBox | None = None
        self._asm_box: pygame_gui.elements.UITextBox | None = None
        self._copy_btn: pygame_gui.elements.UIButton | None = None
        self._env_image: pygame_gui.elements.UIImage | None = None
        self._copy_btn_genome: bytearray | None = None
        self._cached_hex_lines: list[str] = []
        self._cached_asm_lines: list[str] = []
        self._last_org_id: int | None = None
        self._last_genome: bytes = b""
        self._last_pc: int = -1
        self._pc_update_counter: int = 0

        # ── Log Tab 内容 ──
        self._log_box: pygame_gui.elements.UITextBox | None = None
        self._filter_buttons: list[pygame_gui.elements.UIButton] = []
        self._create_log_tab(panel_w, panel_h)

        # 初始显示
        self._update_tab_visibility()

    def _create_stats_tab(self, panel_w: int, panel_h: int) -> None:
        """创建 Stats Tab 内容。"""
        # 图表子选择按钮行
        btn_w = panel_w // len(self._stats_sub_names)
        for i, name in enumerate(self._stats_sub_names):
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(i * btn_w, 0, btn_w, 24),
                text=name,
                manager=self.manager,
                container=self._content_container,
                object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#tab_button"),
            )
            self._stats_sub_buttons.append(btn)
        self._update_stats_sub_button_style()

        chart_w = panel_w - 20
        chart_h = panel_h - TAB_BAR_H - 54  # 54 = 按钮行24 + 间距30
        chart_surface = _render_stats_chart(
            self._population_history,
            self._energy_history,
            self._opcode_total_history,
            self._opcode_org_history,
            self._opcode_colors,
            self._mnemonic_by_code,
            self._legal_opcodes,
            self._stats_sub_index,
            max(chart_w, 1),
            max(chart_h, 1),
        )
        self._stats_chart = pygame_gui.elements.UIImage(
            relative_rect=pygame.Rect(10, 30, chart_w, chart_h),
            image_surface=chart_surface,
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(class_id=None, object_id="#stats_chart"),
        )

    def _update_stats_sub_button_style(self) -> None:
        """高亮当前选中的子图表按钮。"""
        for i, btn in enumerate(self._stats_sub_buttons):
            if i == self._stats_sub_index:
                btn.set_text(f"[{self._stats_sub_names[i]}]")
            else:
                btn.set_text(self._stats_sub_names[i])

    def _build_inspector_widgets(self, panel_w: int, panel_h: int) -> None:
        """一次性创建 Inspector 全部 UI 组件（占位内容），后续用增量更新。"""
        # 清除旧元素
        for elem in self._inspector_elements:
            elem.kill()
        self._inspector_elements.clear()
        if self._placeholder_label is not None:
            self._placeholder_label.kill()
            self._placeholder_label = None

        y = 5
        mx = 5

        # 占位标签（无生物选中时显示）
        self._placeholder_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(0, panel_h // 2 - 10, panel_w, 20),
            text="Click an organism to inspect",
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#placeholder_label"
            ),
        )

        # ── 元数据标签 × 3 ──
        self._meta_labels = []
        for _ in range(3):
            lbl = pygame_gui.elements.UILabel(
                relative_rect=pygame.Rect(mx, y, panel_w - 10, 18),
                text="",
                manager=self.manager,
                container=self._content_container,
                object_id=pygame_gui.core.ObjectID(
                    class_id=None, object_id="#meta_label"
                ),
            )
            self._meta_labels.append(lbl)
            self._inspector_elements.append(lbl)
            y += 18

        y += 3

        # ── 寄存器标签 ──
        self._reg_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(mx, y, panel_w - 10, 18),
            text="",
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#section_label"
            ),
        )
        self._inspector_elements.append(self._reg_label)
        y += 18

        # ── EQ_Flag 标签 ──
        self._eq_flag_label = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect(mx, y, panel_w - 10, 18),
            text="",
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#meta_label"
            ),
        )
        self._inspector_elements.append(self._eq_flag_label)
        y += 20

        # ── Hex Dump 文本框 ──
        self._hex_box = pygame_gui.elements.UITextBox(
            html_text="",
            relative_rect=pygame.Rect(mx, y, panel_w - 10, 100),
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#hex_textbox"
            ),
        )
        self._inspector_elements.append(self._hex_box)
        y += 105

        # ── 反汇编文本框 ──
        self._asm_box = pygame_gui.elements.UITextBox(
            html_text="",
            relative_rect=pygame.Rect(mx, y, panel_w - 10, 100),
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#asm_textbox"
            ),
        )
        self._inspector_elements.append(self._asm_box)
        y += 105

        # ── Copy ASM 按钮 ──
        self._copy_btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(panel_w - 95, y, 80, 22),
            text="Copy ASM",
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#copy_button"
            ),
        )
        self._inspector_elements.append(self._copy_btn)
        y += 28

        # ── 局部环境 9×9 ──
        cell_size = min((panel_w - 20) // 9, 20)
        env_size = 9 * cell_size
        placeholder_surf = pygame.Surface((env_size, env_size))
        placeholder_surf.fill(Theme.BG)
        self._env_image = pygame_gui.elements.UIImage(
            relative_rect=pygame.Rect((panel_w - env_size) // 2, y, env_size, env_size),
            image_surface=placeholder_surf,
            manager=self.manager,
            container=self._content_container,
        )
        self._inspector_elements.append(self._env_image)

        # 重置缓存
        self._cached_hex_lines = []
        self._cached_asm_lines = []
        self._copy_btn_genome = None
        self._last_genome = b""
        self._last_pc = -1
        self._pc_update_counter = 0
        self._inspector_built = True

    def _update_inspector_detail(self, detail: dict) -> None:
        """增量更新 Inspector 组件内容，不做 kill+recreate。"""
        regs = detail["regs"]
        pc = detail["pc"]
        genome = detail["genome_bytes"]
        genome_bytes = bytes(genome)
        genome_changed = genome_bytes != self._last_genome

        # ── 轻量更新：每帧 ──
        self._meta_labels[0].set_text(f"ID: {detail['id']}    Age: {detail['age']}")
        self._meta_labels[1].set_text(f"Energy: {detail['energy']}    Len: {len(genome)}B")
        self._meta_labels[2].set_text(
            f"Pos: ({regs[Organism.DP_X]}, {regs[Organism.DP_Y]})    PC: {pc}"
        )

        reg_parts = [f"{name}={regs[i]}" for i, name in enumerate(REG_NAMES)]
        self._reg_label.set_text("Regs: " + "  ".join(reg_parts))

        ef_val = "1" if detail["equal_flag"] else "0"
        self._eq_flag_label.set_text(f"EQ_Flag: {ef_val}")

        env_surface = _render_env_grid(self.view_api, regs)
        self._env_image.set_image(env_surface)

        # ── 重量更新：genome 变化时立即刷新；PC 变化时节流刷新 ──
        if genome_changed:
            self._cached_hex_lines = _genome_hex_dump(genome)
            self._cached_asm_lines = disassemble_with_labels(genome)
            self._copy_btn_genome = genome
            self._hex_box.set_text(_hex_to_html(self._cached_hex_lines, pc))
            self._asm_box.set_text(_asm_to_html(self._cached_asm_lines, pc))
            self._last_genome = genome_bytes
            self._last_pc = pc
            self._pc_update_counter = 0
        elif pc != self._last_pc:
            # PC 变化但 genome 不变：节流，每 10 帧刷新一次高亮
            self._pc_update_counter += 1
            if self._pc_update_counter >= 10:
                self._hex_box.set_text(_hex_to_html(self._cached_hex_lines, pc))
                self._asm_box.set_text(_asm_to_html(self._cached_asm_lines, pc))
                self._last_pc = pc
                self._pc_update_counter = 0

    def _create_log_tab(self, panel_w: int, panel_h: int) -> None:
        """创建 Log Tab 内容。"""
        # 过滤按钮
        fx = 5
        for name in ["All", "Birth", "Death"]:
            btn = pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(fx, 5, 50, 18),
                text=name,
                manager=self.manager,
                container=self._content_container,
                object_id=pygame_gui.core.ObjectID(
                    class_id=None, object_id="#filter_button"
                ),
            )
            self._filter_buttons.append(btn)
            fx += 55

        # 日志文本框
        log_h = panel_h - TAB_BAR_H - 30
        self._log_box = pygame_gui.elements.UITextBox(
            html_text="",
            relative_rect=pygame.Rect(5, 28, panel_w - 10, max(log_h, 1)),
            manager=self.manager,
            container=self._content_container,
            object_id=pygame_gui.core.ObjectID(
                class_id=None, object_id="#log_textbox"
            ),
        )

    def _update_tab_visibility(self) -> None:
        """根据当前 Tab 显示/隐藏内容。"""
        # Stats
        is_stats = self.active_tab == 0
        if self._stats_chart is not None:
            self._stats_chart.visible = is_stats
        for btn in self._stats_sub_buttons:
            btn.visible = is_stats

        # Inspector: 占位标签 vs 详情组件互斥显示
        is_inspector = self.active_tab == 1
        has_detail = self._last_org_id is not None
        if self._placeholder_label is not None:
            self._placeholder_label.visible = is_inspector and not has_detail
        for elem in self._inspector_elements:
            elem.visible = is_inspector and has_detail

        # Log
        if self._log_box is not None:
            self._log_box.visible = self.active_tab == 2
        for btn in self._filter_buttons:
            btn.visible = self.active_tab == 2

    def set_active_tab(self, tab_idx: int) -> None:
        """切换活动 Tab。"""
        if 0 <= tab_idx < len(TAB_NAMES):
            self.active_tab = tab_idx
            self._update_tab_visibility()
            if tab_idx == 2:
                self._refresh_log_text()

    def handle_button(self, ui_element: pygame_gui.core.UIElement) -> None:
        """处理按钮点击事件。"""
        # Tab 按钮
        for i, btn in enumerate(self._tab_buttons):
            if ui_element == btn:
                self.set_active_tab(i)
                return

        # Stats 子图表按钮
        for i, btn in enumerate(self._stats_sub_buttons):
            if ui_element == btn:
                self._stats_sub_index = i
                self._update_stats_sub_button_style()
                return

        # 过滤按钮
        filter_names = ["all", "birth", "death"]
        for i, btn in enumerate(self._filter_buttons):
            if ui_element == btn:
                self._log_filter = filter_names[i]
                self._refresh_log_text()
                return

        # Copy ASM 按钮
        if ui_element == self._copy_btn and self._copy_btn_genome is not None:
            asm = disassemble_with_labels(self._copy_btn_genome)
            text = "\n".join(asm)
            try:
                pygame.scrap.init()
                pygame.scrap.put(pygame.SCRAP_TEXT, text.encode("utf-8"))
            except Exception:
                pass
            if self._copy_btn is not None:
                self._copy_btn.set_text("Copied!")

    def update_stats(
        self,
        alive: int,
        avg_energy: float,
        opcode_total: dict[int, int] | None = None,
        opcode_org: dict[int, int] | None = None,
    ) -> None:
        """更新统计数据。"""
        self._population_history.append(alive)
        self._energy_history.append(avg_energy)

        # 指令统计：追加历史
        if opcode_total is not None and opcode_org is not None:
            for op in self._legal_opcodes:
                self._opcode_total_history[op].append(opcode_total.get(op, 0))
                self._opcode_org_history[op].append(opcode_org.get(op, 0))

        if self.active_tab == 0 and self._stats_chart is not None:
            panel_rect = self._content_container.rect
            chart_w = panel_rect.width - 20
            chart_h = panel_rect.height - 54  # 54 = 按钮行24 + 间距30
            if chart_w > 0 and chart_h > 0:
                chart_surface = _render_stats_chart(
                    self._population_history,
                    self._energy_history,
                    self._opcode_total_history,
                    self._opcode_org_history,
                    self._opcode_colors,
                    self._mnemonic_by_code,
                    self._legal_opcodes,
                    self._stats_sub_index,
                    chart_w,
                    chart_h,
                )
                self._stats_chart.set_image(chart_surface)
                self._stats_chart.set_dimensions((chart_w, chart_h))

    def update(self) -> None:
        """每帧调用：批量刷新脏日志。"""
        if self._log_dirty and self.active_tab == 2:
            self._refresh_log_text()

    def update_inspector(self, selected_org_id: int | None) -> None:
        """更新 Inspector Tab（增量模式）。"""
        # 非 Inspector Tab 时，仅响应选中生物变化（切换 Tab 时需同步状态）
        if self.active_tab != 1 and selected_org_id == self._last_org_id:
            return

        panel_rect = self._content_container.rect
        panel_w = panel_rect.width
        panel_h = panel_rect.height

        # 无生物选中
        if selected_org_id is None:
            self._last_org_id = None
            self._last_genome = b""
            self._last_pc = -1
            if self._inspector_built:
                self._placeholder_label.set_text("Click an organism to inspect")
            self._update_tab_visibility()
            return

        # 生物已死亡
        detail = self.view_api.get_organism_detail_safe(selected_org_id)
        if detail is None:
            self._last_org_id = None
            self._last_genome = b""
            self._last_pc = -1
            if self._inspector_built:
                self._placeholder_label.set_text("Organism no longer alive")
            self._update_tab_visibility()
            return

        # 首次创建组件
        if not self._inspector_built:
            self._build_inspector_widgets(panel_w, panel_h)

        # 增量更新内容
        org_changed = selected_org_id != self._last_org_id
        self._last_org_id = selected_org_id
        if org_changed:
            # 换了生物，强制 genome 视为变化以刷新 Hex/ASM
            self._last_genome = b""
        self._update_inspector_detail(detail)
        self._update_tab_visibility()

    def add_log_event(self, event_type: str, data: dict) -> None:
        """添加日志事件。仅追加到 deque 并标记脏位，不直接更新文本框。"""
        color = Theme.SUCCESS if event_type == "birth" else Theme.WARNING
        tick = data.get("tick", 0)
        org_id = data.get("org_id", "?")
        ex, ey = data.get("x", "?"), data.get("y", "?")
        text = f"[Tick:{tick}] [{event_type.upper()}] Org #{org_id} at ({ex},{ey})"
        self._log_entries.append((text, color))
        self._log_dirty = True

    def _refresh_log_text(self) -> None:
        """重建日志文本框（过滤变化时）。仅渲染最近 _LOG_DISPLAY_LIMIT 条。"""
        if self._log_box is None:
            return
        parts: list[str] = []
        # 只取最近 _LOG_DISPLAY_LIMIT 条过滤后的结果
        for text, color in reversed(self._log_entries):
            if self._log_filter != "all":
                event_tag = f"[{self._log_filter.upper()}]"
                if event_tag not in text:
                    continue
            r, g, b = color
            parts.append(f'<font color="#{r:02X}{g:02X}{b:02X}">{_escape(text)}</font><br>')
            if len(parts) >= self._LOG_DISPLAY_LIMIT:
                break
        # parts 是倒序收集的，需要反转为时间正序
        parts.reverse()
        self._log_box.set_text("".join(parts))
        if self._log_box.scroll_bar is not None:
            self._log_box.scroll_bar.set_scroll_from_start_percentage(1.0)
        self._log_dirty = False

    def rebuild_layout(self, win_w: int, win_h: int) -> None:
        """窗口缩放时重建右侧面板布局。"""
        panel_w = int(win_w * RIGHT_PANEL_RATIO)
        panel_h = win_h - TOP_BAR_H
        panel_rect = pygame.Rect(win_w - panel_w, TOP_BAR_H, panel_w, panel_h)
        self._panel.set_dimensions((panel_w, panel_h))
        self._panel.set_relative_position(panel_rect.topleft)

        # Tab 按钮重新排列
        tab_w = panel_w // len(TAB_NAMES)
        for i, btn in enumerate(self._tab_buttons):
            btn.set_dimensions((tab_w, TAB_BAR_H))
            btn.set_relative_position((i * tab_w, 0))

        # 内容容器
        content_w = panel_w
        content_h = panel_h - TAB_BAR_H
        self._content_container.set_dimensions((content_w, content_h))
        self._content_container.set_relative_position((0, TAB_BAR_H))

        # Stats 图表重建
        if self._stats_chart is not None:
            chart_w = content_w - 20
            chart_h = content_h - 54  # 54 = 按钮行24 + 间距30
            if chart_w > 0 and chart_h > 0:
                chart_surface = _render_stats_chart(
                    self._population_history,
                    self._energy_history,
                    self._opcode_total_history,
                    self._opcode_org_history,
                    self._opcode_colors,
                    self._mnemonic_by_code,
                    self._legal_opcodes,
                    self._stats_sub_index,
                    chart_w,
                    chart_h,
                )
                self._stats_chart.set_image(chart_surface)
                self._stats_chart.set_dimensions((chart_w, chart_h))
                self._stats_chart.set_relative_position((10, 30))

        # Stats 子按钮重建
        btn_w = content_w // len(self._stats_sub_names)
        for i, btn in enumerate(self._stats_sub_buttons):
            btn.set_dimensions((btn_w, 24))
            btn.set_relative_position((i * btn_w, 0))

        # Log 文本框重建
        if self._log_box is not None:
            log_h = content_h - 28
            self._log_box.set_dimensions((content_w - 10, max(log_h, 1)))
            self._log_box.set_relative_position((5, 28))

        # Inspector 组件需要在下次 update_inspector 时重建
        for elem in self._inspector_elements:
            elem.kill()
        self._inspector_elements.clear()
        if self._placeholder_label is not None:
            self._placeholder_label.kill()
            self._placeholder_label = None
        self._inspector_built = False
