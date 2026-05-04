"""主应用 - Pygame初始化、游戏循环、事件分发与渲染编排"""

from __future__ import annotations

import numpy as np
import pygame

from cyberterrarium.facade.api import ControlAPI, ViewAPI
from cyberterrarium.model.config import WORLD_HEIGHT, WORLD_WIDTH
from cyberterrarium.view.camera import Camera
from cyberterrarium.view.layout import (
    FONT_LG,
    FONT_MD,
    FONT_SM,
    LEFT_VIEWPORT,
    RIGHT_PANEL,
    SCREEN_H,
    SCREEN_W,
    Theme,
)
from cyberterrarium.view.renderer import MATERIAL_LUT, FrameRenderer
from cyberterrarium.view.widgets import RightPanel, TopBar


class CyberTerrariumUI:
    """赛博生态缸主界面。"""

    def __init__(self, view_api: ViewAPI, control_api: ControlAPI) -> None:
        self.view_api = view_api
        self.control_api = control_api
        self.renderer = FrameRenderer(view_api)
        self.camera = Camera(WORLD_HEIGHT, WORLD_WIDTH)
        self.top_bar = TopBar()
        self.right_panel = RightPanel(view_api)
        self.selected_org_id: int | None = None
        self.running: bool = True
        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.fps: float = 60.0
        # 字体（init_pygame中初始化）
        self.font_sm: pygame.font.Font | None = None
        self.font_md: pygame.font.Font | None = None
        self.font_lg: pygame.font.Font | None = None
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
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("CyberTerrarium")
        self.font_sm = pygame.font.SysFont(Theme.FONT_NAME, FONT_SM)
        self.font_md = pygame.font.SysFont(Theme.FONT_NAME, FONT_MD)
        self.font_lg = pygame.font.SysFont(Theme.FONT_NAME, FONT_LG)
        self.top_bar.init_fonts(self.font_sm, self.font_md)
        self.right_panel.init_fonts(self.font_sm, self.font_md)

    def run(self) -> None:
        self.init_pygame()
        while self.running:
            self._handle_events()
            self._update_simulation()
            self._render_frame()
            self.fps = self.clock.get_fps()
            self.clock.tick(60)
        pygame.quit()

    # ── 事件处理 ──

    def _handle_events(self) -> None:
        ctrl = self.control_api.ctrl
        is_debug = ctrl.mode == "DEBUG"

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                self._on_key(event.key, is_debug, ctrl)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._on_mouse_down(event, is_debug, ctrl)

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
            self._flash_phase("PHASE 3: REPRODUCTION")
        elif key == pygame.K_F5 and is_debug:
            self.control_api.step_full_tick()
            self._flash_phase("FULL TICK")
        elif key == pygame.K_d:
            if ctrl.mode == "DEBUG":
                self.control_api.exit_debug_mode()
            else:
                self.control_api.enter_debug_mode()
        # WASD平移
        elif key == pygame.K_w:
            self.camera.pan(0, 30)
        elif key == pygame.K_s:
            self.camera.pan(0, -30)
        elif key == pygame.K_a:
            self.camera.pan(30, 0)
        elif key == pygame.K_d:
            pass  # D键已被调试模式占用，平移功能由右键拖拽提供

    def _on_mouse_down(self, event, is_debug: bool, ctrl) -> None:
        mx, my = event.pos
        vx, vy, vw, vh = LEFT_VIEWPORT
        px, py, pw, ph = RIGHT_PANEL

        if event.button == 1:  # 左键
            # 顶栏
            if my < 40:
                self.top_bar.handle_click(mx, my, SCREEN_W)
            # 视口内点击选生物
            elif vx <= mx < vx + vw and vy <= my < vy + vh:
                self._select_organism_at(mx - vx, my - vy)
            # 右侧面板
            elif px <= mx < px + pw and py <= my < py + ph:
                self.right_panel.handle_click(mx, my)

        elif event.button == 3:  # 右键 - 开始拖拽
            self._right_dragging = True
            self._last_mouse = (mx, my)

        elif event.button == 4:  # 滚轮上
            if vx <= mx < vx + vw and vy <= my < vy + vh:
                self.camera.zoom_at(mx - vx, my - vy, 1.2)
        elif event.button == 5 and vx <= mx < vx + vw and vy <= my < vy + vh:
            self.camera.zoom_at(mx - vx, my - vy, 1 / 1.2)

    def _on_mouse_up(self, event) -> None:
        if event.button == 1:
            self.top_bar.handle_release()
        elif event.button == 3:
            self._right_dragging = False

    def _on_mouse_motion(self, event) -> None:
        mx, my = event.pos
        if self._right_dragging:
            dx = mx - self._last_mouse[0]
            dy = my - self._last_mouse[1]
            self.camera.pan(-dx, -dy)
            self._last_mouse = (mx, my)
        if pygame.mouse.get_pressed()[0]:
            self.top_bar.handle_drag(mx)

    def _on_mouse_wheel(self, event) -> None:
        mx, my = pygame.mouse.get_pos()
        vx, vy, vw, vh = LEFT_VIEWPORT
        if vx <= mx < vx + vw and vy <= my < vy + vh:
            factor = 1.15 if event.y > 0 else 1 / 1.15
            self.camera.zoom_at(mx - vx, my - vy, factor)

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
        # 自动切到Inspector Tab
        if self.selected_org_id is not None:
            self.right_panel.active_tab = 1

    def _flash_phase(self, text: str) -> None:
        self._last_phase_text = text
        self._phase_flash_until = pygame.time.get_ticks() + 1000

    # ── 仿真更新 ──

    def _update_simulation(self) -> None:
        ctrl = self.control_api.ctrl
        if ctrl.mode == "CONTINUOUS" and not ctrl.is_paused:
            budget = (1.0 / 60.0) * 0.8
            for _ in range(self.top_bar.ticks_per_frame):
                self.control_api.advance_continuous_frame(budget / self.top_bar.ticks_per_frame)
        # 更新统计
        stats = self.view_api.get_global_stats()
        alive = stats["alive"]
        energies = self.view_api.get_organism_energies_array()
        avg_e = float(np.mean(energies)) if len(energies) > 0 else 0.0
        self.right_panel.stats.update(alive, avg_e)

    # ── 渲染 ──

    def _render_frame(self) -> None:
        self.screen.fill(Theme.BG)
        self._render_viewport()
        self._render_top_bar()
        self._render_right_panel()
        pygame.display.flip()

    def _render_viewport(self) -> None:
        vx, vy, vw, vh = LEFT_VIEWPORT
        # 同步视图模式
        self.renderer.mode = self.top_bar.view_mode

        # 生成帧
        pixel_array = self.renderer.render()  # (W, H, 3) uint8
        small_surface = pygame.surfarray.make_surface(pixel_array)

        # 缩放
        scaled_w = int(self.camera.grid_w * self.camera.zoom)
        scaled_h = int(self.camera.grid_h * self.camera.zoom)
        big_surface = pygame.transform.scale(small_surface, (scaled_w, scaled_h))

        # 贴图到视口区域
        self.screen.set_clip(pygame.Rect(vx, vy, vw, vh))
        self.screen.blit(big_surface, (vx - int(self.camera.cam_x), vy - int(self.camera.cam_y)))
        self.screen.set_clip(None)

        # HUD叠层
        self._render_viewport_hud(vx, vy, vw, vh)

    def _render_viewport_hud(self, vx: int, vy: int, vw: int, vh: int) -> None:
        assert self.font_sm is not None
        # 阶段提示（调试模式闪烁）
        now = pygame.time.get_ticks()
        if now < self._phase_flash_until:
            txt = self.font_lg.render(self._last_phase_text, True, Theme.HIGHLIGHT)
            bg = pygame.Surface((txt.get_width() + 10, txt.get_height() + 6), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            self.screen.blit(bg, (vx + 8, vy + 8))
            self.screen.blit(txt, (vx + 13, vy + 11))

        # 图例（左下角）
        lx = vx + 8
        ly = vy + vh - 8 - 5 * 16
        names = ["Empty", "Nutrient", "Enzyme", "Toxin", "Signal", "Organism"]
        for i, name in enumerate(names):
            color = tuple(MATERIAL_LUT[i]) if i < 5 else (255, 255, 255)
            pygame.draw.rect(self.screen, color, (lx, ly, 10, 10))
            txt = self.font_sm.render(name, True, Theme.TEXT)
            self.screen.blit(txt, (lx + 14, ly - 2))
            ly += 16

        # 选中生物闪烁框
        if self.selected_org_id is not None:
            detail = self.view_api.get_organism_detail_safe(self.selected_org_id)
            if detail is not None:
                org_x = detail["regs"][5]  # DP_X
                org_y = detail["regs"][6]  # DP_Y
                sx = vx + int(org_x * self.camera.zoom - self.camera.cam_x)
                sy = vy + int(org_y * self.camera.zoom - self.camera.cam_y)
                cell = int(self.camera.zoom)
                if (pygame.time.get_ticks() // 500) % 2 == 0:
                    pygame.draw.rect(self.screen, (255, 255, 255), (sx, sy, cell, cell), 1)

    def _render_top_bar(self) -> None:
        stats = self.view_api.get_global_stats()
        self.top_bar.render(
            self.screen,
            mode=self.control_api.ctrl.mode,
            is_paused=self.control_api.ctrl.is_paused,
            fps=self.fps,
            tick=stats["tick"],
            alive=stats["alive"],
            cap=stats["cap"],
        )

    def _render_right_panel(self) -> None:
        self.right_panel.render(self.screen, self.selected_org_id)

    # ── 事件回调 ──

    def _on_sim_event(self, event_type: str, data: dict) -> None:
        self.right_panel.log.add_event(event_type, data)
