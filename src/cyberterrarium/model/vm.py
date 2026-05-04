"""指令执行引擎 - 虚拟机CPU核心"""

from cyberterrarium.model.config import (
    C_MAKE_ENZ,
    C_MAKE_SIG,
    C_MAKE_TOX,
    C_TOUCH_TOX,
    E_ENZ_EAT,
    E_NUT,
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
        spawn_requests: list[dict] = []

        bytecode = org.genome[org.pc : org.pc + 4]
        if len(bytecode) < 4:
            org.pc = 0
            return spawn_requests

        opcode = bytecode[0]
        p1 = bytecode[1]
        p2 = bytecode[2]
        _p3 = bytecode[3]  # noqa: F841 - reserved for future instructions
        if opcode == 0x00:
            pass  # NOP
        elif opcode == 0x01:
            self._op_mov(org, p1, p2)
        elif opcode == 0x02:
            self._op_add(org, p1, p2)
        elif opcode == 0x03:
            self._op_sub(org, p1, p2)
        elif opcode == 0x04:
            self._op_and(org, p1, p2)
        elif opcode == 0x05:
            self._op_or(org, p1, p2)
        elif opcode == 0x06:
            self._op_not(org, p1)
        elif opcode == 0x09:
            self._op_read_rel(org, p1, p2, world)
        elif opcode == 0x0A:
            self._op_read_abs(org, p1, p2, world)
        elif opcode == 0x0B:
            self._op_eat(org, world)
        elif opcode == 0x0C:
            self._op_make(org, p1)
        elif opcode == 0x0D:
            self._op_emit(org, p1, p2, world)
        elif opcode == 0x0E:
            self._op_move_x(org, p1, world)
        elif opcode == 0x0F:
            self._op_move_y(org, p1, world)
        elif opcode == 0x10:
            self._op_cmp(org, p1, p2)
        elif opcode == 0x11:
            self._op_jz(org, p1)
        elif opcode == 0x12:
            self._op_jnz(org, p1)
        elif opcode == 0x13:
            self._op_jmp(org, p1)
        elif opcode == 0x14:
            spawn_requests = self._op_split(org, world, population)
        else:
            pass  # 未定义Opcode → 当NOP处理

        # 默认推进PC
        if opcode not in (0x11, 0x12, 0x13):
            org.pc = (org.pc + 4) % len(org.genome)

        return spawn_requests

    def _safe_reg(self, idx: int) -> int:
        return idx if 0 <= idx < Organism.REG_COUNT else 0

    def _op_mov(self, org: Organism, ra: int, imm: int) -> None:
        org.regs[self._safe_reg(ra)] = imm

    def _op_add(self, org: Organism, ra: int, rb: int) -> None:
        org.regs[self._safe_reg(ra)] += org.regs[self._safe_reg(rb)]

    def _op_sub(self, org: Organism, ra: int, rb: int) -> None:
        org.regs[self._safe_reg(ra)] -= org.regs[self._safe_reg(rb)]

    def _op_and(self, org: Organism, ra: int, rb: int) -> None:
        org.regs[self._safe_reg(ra)] &= org.regs[self._safe_reg(rb)]

    def _op_or(self, org: Organism, ra: int, rb: int) -> None:
        org.regs[self._safe_reg(ra)] |= org.regs[self._safe_reg(rb)]

    def _op_not(self, org: Organism, ra: int) -> None:
        org.regs[self._safe_reg(ra)] = ~org.regs[self._safe_reg(ra)]

    def _op_read_rel(self, org: Organism, imm_x: int, imm_y: int, world: World) -> None:
        tx = (org.regs[Organism.DP_X] + imm_x) % world.w
        ty = (org.regs[Organism.DP_Y] + imm_y) % world.h
        org.regs[Organism.R0] = world.get_material(tx, ty)

    def _op_read_abs(self, org: Organism, rx: int, ry: int, world: World) -> None:
        tx = org.regs[self._safe_reg(rx)] % world.w
        ty = org.regs[self._safe_reg(ry)] % world.h
        org.regs[Organism.R0] = world.get_material(tx, ty)

    def _op_eat(self, org: Organism, world: World) -> None:
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

    def _op_make(self, org: Organism, mat_id: int) -> None:
        if mat_id == World.ENZYME:
            org.energy -= C_MAKE_ENZ
            org.regs[Organism.INV] = World.ENZYME
        elif mat_id == World.TOXIN:
            org.energy -= C_MAKE_TOX
            org.regs[Organism.INV] = World.TOXIN
        elif mat_id == World.SIGNAL:
            org.energy -= C_MAKE_SIG
            org.regs[Organism.INV] = World.SIGNAL
        else:
            org.energy -= C_MAKE_ENZ  # 非法物质：代谢失误惩罚

    def _op_emit(self, org: Organism, imm_x: int, imm_y: int, world: World) -> None:
        if abs(imm_x) + abs(imm_y) > 1:
            return  # 写权限校验失败
        if org.regs[Organism.INV] == World.EMPTY:
            return  # 背包为空
        tx = (org.regs[Organism.DP_X] + imm_x) % world.w
        ty = (org.regs[Organism.DP_Y] + imm_y) % world.h
        material = org.regs[Organism.INV]
        world.set_material(tx, ty, material)
        if material == World.SIGNAL:
            world.signal_life[ty % world.h, tx % world.w] = 50
        org.regs[Organism.INV] = World.EMPTY

    def _op_move_x(self, org: Organism, rx: int, world: World) -> None:
        new_x = (org.regs[Organism.DP_X] + org.regs[self._safe_reg(rx)]) % world.w
        new_y = org.regs[Organism.DP_Y]
        self._check_toxin(org, new_x, new_y, world)
        org.regs[Organism.DP_X] = new_x

    def _op_move_y(self, org: Organism, rx: int, world: World) -> None:
        new_x = org.regs[Organism.DP_X]
        new_y = (org.regs[Organism.DP_Y] + org.regs[self._safe_reg(rx)]) % world.h
        self._check_toxin(org, new_x, new_y, world)
        org.regs[Organism.DP_Y] = new_y

    def _check_toxin(self, org: Organism, x: int, y: int, world: World) -> None:
        cell = world.get_material(x, y)
        if cell == World.TOXIN:
            org.energy -= C_TOUCH_TOX
            world.set_material(x, y, World.EMPTY)

    def _op_cmp(self, org: Organism, ra: int, rb: int) -> None:
        org.equal_flag = org.regs[self._safe_reg(ra)] == org.regs[self._safe_reg(rb)]

    def _op_jz(self, org: Organism, offset: int) -> None:
        if org.equal_flag:
            signed_offset = offset if offset < 128 else offset - 256
            org.pc = (org.pc + signed_offset * 4) % len(org.genome)
        else:
            org.pc = (org.pc + 4) % len(org.genome)

    def _op_jnz(self, org: Organism, offset: int) -> None:
        if not org.equal_flag:
            signed_offset = offset if offset < 128 else offset - 256
            org.pc = (org.pc + signed_offset * 4) % len(org.genome)
        else:
            org.pc = (org.pc + 4) % len(org.genome)

    def _op_jmp(self, org: Organism, offset: int) -> None:
        signed_offset = offset if offset < 128 else offset - 256
        org.pc = (org.pc + signed_offset * 4) % len(org.genome)

    def _op_split(
        self, org: Organism, world: World, population: Population
    ) -> list[dict]:
        # SPLIT 已废弃，执行效果等同 NOP
        return []
