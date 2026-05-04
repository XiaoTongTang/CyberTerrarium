"""种子配置加载器测试"""

import json
import tempfile
from pathlib import Path

import pytest

from cyberterrarium.model.config import MAX_POP, MIN_GENOME_LENGTH
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World
from cyberterrarium.tools.seed_loader import (
    SeedConfigError,
    _compile_species,
    _generate_grid_positions,
    load_seed_config,
    populate,
)


def _write_json(data: dict, tmpdir: Path) -> str:
    p = tmpdir / "seed.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


class TestLoadSeedConfig:
    # 场景：正常读取包含一个物种的配置
    def test_valid_single_species(self, tmp_path):
        path = _write_json(
            {"species": [{"name": "A", "assembly": "NOP", "count": 5}]}, tmp_path
        )
        config = load_seed_config(path)
        assert len(config["species"]) == 1
        assert config["species"][0]["name"] == "A"

    # 场景：配置文件不存在时返回空species
    def test_missing_file_returns_empty(self, tmp_path):
        config = load_seed_config(tmp_path / "nonexistent.json")
        assert config["species"] == []

    # 场景：species字段缺失时报错
    def test_missing_species_field(self, tmp_path):
        path = _write_json({"other": []}, tmp_path)
        with pytest.raises(SeedConfigError, match="species"):
            load_seed_config(path)

    # 场景：count字段为0时报错
    def test_count_zero(self, tmp_path):
        path = _write_json(
            {"species": [{"name": "A", "assembly": "NOP", "count": 0}]}, tmp_path
        )
        with pytest.raises(SeedConfigError, match="count"):
            load_seed_config(path)

    # 场景：总数量超过MAX_POP时报错
    def test_total_exceeds_max_pop(self, tmp_path):
        path = _write_json(
            {"species": [{"name": "A", "assembly": "NOP", "count": MAX_POP + 1}]},
            tmp_path,
        )
        with pytest.raises(SeedConfigError, match="MAX_POP"):
            load_seed_config(path)


class TestCompileSpecies:
    # 场景：有效汇编代码编译成功
    def test_valid_assembly(self):
        result = _compile_species([{"name": "G", "assembly": "NOP\nNOP", "count": 1}])
        assert len(result) == 1
        assert result[0][0] == "G"
        assert len(result[0][1]) >= MIN_GENOME_LENGTH

    # 场景：汇编语法错误时报错
    def test_invalid_assembly(self):
        with pytest.raises(SeedConfigError, match="assembly error"):
            _compile_species([{"name": "X", "assembly": "INVALID", "count": 1}])

    # 场景：编译后基因组过短时报错
    def test_genome_too_short(self):
        with pytest.raises(SeedConfigError, match="MIN_GENOME_LENGTH"):
            _compile_species([{"name": "S", "assembly": "NOP", "count": 1}])

    # 场景：多物种编译
    def test_multiple_species(self):
        result = _compile_species(
            [
                {"name": "A", "assembly": "MOV R0, 1\nMOVE_X R0\nEAT\nJMP -2", "count": 10},
                {"name": "B", "assembly": "MAKE TOXIN\nEMIT 0, 1\nJMP -1\nNOP", "count": 5},
            ]
        )
        assert len(result) == 2
        assert result[0][2] == 10
        assert result[1][2] == 5


class TestGridPositions:
    # 场景：0个生物时返回空列表
    def test_zero_returns_empty(self):
        assert _generate_grid_positions(0, 200, 200) == []

    # 场景：生成数量等于请求数量
    def test_correct_count(self):
        positions = _generate_grid_positions(50, 200, 200)
        assert len(positions) == 50

    # 场景：所有坐标在世界范围内
    def test_positions_in_bounds(self):
        positions = _generate_grid_positions(100, 200, 200)
        for x, y in positions:
            assert 0 <= x < 200
            assert 0 <= y < 200

    # 场景：大数量投放
    def test_large_count(self):
        positions = _generate_grid_positions(1000, 200, 200)
        assert len(positions) == 1000


class TestPopulate:
    # 场景：投放单个物种
    def test_single_species(self):
        world = World(200, 200)
        pop = Population()
        ctrl = SimulationController(world, pop)
        count = populate(
            ctrl,
            [{"name": "G", "assembly": "MOV R0, 1\nMOVE_X R0\nEAT\nJMP -2", "count": 10}],
        )
        assert count == 10
        assert pop.alive_count == 10

    # 场景：投放多物种
    def test_multiple_species(self):
        world = World(200, 200)
        pop = Population()
        ctrl = SimulationController(world, pop)
        count = populate(
            ctrl,
            [
                {"name": "A", "assembly": "MOV R0, 1\nMOVE_X R0\nEAT\nJMP -2", "count": 20},
                {"name": "B", "assembly": "NOP\nNOP\nNOP\nNOP", "count": 5},
            ],
        )
        assert count == 25
        assert pop.alive_count == 25

    # 场景：空species列表不投放
    def test_empty_species(self):
        world = World(200, 200)
        pop = Population()
        ctrl = SimulationController(world, pop)
        count = populate(ctrl, [])
        assert count == 0
        assert pop.alive_count == 0

    # 场景：投放后缓存数组已重建
    def test_cache_rebuilt(self):
        world = World(200, 200)
        pop = Population()
        ctrl = SimulationController(world, pop)
        populate(
            ctrl,
            [{"name": "G", "assembly": "MOV R0, 1\nMOVE_X R0\nEAT\nJMP -2", "count": 5}],
        )
        assert len(ctrl._cached_alive_positions_yx) == 5
        assert len(ctrl._cached_alive_energies) == 5
