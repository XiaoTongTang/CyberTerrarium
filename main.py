"""赛博生态缸入口"""

from cyberterrarium.model.config import WORLD_HEIGHT, WORLD_WIDTH
from cyberterrarium.model.controller import SimulationController
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World
from cyberterrarium.facade.api import ControlAPI, ViewAPI
from cyberterrarium.view.app import CyberTerrariumUI


def main() -> None:
    world = World(WORLD_WIDTH, WORLD_HEIGHT)
    population = Population()
    controller = SimulationController(world, population)

    view = ViewAPI(controller)
    control = ControlAPI(controller)

    ui = CyberTerrariumUI(view, control)
    ui.run()


if __name__ == "__main__":
    main()
