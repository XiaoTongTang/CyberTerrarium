"""赛博生态缸入口"""

import argparse
import sys

from cyberterrarium.model.config import WORLD_HEIGHT, WORLD_WIDTH
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World
from cyberterrarium.facade.api import ControlAPI, ViewAPI
from cyberterrarium.tools.seed_loader import SeedConfigError, load_seed_config, populate
from cyberterrarium.view.app import CyberTerrariumUI

DEFAULT_SEED_PATH = "seed.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="CyberTerrarium - 赛博生态缸")
    parser.add_argument(
        "--seed", default=DEFAULT_SEED_PATH,
        help=f"种子配置文件路径 (默认: {DEFAULT_SEED_PATH})",
    )
    args = parser.parse_args()

    world = World(WORLD_WIDTH, WORLD_HEIGHT)
    population = Population()
    controller = SimulationController(world, population)

    # 加载种子配置并投放初始生物
    try:
        config = load_seed_config(args.seed)
    except SeedConfigError as e:
        print(f"种子配置错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"读取种子配置失败: {e}", file=sys.stderr)
        sys.exit(1)

    if config["species"]:
        try:
            count = populate(controller, config["species"])
            print(f"已投放 {count} 个初始生物 (配置: {args.seed})")
        except SeedConfigError as e:
            print(f"投放失败: {e}", file=sys.stderr)
            sys.exit(1)

    view = ViewAPI(controller)
    control = ControlAPI(controller)

    ui = CyberTerrariumUI(view, control)
    ui.run()


if __name__ == "__main__":
    main()
