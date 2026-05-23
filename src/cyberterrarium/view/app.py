"""主应用 - pygame_gui 集成、锚点布局、事件分流与渲染编排"""

from __future__ import annotations

import numpy as np
import pygame
import pygame_gui

from cyberterrarium.facade.api import ControlAPI, ViewAPI
from cyberterrarium.model.config import WORLD_HEIGHT, WORLD_WIDTH
from cyberterrarium.view.camera import Camera
from cyberterrarium.view.layout import (
    INIT_SCREEN_H,
    INIT_SCREEN_W,
    RIGHT_PANEL_RATIO,
    THEME_JSON_PATH,
    TOP_BAR_H,
    Theme,
)
from cyberterrarium.view.renderer import FrameRenderer
from cyberterrarium.view.widgets import RightPanel, TopBar


class CyberTerrariumUI:
    """赛博生态缸主界面。"""

    def __init__(self, view_api: ViewAPI, control_api: ControlAPI) -> None:
        self.view_api = view_api
        self.control_api = control_api
        self.renderer = FrameRenderer(view_api)
        self.camera = Camera(WORLD_HEIGHT, WORLD_WIDTH)
        self.manager: pygame_gui.UIManager | None = None
        self.top_bar: TopBar | None = None
        self.right_panel: RightPanel | None = None
        self.selected_org_id: int | None = None
        self.running: bool = True
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.fps: float = 60.0
        # 拖拽状态
        self._right_dragging: bool = False
        self._last_mouse: tuple[int, int] = (0, 0)
        # HUD闪烁
        self._phase_flash_until: int = 0
        self._last_phase_text: str = ""
        # 事件监听
        self.control_api.ctrl.add_event_listener(self._on_sim_event)

    def init_pygame(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode(
            (INIT_SCREEN_W, INIT_SCREEN_H), pygame.RESIZABLE
        )
        pygame.display.set_caption("CyberTerrarium")

        self.manager = pygame_gui.UIManager(
            (INIT_SCREEN_W, INIT_SCREEN_H), theme_path=THEME_JSON_PATH
        )

        # 创建顶栏
        self.top_bar = TopBar(self.manager)

        # 创建右侧面板
        self.right_panel = RightPanel(self.manager, self.view_api)

    def _calc_viewport_rect(self, win_w: int, win_h: int) -> pygame.Rect:
        """计算视口区域的矩形（顶栏下方、右面板左侧）。"""
        panel_w = int(win_w * RIGHT_PANEL_RATIO)
        return pygame.Rect(0, TOP_BAR_H, win_w - panel_w, win_h - TOP_BAR_H)

    def _calc_right_panel_rect(self, win_w: int, win_h: int) -> pygame.Rect:
        """计算右面板区域的矩形。"""
        panel_w = int(win_w * RIGHT_PANEL_RATIO)
        return pygame.Rect(win_w - panel_w, TOP_BAR_H, panel_w, win_h - TOP_BAR_H)

    def run(self) -> None:
        self.init_pygame()
        while self.running:
            time_delta = self.clock.tick(60) / 1000.0
            self._handle_events()
            self._update_simulation()
            self._render_frame()
            assert self.manager is not None
            self.manager.update(time_delta)
            self.manager.draw_ui(self.screen)
            pygame.display.flip()
            self.fps = self.clock.get_fps()
        pygame.quit()

    # ── 事件处理 ──

    def _handle_events(self) -> None:
        assert self.manager is not None
        ctrl = self.control_api.ctrl
        is_debug = ctrl.mode == "DEBUG"

        for event in pygame.event.get():
            # pygame_gui 先处理
            self.manager.process_events(event)

            if event.type == pygame.QUIT:
                self.running = False
                return

            # 处理 pygame_gui 自定义事件
            self._handle_ui_event(event)

            # 窗口缩放
            if event.type == pygame.VIDEORESIZE:
                self.screen = pygame.display.set_mode(
                    (event.w, event.h), pygame.RESIZABLE
                )
                self.manager.set_window_resolution((event.w, event.h))
                self._rebuild_layout(event.w, event.h)

            # 游戏事件仅在鼠标不悬停 UI 时传递
            if not self.manager.hovering_any_ui_element:
                self._handle_game_event(event, is_debug, ctrl)

    def _handle_ui_event(self, event: pygame.event.Event) -> None:
        """处理 pygame_gui 产生的 UI 事件。"""
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            ui_element = event.ui_element
            if self.top_bar is not None:
                self.top_bar.handle_button(ui_element)
            if self.right_panel is not None:
                self.right_panel.handle_button(ui_element)
        elif event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
            if self.top_bar is not None:
                self.top_bar.handle_slider(event.ui_element, event.value)

    def _handle_game_event(
        self, event: pygame.event.Event, is_debug: bool, ctrl
    ) -> None:
        if event.type == pygame.KEYDOWN:
            self._on_key(event.key, is_debug, ctrl)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._on_mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._on_mouse_up(event)
        elif event.type == pygame.MOUSEMOTION:
            self._on_mouse_motion(event)
        elif event.type == pygame.MOUSEWHEEL:
            self._on_mouse_wheel(event)

    def _on_key(self, key: int, is_debug: bool, ctrl) -> None:
        if key == pygame.K_ESCAPE:
            if is_debug:
                self.control_api.exit_debug_mode()
            else:
                self.running = False
        elif key == pygame.K_SPACE:
            if not is_debug:
                self.control_api.toggle_pause()
        elif key == pygame.K_F1 and is_debug:
            self.control_api.step_physics()
            self._flash_phase("PHASE 1: PHYSICS")
        elif key == pygame.K_F2 and is_debug:
            self.control_api.step_life()
            self._flash_phase("PHASE 2: LIFE")
        elif key == pygame.K_F3 and is_debug:
            self.control_api.step_reproduction()
            self._flash_phase("PHASE 3: REPRO + SETTLE")
        elif key == pygame.K_F5 and is_debug:
            self.control_api.step_full_tick()
            self._flash_phase("FULL TICK")
        elif key == pygame.K_d:
            if ctrl.mode == "DEBUG":
                self.control_api.exit_debug_mode()
            else:
                self.control_api.enter_debug_mode()
        elif key == pygame.K_w:
            self.camera.pan(0, 30)
        elif key == pygame.K_s:
            self.camera.pan(0, -30)
        elif key == pygame.K_a:
            self.camera.pan(30, 0)

    def _on_mouse_down(self, event: pygame.event.Event) -> None:
        assert self.manager is not None
        mx, my = event.pos
        vr = self._calc_viewport_rect(*self.screen.get_size())

        if event.button == 1:  # 左键 — 在视口内选择生物
            if vr.collidepoint(mx, my):
                self._select_organism_at(mx - vr.x, my - vr.y)

        elif event.button == 3:  # 右键 — 开始拖拽
            self._right_dragging = True
            self._last_mouse = (mx, my)

        elif event.button == 4:  # 滚轮上
            if vr.collidepoint(mx, my):
                self.camera.zoom_at(mx - vr.x, my - vr.y, 1.2)
        elif event.button == 5 and vr.collidepoint(mx, my):  # 滚轮下
            self.camera.zoom_at(mx - vr.x, my - vr.y, 1 / 1.2)

    def _on_mouse_up(self, event: pygame.event.Event) -> None:
        if event.button == 3:
            self._right_dragging = False

    def _on_mouse_motion(self, event: pygame.event.Event) -> None:
        mx, my = event.pos
        if self._right_dragging:
            dx = mx - self._last_mouse[0]
            dy = my - self._last_mouse[1]
            self.camera.pan(-dx, -dy)
            self._last_mouse = (mx, my)

    def _on_mouse_wheel(self, event: pygame.event.Event) -> None:
        assert self.manager is not None
        mx, my = pygame.mouse.get_pos()
        vr = self._calc_viewport_rect(*self.screen.get_size())
        if vr.collidepoint(mx, my):
            factor = 1.15 if event.y > 0 else 1 / 1.15
            self.camera.zoom_at(mx - vr.x, my - vr.y, factor)

    def _select_organism_at(self, sx: int, sy: int) -> None:
        gy, gx = self.camera.screen_to_grid(sx, sy)
        positions = self.view_api.get_organism_positions_array()
        ids = self.view_api.get_organism_ids_array()
        if len(positions) > 0:
            match = (positions[:, 0] == gy) & (positions[:, 1] == gx)
            matching = ids[match]
            self.selected_org_id = int(matching[0]) if len(matching) > 0 else None
        else:
            self.selected_org_id = None
        # 自动切到 Inspector Tab
        if self.selected_org_id is not None and self.right_panel is not None:
            self.right_panel.set_active_tab(1)

    def _flash_phase(self, text: str) -> None:
        self._last_phase_text = text
        self._phase_flash_until = pygame.time.get_ticks() + 1000

    # ── 仿真更新 ──

    def _update_simulation(self) -> None:
        assert self.top_bar is not None and self.right_panel is not None
        ctrl = self.control_api.ctrl
        if ctrl.mode == "CONTINUOUS" and not ctrl.is_paused:
            budget = (1.0 / 60.0) * 0.8
            for _ in range(self.top_bar.ticks_per_frame):
                self.control_api.advance_continuous_frame(
                    budget / self.top_bar.ticks_per_frame
                )
        # 更新统计
        stats = self.view_api.get_global_stats()
        alive = stats["alive"]
        energies = self.view_api.get_organism_energies_array()
        avg_e = float(np.mean(energies)) if len(energies) > 0 else 0.0
        self.right_panel.update_stats(alive, avg_e)

        # 更新顶栏信息
        self.top_bar.update_info(
            mode=ctrl.mode,
            is_paused=ctrl.is_paused,
            fps=self.fps,
            tick=stats["tick"],
            alive=alive,
            cap=stats["cap"],
        )

        # 更新 Inspector
        self.right_panel.update_inspector(self.selected_org_id)

        # 批量刷新脏日志
        self.right_panel.update()

    # ── 渲染 ──

    def _render_frame(self) -> None:
        self.screen.fill(Theme.BG)
        self._render_viewport()
        self._render_viewport_hud()

    def _render_viewport(self) -> None:
        # 同步视图模式
        if self.top_bar is not None:
            self.renderer.mode = self.top_bar.view_mode

        # 生成帧
        pixel_array = self.renderer.render()  # (W, H, 3) uint8
        small_surface = pygame.surfarray.make_surface(pixel_array)

        # 缩放
        scaled_w = int(self.camera.grid_w * self.camera.zoom)
        scaled_h = int(self.camera.grid_h * self.camera.zoom)
        big_surface = pygame.transform.scale(
            small_surface, (max(scaled_w, 1), max(scaled_h, 1))
        )

        # 贴图到视口区域（用裁剪防止溢出到右面板/顶栏）
        vr = self._calc_viewport_rect(*self.screen.get_size())
        self.screen.set_clip(vr)
        self.screen.blit(
            big_surface, (vr.x - int(self.camera.cam_x), vr.y - int(self.camera.cam_y))
        )
        self.screen.set_clip(None)

    def _render_viewport_hud(self) -> None:
        """在视口上绘制 HUD 叠层（图例、选中框等）。"""
        vr = self._calc_viewport_rect(*self.screen.get_size())

        # 选中生物闪烁框
        if self.selected_org_id is not None:
            detail = self.view_api.get_organism_detail_safe(self.selected_org_id)
            if detail is not None:
                org_x = detail["regs"][5]  # DP_X
                org_y = detail["regs"][6]  # DP_Y
                sx = vr.x + int(org_x * self.camera.zoom - self.camera.cam_x)
                sy = vr.y + int(org_y * self.camera.zoom - self.camera.cam_y)
                cell = int(self.camera.zoom)
                if (pygame.time.get_ticks() // 500) % 2 == 0:
                    pygame.draw.rect(self.screen, (255, 255, 255), (sx, sy, cell, cell), 1)

    def _rebuild_layout(self, win_w: int, win_h: int) -> None:
        """窗口缩放时重建布局。"""
        assert self.manager is not None
        assert self.top_bar is not None
        assert self.right_panel is not None

        # 更新右侧面板（视口无需特殊处理，每帧自动计算 rect）
        self.right_panel.rebuild_layout(win_w, win_h)

    # ── 事件回调 ──

    def _on_sim_event(self, event_type: str, data: dict) -> None:
        if self.right_panel is not None:
            self.right_panel.add_log_event(event_type, data)
