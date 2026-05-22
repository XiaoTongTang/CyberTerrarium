"""仿真控制器 - 系统调度核心，状态机管理者"""

import random

import numpy as np

from cyberterrarium.model.config import (
    AGE_LIMIT,
    C_BASE,
    C_PER_INST,
    E_BIRTH,
    MAX_GENOME_LENGTH,
    MIN_GENOME_LENGTH,
    NUTRIENT_LIFE,
    NUTRIENT_SPAWN_RATE,
    REPRO_ENERGY_MULTIPLIER,
)
from cyberterrarium.model.fingerprint import compute_fingerprint
from cyberterrarium.model.mutation import apply_mutations
from cyberterrarium.model.organism import Organism
from cyberterrarium.model.population import Population
from cyberterrarium.model.vm import VirtualMachine
from cyberterrarium.model.world import World


def np_random_mask(base_mask: np.ndarray, probability: float) -> np.ndarray:
    """在base_mask为True的位置中，按概率生成随机掩码。"""
    rand = np.random.random(base_mask.shape)
    return base_mask & (rand < probability)


class SimulationController:
    def __init__(self, world: World, population: Population) -> None:
        self.world = world
        self.population = population
        self.vm = VirtualMachine()
        self.current_tick = 0
        self.is_paused = False
        self.mode = "CONTINUOUS"  # CONTINUOUS | DEBUG
        self._spawn_queue: list[dict] = []
        # 零拷贝渲染缓存
        self._cached_alive_positions_yx: np.ndarray = np.empty((0, 2), dtype=np.int16)
        self._cached_alive_energies: np.ndarray = np.empty(0, dtype=np.int32)
        self._cached_alive_ids: np.ndarray = np.empty(0, dtype=np.int32)
        # 事件系统
        self._event_listeners: list = []

    def run_one_full_tick(self) -> None:
        self.execute_phase_1()
        self.execute_phase_2()
        self.execute_phase_repro()
        self.execute_phase_3()

    def execute_phase_1(self) -> None:
        """物理与环境阶段：种植反应 + 信号衰减 + 营养衰减 + 酶衰减 + 营养生成"""
        grid = self.world.grid

        # Step 0: 种植反应
        nutrient_mask = grid == World.NUTRIENT
        enzyme_mask = grid == World.ENZYME
        nutrient_influence = self._dilate_4(nutrient_mask)
        triggered_enzymes = enzyme_mask & nutrient_influence

        if triggered_enzymes.any():
            enzyme_influence = self._dilate_4(triggered_enzymes)
            trigger_nutrients = nutrient_mask & enzyme_influence
            new_nutrient_area = self._dilate_3x3(trigger_nutrients)
            grid[triggered_enzymes] = World.EMPTY
            self.world.enzyme_life[triggered_enzymes] = 0
            can_overwrite = (
                (grid == World.EMPTY)
                | (grid == World.NUTRIENT)
                | (grid == World.ENZYME)
            )
            write_mask = new_nutrient_area & can_overwrite
            grid[write_mask] = World.NUTRIENT
            self.world.nutrient_life[write_mask] = NUTRIENT_LIFE

        # Step 1: 信号衰减
        mask = self.world.signal_life > 0
        self.world.signal_life[mask] -= 1
        expired = (self.world.signal_life == 0) & (grid == World.SIGNAL)
        grid[expired] = World.EMPTY

        # Step 2: 营养衰减
        nmask = self.world.nutrient_life > 0
        self.world.nutrient_life[nmask] -= 1
        n_expired = (self.world.nutrient_life == 0) & (grid == World.NUTRIENT)
        grid[n_expired] = World.EMPTY

        # Step 3: 酶环境衰减
        emask = self.world.enzyme_life > 0
        self.world.enzyme_life[emask] -= 1
        e_expired = (self.world.enzyme_life == 0) & (grid == World.ENZYME)
        grid[e_expired] = World.EMPTY

        # Step 4: 营养生成
        self.current_tick += 1
        if self.current_tick % NUTRIENT_LIFE == 1:
            empty_mask = grid == World.EMPTY
            spawn_mask = np_random_mask(empty_mask, NUTRIENT_SPAWN_RATE)
            grid[spawn_mask] = World.NUTRIENT
            self.world.nutrient_life[spawn_mask] = NUTRIENT_LIFE

    def execute_phase_2(self) -> None:
        """生命调度阶段：洗牌 + 衰老 + 年龄判死 + 扣税判死 + 执行指令"""
        alive_list = self.population.get_alive_list()
        random.shuffle(alive_list)

        # 统一衰老
        for org in alive_list:
            org.age += 1

        for org in alive_list:
            # 年龄判死
            if org.age >= AGE_LIMIT:
                self._kill_and_corpse(org)
                continue

            # 扣税判死
            org.energy -= 1
            if org.energy <= 0:
                self._kill_and_corpse(org)
                continue

            # 执行指令（SPLIT 已废弃，不再产生 spawn request）
            self.vm.execute_instruction(org, self.world, self.population)

        self._rebuild_alive_cache()

    def execute_phase_repro(self) -> None:
        """自动繁殖阶段：能量达标的生物自动触发繁殖"""
        alive_list = self.population.get_alive_list()
        spawn_queue: list[dict] = []

        for org in alive_list:
            cost = C_BASE + len(org.genome) * C_PER_INST
            threshold = int(cost * REPRO_ENERGY_MULTIPLIER)
            if org.energy < threshold:
                continue
            # 种群上限校验
            if self.population.is_full:
                break
            # 空间校验
            dp_x = org.regs[Organism.DP_X]
            dp_y = org.regs[Organism.DP_Y]
            empty_positions: list[tuple[int, int]] = []
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx, ny = (dp_x + dx) % self.world.w, (dp_y + dy) % self.world.h
                    if (
                        self.world.get_material(nx, ny) != World.TOXIN
                        and self.world.get_entity(nx, ny) is None
                    ):
                        empty_positions.append((nx, ny))
            if not empty_positions:
                continue
            # 执行繁殖
            org.energy -= cost
            child_genome = apply_mutations(bytearray(org.genome))
            if len(child_genome) < MIN_GENOME_LENGTH or len(child_genome) > MAX_GENOME_LENGTH:
                continue
            child_x, child_y = random.choice(empty_positions)
            spawn_queue.append({"genome": child_genome, "x": child_x, "y": child_y})

        self._spawn_queue = spawn_queue

    def execute_phase_3(self) -> None:
        """繁衍结算阶段"""
        for req in self._spawn_queue:
            org_id = self.population.spawn(
                genome=req["genome"], x=req["x"], y=req["y"], energy=E_BIRTH
            )
            if org_id >= 0:
                org = self.population.pool[org_id]
                org.fingerprint = compute_fingerprint(org.genome)
                self.world.set_entity(req["x"], req["y"], org)
                self._emit_event("birth", {
                    "tick": self.current_tick,
                    "org_id": org_id,
                    "x": req["x"],
                    "y": req["y"],
                })
        self._spawn_queue = []
        self._rebuild_alive_cache()

    def _kill_and_corpse(self, org: Organism) -> None:
        org.alive = False
        x, y = org.regs[Organism.DP_X], org.regs[Organism.DP_Y]
        self.world.set_entity(x, y, None)
        self.world.set_material(x, y, World.NUTRIENT)
        self.world.nutrient_life[y % self.world.h, x % self.world.w] = NUTRIENT_LIFE
        self._emit_event("death", {
            "tick": self.current_tick,
            "org_id": org.org_id,
            "x": org.regs[Organism.DP_X],
            "y": org.regs[Organism.DP_Y],
        })
        self.population.recycle(org.org_id)

    def _rebuild_alive_cache(self) -> None:
        alive = self.population.get_alive_list()
        n = len(alive)
        if n == 0:
            self._cached_alive_positions_yx = np.empty((0, 2), dtype=np.int16)
            self._cached_alive_energies = np.empty(0, dtype=np.int32)
            self._cached_alive_ids = np.empty(0, dtype=np.int32)
            return
        pos = np.empty((n, 2), dtype=np.int16)
        eng = np.empty(n, dtype=np.int32)
        ids = np.empty(n, dtype=np.int32)
        for i, org in enumerate(alive):
            pos[i, 0] = org.regs[Organism.DP_Y] % self.world.h
            pos[i, 1] = org.regs[Organism.DP_X] % self.world.w
            eng[i] = org.energy
            ids[i] = org.org_id
        self._cached_alive_positions_yx = pos
        self._cached_alive_energies = eng
        self._cached_alive_ids = ids

    def add_event_listener(self, callback) -> None:
        self._event_listeners.append(callback)

    def _emit_event(self, event_type: str, data: dict) -> None:
        for cb in self._event_listeners:
            cb(event_type, data)

    def take_snapshot(self) -> dict:
        """保存当前世界完整状态"""
        snapshot: dict = {
            "tick_count": self.current_tick,
            "world_grid": self.world.grid.copy(),
            "world_signal": self.world.signal_life.copy(),
            "world_nutrient": self.world.nutrient_life.copy(),
            "world_enzyme": self.world.enzyme_life.copy(),
            "organisms": [],
        }
        for org in self.population.pool:
            if org is not None and org.alive:
                snapshot["organisms"].append(
                    {
                        "id": org.org_id,
                        "pc": org.pc,
                        "regs": org.regs.copy(),
                        "energy": org.energy,
                        "age": org.age,
                        "genome": bytearray(org.genome),
                        "fingerprint": list(org.fingerprint)
                            if org.fingerprint is not None else None
                    }
                )
        return snapshot

    def load_snapshot(self, snapshot: dict) -> None:
        """从快照恢复世界状态"""
        self.current_tick = snapshot["tick_count"]
        self.world.grid = snapshot["world_grid"].copy()
        self.world.signal_life = snapshot["world_signal"].copy()
        self.world.nutrient_life = snapshot["world_nutrient"].copy()
        self.world.enzyme_life = snapshot["world_enzyme"].copy()
        # 重建实体网格
        self.world.entity_grid = [
            [None for _ in range(self.world.w)] for _ in range(self.world.h)
        ]
        # 重建种群
        for i in range(self.population.max_cap):
            self.population.pool[i] = None
        self.population.free_ids = list(range(self.population.max_cap - 1, -1, -1))
        for org_data in snapshot["organisms"]:
            x = org_data["regs"][Organism.DP_X]
            y = org_data["regs"][Organism.DP_Y]
            org_id = self.population.spawn(
                genome=org_data["genome"],
                x=x,
                y=y,
                energy=org_data["energy"],
            )
            if org_id >= 0:
                org = self.population.pool[org_id]
                fp_data = org_data.get("fingerprint")
                org.fingerprint = set(fp_data) if fp_data is not None else None
                self.world.set_entity(x, y, org)

    @staticmethod
    def _dilate_4(mask: np.ndarray) -> np.ndarray:
        """4连通膨胀（上下左右），np.roll 天然支持环形边界"""
        return (
            mask
            | np.roll(mask, 1, axis=0)
            | np.roll(mask, -1, axis=0)
            | np.roll(mask, 1, axis=1)
            | np.roll(mask, -1, axis=1)
        )

    @staticmethod
    def _dilate_3x3(mask: np.ndarray) -> np.ndarray:
        """3×3全膨胀（8连通+自身）"""
        result = mask.copy()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                result |= np.roll(np.roll(mask, dx, axis=0), dy, axis=1)
        return result
