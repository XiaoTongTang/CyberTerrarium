"""种子配置加载器 - 读取JSON配置、编译汇编、均匀投放初始生物"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from cyberterrarium.model.config import MAX_GENOME_LENGTH, MAX_POP, MIN_GENOME_LENGTH
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.fingerprint import compute_fingerprint, compute_gene_signature
from cyberterrarium.tools.assembler import AssembleError, assemble


class SeedConfigError(Exception):
    pass


def load_seed_config(path: str | Path) -> dict:
    """读取并验证种子配置JSON文件。"""
    path = Path(path)
    if not path.exists():
        return {"species": []}

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if "species" not in data or not isinstance(data["species"], list):
        raise SeedConfigError("'species' field must be a list")

    total_count = 0
    for i, sp in enumerate(data["species"]):
        if "name" not in sp:
            raise SeedConfigError(f"species[{i}]: missing 'name'")
        if "assembly" not in sp:
            raise SeedConfigError(f"species[{i}]: missing 'assembly'")
        if "count" not in sp:
            raise SeedConfigError(f"species[{i}]: missing 'count'")
        if not isinstance(sp["count"], int) or sp["count"] < 0:
            raise SeedConfigError(f"species[{i}]: 'count' must be an integer >= 0")
        total_count += sp["count"]

    if total_count > MAX_POP:
        raise SeedConfigError(
            f"Total count {total_count} exceeds MAX_POP ({MAX_POP})"
        )

    return data


def _compile_species(species_list: list[dict]) -> list[tuple[str, bytearray, int]]:
    """编译所有物种的汇编代码，返回 (name, genome, count) 列表。"""
    compiled: list[tuple[str, bytearray, int]] = []
    for sp in species_list:
        name = sp["name"]
        source = sp["assembly"]
        count = sp["count"]
        try:
            genome = assemble(source)
        except AssembleError as e:
            raise SeedConfigError(f"Species '{name}': assembly error: {e}") from e
        glen = len(genome)
        if glen < MIN_GENOME_LENGTH:
            raise SeedConfigError(
                f"Species '{name}': genome length {glen} < MIN_GENOME_LENGTH ({MIN_GENOME_LENGTH})"
            )
        if glen > MAX_GENOME_LENGTH:
            raise SeedConfigError(
                f"Species '{name}': genome length {glen} > MAX_GENOME_LENGTH ({MAX_GENOME_LENGTH})"
            )
        compiled.append((name, genome, count))
    return compiled


def _generate_grid_positions(
    total: int, world_w: int, world_h: int
) -> list[tuple[int, int]]:
    """生成均匀网格分布的候选坐标列表。"""
    if total == 0:
        return []
    cols = math.ceil(math.sqrt(total * world_w / world_h))
    rows = math.ceil(total / cols)
    step_x = world_w / cols
    step_y = world_h / rows
    positions: list[tuple[int, int]] = []
    for r in range(rows):
        for c in range(cols):
            if len(positions) >= total:
                break
            x = int(c * step_x + step_x / 2) % world_w
            y = int(r * step_y + step_y / 2) % world_h
            positions.append((x, y))
    random.shuffle(positions)
    return positions[:total]


def _find_nearby_empty(
    x: int, y: int, world, max_radius: int = 5
) -> tuple[int, int] | None:
    """在曼哈顿距离 max_radius 内搜索空格。"""
    from cyberterrarium.model.world import World

    for dist in range(1, max_radius + 1):
        for dx in range(-dist, dist + 1):
            remaining = dist - abs(dx)
            for dy in (-remaining, remaining) if remaining > 0 else (0,):
                nx = (x + dx) % world.w
                ny = (y + dy) % world.h
                if world.grid[ny, nx] == World.EMPTY:
                    return (nx, ny)
    return None


def populate(
    controller: SimulationController, species_list: list[dict]
) -> int:
    """编译汇编代码并将生物均匀投放到世界中。返回实际投放数。"""
    compiled = _compile_species(species_list)
    total = sum(count for _, _, count in compiled)
    if total == 0:
        return 0

    world = controller.world
    positions = _generate_grid_positions(total, world.w, world.h)

    spawned = 0
    pos_idx = 0
    for _name, genome, count in compiled:
        for _ in range(count):
            if pos_idx >= len(positions):
                break
            x, y = positions[pos_idx]
            pos_idx += 1
            org_id = controller.population.spawn(
                genome=bytearray(genome), x=x, y=y
            )
            if org_id >= 0:
                spawned += 1
                org = controller.population.pool[org_id]
                org.fingerprint = compute_fingerprint(org.genome)
                org.gene_signature = compute_gene_signature(org.fingerprint)
                controller.world.set_entity(x, y, org)

    controller._rebuild_alive_cache()
    return spawned
