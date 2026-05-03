"""外观层API - 视图只读接口与控制写接口"""

from __future__ import annotations

import numpy as np

from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.organism import Organism


class ViewAPI:
    """只读接口：为视图层提供数据拉取能力。"""

    def __init__(self, controller: SimulationController) -> None:
        self.ctrl = controller

    def get_chemical_grid_ref(self) -> np.ndarray:
        """获取世界化学物质矩阵引用（零拷贝，仅渲染使用）。"""
        return self.ctrl.world.grid

    def get_organism_positions_array(self) -> np.ndarray:
        """获取存活生物坐标矩阵 (N, 2) int16。"""
        alive = self.ctrl.population.get_alive_list()
        if not alive:
            return np.empty((0, 2), dtype=np.int16)
        positions = np.array(
            [[org.regs[Organism.DP_X], org.regs[Organism.DP_Y]] for org in alive],
            dtype=np.int16,
        )
        return positions

    def get_global_stats(self) -> dict:
        return {
            "tick": self.ctrl.current_tick,
            "alive": self.ctrl.population.alive_count,
            "cap": self.ctrl.population.max_cap,
        }

    def get_organism_detail_safe(self, org_id: int) -> dict | None:
        """获取单个生物的深拷贝快照（调试专用，安全隔离）。"""
        org = self.ctrl.population.pool[org_id]
        if org is None or not org.alive:
            return None
        return {
            "id": org.org_id,
            "age": org.age,
            "pc": org.pc,
            "energy": org.energy,
            "regs": org.regs.copy(),
            "equal_flag": org.equal_flag,
            "genome_bytes": bytearray(org.genome),
        }

    def get_phase_state(self) -> str:
        if self.ctrl.mode == "CONTINUOUS" and not self.ctrl.is_paused:
            return "连续运行中"
        return f"调试挂起 | Tick: {self.ctrl.current_tick}"


class ControlAPI:
    """只写接口：接收用户控制指令。"""

    def __init__(self, controller: SimulationController) -> None:
        self.ctrl = controller

    def toggle_pause(self) -> None:
        self.ctrl.is_paused = not self.ctrl.is_paused

    def enter_debug_mode(self) -> None:
        self.ctrl.mode = "DEBUG"
        self.ctrl.is_paused = True

    def exit_debug_mode(self) -> None:
        self.ctrl.mode = "CONTINUOUS"
        self.ctrl.is_paused = False

    def advance_continuous_frame(self, budget_seconds: float) -> None:
        import time

        if self.ctrl.mode != "CONTINUOUS" or self.ctrl.is_paused:
            return
        start = time.perf_counter()
        while time.perf_counter() - start < budget_seconds:
            self.ctrl.run_one_full_tick()

    def step_physics(self) -> None:
        if self.ctrl.mode == "DEBUG":
            self.ctrl.execute_phase_1()

    def step_life(self) -> None:
        if self.ctrl.mode == "DEBUG":
            self.ctrl.execute_phase_2()

    def step_reproduction(self) -> None:
        if self.ctrl.mode == "DEBUG":
            self.ctrl.execute_phase_3()

    def step_full_tick(self) -> None:
        if self.ctrl.mode == "DEBUG":
            self.ctrl.execute_phase_1()
            self.ctrl.execute_phase_2()
            self.ctrl.execute_phase_3()
