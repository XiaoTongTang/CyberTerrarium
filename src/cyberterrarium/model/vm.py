"""指令执行引擎 - 虚拟机CPU核心"""

from __future__ import annotations

from cyberterrarium.model.config import (
    C_MAKE_ENZ,
    C_MAKE_SIG,
    C_MAKE_TOX,
    C_TOUCH_TOX,
    E_ENZ_EAT,
    E_NUT,
)
from cyberterrarium.model.isa import (
    DATA_REG_COUNT,
    OPCODE_BY_CODE,
    PC_ADVANCE_EXEMPT,
    REG_COUNT,
)
from cyberterrarium.model.organism import Organism
from cyberterrarium.model.population import Population
from cyberterrarium.model.world import World


class VirtualMachine:
    """指令解码与执行引擎。"""

    def execute_instruction(
        self, org: Organism, world: World, population: Population
    ) -> list[dict]:
        """执行一条指令，返回本Tick产生的繁衍请求列表。"""
        bytecode = org.genome[org.pc : org.pc + 4]
        if len(bytecode) < 4:
            org.pc = 0
            return []

        opcode = bytecode[0]
        p1 = bytecode[1]
        p2 = bytecode[2]
        _p3 = bytecode[3]  # noqa: F841 - reserved

        # 查表分发
        opdef = OPCODE_BY_CODE.get(opcode)
        if opdef is not None:
            handler = getattr(self, opdef.handler_method)
            result = handler(org, p1, p2, world, population)
            spawn_requests = (
                result if opdef.returns_spawn and isinstance(result, list) else []
            )
        else:
            spawn_requests = []  # 未定义Opcode → NOP

        # PC推进
        if opcode not in PC_ADVANCE_EXEMPT:
            org.pc = (org.pc + 4) % len(org.genome)

        # 归一化DP坐标：防御性兜底
        org.regs[Organism.DP_X] = org.regs[Organism.DP_X] % world.w
        org.regs[Organism.DP_Y] = org.regs[Organism.DP_Y] % world.h

        return spawn_requests

    def _safe_reg(self, idx: int) -> int:
        return idx if 0 <= idx < REG_COUNT else 0

    def _data_reg(self, idx: int) -> int:
        """映射到通用数据寄存器，INV/DP_X/DP_Y返回R0。"""
        return idx if 0 <= idx < DATA_REG_COUNT else 0

    # ── 统一签名 (org, p1, p2, world, population) ──

    def _op_nop(
        self, org: Organism, _p1: int, _p2: int, _w: World, _pop: Population
    ) -> None:
        pass

    def _op_mov(
        self, org: Organism, p1: int, p2: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] = p2

    def _op_add(
        self, org: Organism, p1: int, p2: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] += org.regs[self._safe_reg(p2)]

    def _op_sub(
        self, org: Organism, p1: int, p2: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] -= org.regs[self._safe_reg(p2)]

    def _op_and(
        self, org: Organism, p1: int, p2: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] &= org.regs[self._safe_reg(p2)]

    def _op_or(
        self, org: Organism, p1: int, p2: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] |= org.regs[self._safe_reg(p2)]

    def _op_not(
        self, org: Organism, p1: int, _p2: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] = ~org.regs[self._data_reg(p1)]

    def _op_read_rel(
        self, org: Organism, p1: int, p2: int, world: World, _pop: Population
    ) -> None:
        tx = (org.regs[Organism.DP_X] + p1) % world.w
        ty = (org.regs[Organism.DP_Y] + p2) % world.h
        org.regs[Organism.R0] = world.get_material(tx, ty)

    def _op_read_abs(
        self, org: Organism, p1: int, p2: int, world: World, _pop: Population
    ) -> None:
        tx = org.regs[self._safe_reg(p1)] % world.w
        ty = org.regs[self._safe_reg(p2)] % world.h
        org.regs[Organism.R0] = world.get_material(tx, ty)

    def _op_eat(
        self, org: Organism, _p1: int, _p2: int, world: World, _pop: Population
    ) -> None:
        cell = world.get_material(org.regs[Organism.DP_X], org.regs[Organism.DP_Y])
        if cell == World.NUTRIENT:
            if org.regs[Organism.INV] == World.ENZYME:
                org.energy += E_ENZ_EAT
            else:
                org.energy += E_NUT
            org.regs[Organism.INV] = 0
            x = org.regs[Organism.DP_X]
            y = org.regs[Organism.DP_Y]
            world.set_material(x, y, World.EMPTY)
            world.nutrient_life[y % world.h, x % world.w] = 0

    def _op_make(
        self, org: Organism, p1: int, _p2: int, _w: World, _pop: Population
    ) -> None:
        if p1 == World.ENZYME:
            org.energy -= C_MAKE_ENZ
            org.regs[Organism.INV] = World.ENZYME
        elif p1 == World.TOXIN:
            org.energy -= C_MAKE_TOX
            org.regs[Organism.INV] = World.TOXIN
        elif p1 == World.SIGNAL:
            org.energy -= C_MAKE_SIG
            org.regs[Organism.INV] = World.SIGNAL
        else:
            org.energy -= C_MAKE_ENZ

    def _op_emit(
        self, org: Organism, p1: int, p2: int, world: World, _pop: Population
    ) -> None:
        if abs(p1) + abs(p2) > 1:
            return
        material = org.regs[Organism.INV]
        if material < World.NUTRIENT or material > World.SIGNAL:
            return
        tx = (org.regs[Organism.DP_X] + p1) % world.w
        ty = (org.regs[Organism.DP_Y] + p2) % world.h
        world.set_material(tx, ty, material)
        if material == World.SIGNAL:
            world.signal_life[ty % world.h, tx % world.w] = 50
        org.regs[Organism.INV] = World.EMPTY

    def _op_move_x(
        self, org: Organism, p1: int, _p2: int, world: World, _pop: Population
    ) -> None:
        new_x = (org.regs[Organism.DP_X] + org.regs[self._safe_reg(p1)]) % world.w
        new_y = org.regs[Organism.DP_Y]
        if world.get_entity(new_x, new_y) is not None:
            return
        self._check_toxin(org, new_x, new_y, world)
        old_x = org.regs[Organism.DP_X]
        world.set_entity(old_x, new_y, None)
        org.regs[Organism.DP_X] = new_x
        world.set_entity(new_x, new_y, org)

    def _op_move_y(
        self, org: Organism, p1: int, _p2: int, world: World, _pop: Population
    ) -> None:
        new_x = org.regs[Organism.DP_X]
        new_y = (org.regs[Organism.DP_Y] + org.regs[self._safe_reg(p1)]) % world.h
        if world.get_entity(new_x, new_y) is not None:
            return
        self._check_toxin(org, new_x, new_y, world)
        old_y = org.regs[Organism.DP_Y]
        world.set_entity(new_x, old_y, None)
        org.regs[Organism.DP_Y] = new_y
        world.set_entity(new_x, new_y, org)

    def _check_toxin(
        self, org: Organism, x: int, y: int, world: World
    ) -> None:
        cell = world.get_material(x, y)
        if cell == World.TOXIN:
            org.energy -= C_TOUCH_TOX
            world.set_material(x, y, World.EMPTY)

    def _op_cmp(
        self, org: Organism, p1: int, p2: int, _w: World, _pop: Population
    ) -> None:
        org.equal_flag = org.regs[self._safe_reg(p1)] == org.regs[self._safe_reg(p2)]

    def _op_jz(
        self, org: Organism, p1: int, _p2: int, _w: World, _pop: Population
    ) -> None:
        if org.equal_flag:
            signed_offset = p1 if p1 < 128 else p1 - 256
            org.pc = (org.pc + signed_offset * 4) % len(org.genome)
        else:
            org.pc = (org.pc + 4) % len(org.genome)

    def _op_jnz(
        self, org: Organism, p1: int, _p2: int, _w: World, _pop: Population
    ) -> None:
        if not org.equal_flag:
            signed_offset = p1 if p1 < 128 else p1 - 256
            org.pc = (org.pc + signed_offset * 4) % len(org.genome)
        else:
            org.pc = (org.pc + 4) % len(org.genome)

    def _op_jmp(
        self, org: Organism, p1: int, _p2: int, _w: World, _pop: Population
    ) -> None:
        signed_offset = p1 if p1 < 128 else p1 - 256
        org.pc = (org.pc + signed_offset * 4) % len(org.genome)

    def _op_split(
        self, org: Organism, _p1: int, _p2: int, _w: World, _pop: Population
    ) -> list[dict]:
        return []
