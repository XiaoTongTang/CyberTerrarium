"""赛博生态缸入口"""

from cyberterrarium.model.config import WORLD_HEIGHT, WORLD_WIDTH
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World
from cyberterrarium.facade.api import ControlAPI, ViewAPI


def main() -> None:
    world = World(WORLD_WIDTH, WORLD_HEIGHT)
    population = Population()
    controller = SimulationController(world, population)

    view = ViewAPI(controller)
    control = ControlAPI(controller)

    # TODO: 接入Pygame渲染循环
    print("CyberTerrarium initialized.")
    print(f"World: {world.w}x{world.h}, Max Pop: {population.max_cap}")


if __name__ == "__main__":
    main()
