"""仿真控制器 - 系统调度核心，状态机管理者"""

import random

import numpy as np

from cyberterrarium.model.config import AGE_LIMIT, E_BIRTH, NUTRIENT_SPAWN_RATE
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

    def run_one_full_tick(self) -> None:
        self.execute_phase_1()
        self.execute_phase_2()
        self.execute_phase_3()

    def execute_phase_1(self) -> None:
        """物理与环境阶段：信号衰减 + 营养生成"""
        # 信号衰减
        mask = self.world.signal_life > 0
        self.world.signal_life[mask] -= 1
        expired = (self.world.signal_life == 0) & (self.world.grid == World.SIGNAL)
        self.world.grid[expired] = World.EMPTY

        # 营养生成
        empty_mask = self.world.grid == World.EMPTY
        spawn_mask = np_random_mask(empty_mask, NUTRIENT_SPAWN_RATE)
        self.world.grid[spawn_mask] = World.NUTRIENT

        self.current_tick += 1

    def execute_phase_2(self) -> None:
        """生命调度阶段：洗牌 + 衰老 + 年龄判死 + 扣税判死 + 执行指令"""
        alive_list = self.population.get_alive_list()
        random.shuffle(alive_list)
        spawn_queue: list[dict] = []

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

            # 执行指令
            requests = self.vm.execute_instruction(org, self.world, self.population)
            for req in requests:
                child_genome = apply_mutations(req["genome"])
                spawn_queue.append(
                    {"genome": child_genome, "x": req["x"], "y": req["y"]}
                )

        # 暂存繁衍队列
        self._spawn_queue = spawn_queue

    def execute_phase_3(self) -> None:
        """繁衍结算阶段"""
        for req in self._spawn_queue:
            self.population.spawn(
                genome=req["genome"], x=req["x"], y=req["y"], energy=E_BIRTH
            )
        self._spawn_queue = []

    def _kill_and_corpse(self, org: Organism) -> None:
        org.alive = False
        self.world.set_material(org.regs[Organism.DP_X], org.regs[Organism.DP_Y], World.NUTRIENT)

    def take_snapshot(self) -> dict:
        """保存当前世界完整状态"""
        snapshot: dict = {
            "tick_count": self.current_tick,
            "world_grid": self.world.grid.copy(),
            "world_signal": self.world.signal_life.copy(),
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
                    }
                )
        return snapshot

    def load_snapshot(self, snapshot: dict) -> None:
        """从快照恢复世界状态"""
        self.current_tick = snapshot["tick_count"]
        self.world.grid = snapshot["world_grid"].copy()
        self.world.signal_life = snapshot["world_signal"].copy()
        # 重建种群（简化实现）
        for org in self.population.pool:
            if org is not None:
                org.alive = False
        self.population.free_ids = list(range(self.population.max_cap - 1, -1, -1))
        for org_data in snapshot["organisms"]:
            self.population.spawn(
                genome=org_data["genome"],
                x=org_data["regs"][Organism.DP_X],
                y=org_data["regs"][Organism.DP_Y],
                energy=org_data["energy"],
            )
