"""指令执行引擎 - 虚拟机CPU核心"""

from __future__ import annotations

from cyberterrarium.model.bitmap import BMAP_MASK, BMAP_OFFSETS
from cyberterrarium.model.config import (
    C_ATTACK_BASE,
    C_ATTACK_PER_BIT,
    C_DAMAGE_PER_HIT,
    C_EMIT_ENZ,
    C_EMIT_SIG,
    C_EMIT_TOX,
    C_LEECH_PER_HIT,
    C_MAKE_ENZ,
    C_MAKE_SIG,
    C_MAKE_TOX,
    C_SCAN_BIO,
    C_TOUCH_TOX,
    E_ENZ_EAT,
    E_NUT,
    ENZ_LIFE,
    MOVE_BASE,
    MOVE_RATE,
    MOVE_SPRINT,
    NUTRIENT_LIFE,
    TOX_LIFETIME,
)
from cyberterrarium.model.fingerprint import jaccard_similarity
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
        p3 = bytecode[3]

        # 查表分发
        opdef = OPCODE_BY_CODE.get(opcode)
        if opdef is not None:
            handler = getattr(self, opdef.handler_method)
            result = handler(org, p1, p2, p3, world, population)
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

    @staticmethod
    def _move_cost(dx: int, dy: int) -> int:
        d = abs(dx) + abs(dy)
        if d == 0:
            return 0
        return MOVE_BASE + MOVE_RATE * d + MOVE_SPRINT * d * (d - 1) // 2

    # ── 统一签名 (org, p1, p2, p3, world, population) ──

    def _op_nop(
        self, org: Organism, _p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        pass

    def _op_mov(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] = p2

    def _op_add(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] += org.regs[self._safe_reg(p2)]

    def _op_sub(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] -= org.regs[self._safe_reg(p2)]

    def _op_and(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] &= org.regs[self._safe_reg(p2)]

    def _op_or(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] |= org.regs[self._safe_reg(p2)]

    def _op_not(
        self, org: Organism, p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] = ~org.regs[self._data_reg(p1)]

    def _op_read_rel(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        tx = (org.regs[Organism.DP_X] + p1) % world.w
        ty = (org.regs[Organism.DP_Y] + p2) % world.h
        org.regs[Organism.R0] = world.get_material(tx, ty)

    def _op_read_abs(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        tx = org.regs[self._safe_reg(p1)] % world.w
        ty = org.regs[self._safe_reg(p2)] % world.h
        org.regs[Organism.R0] = world.get_material(tx, ty)

    def _op_eat(
        self, org: Organism, _p1: int, _p2: int, _p3: int, world: World, _pop: Population
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
        self, org: Organism, p1: int, _p2: int, _p3: int, _w: World, _pop: Population
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
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, _pop: Population
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
        elif material == World.ENZYME:
            world.enzyme_life[ty % world.h, tx % world.w] = ENZ_LIFE
        elif material == World.TOXIN:
            world.toxin_life[ty % world.h, tx % world.w] = TOX_LIFETIME
            world.toxin_signature[ty % world.h, tx % world.w] = org.gene_signature
        org.regs[Organism.INV] = World.EMPTY

    def _op_move_x(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        dx = org.regs[self._safe_reg(p1)]
        new_x = (org.regs[Organism.DP_X] + dx) % world.w
        new_y = org.regs[Organism.DP_Y]
        cost = self._move_cost(dx, 0)
        if cost > 0 and org.energy < cost:
            return
        if world.get_entity(new_x, new_y) is not None:
            return
        org.energy -= cost
        self._check_toxin(org, new_x, new_y, world)
        old_x = org.regs[Organism.DP_X]
        world.set_entity(old_x, new_y, None)
        org.regs[Organism.DP_X] = new_x
        world.set_entity(new_x, new_y, org)

    def _op_move_y(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        dy = org.regs[self._safe_reg(p1)]
        new_x = org.regs[Organism.DP_X]
        new_y = (org.regs[Organism.DP_Y] + dy) % world.h
        cost = self._move_cost(0, dy)
        if cost > 0 and org.energy < cost:
            return
        if world.get_entity(new_x, new_y) is not None:
            return
        org.energy -= cost
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
            toxin_sig = world.toxin_signature[y % world.h, x % world.w]
            if toxin_sig == 0 or org.gene_signature != toxin_sig:
                org.energy -= C_TOUCH_TOX
            self._corrosion_reaction(x, y, world)

    def _corrosion_reaction(
        self, x: int, y: int, world: World
    ) -> None:
        world.set_material(x, y, World.EMPTY)
        world.toxin_life[y % world.h, x % world.w] = 0
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (x + dx) % world.w
                ny = (y + dy) % world.h
                if world.get_material(nx, ny) == World.TOXIN:
                    world.set_material(nx, ny, World.NUTRIENT)
                    world.nutrient_life[ny, nx] = NUTRIENT_LIFE
                    world.toxin_life[ny, nx] = 0

    def _op_cmp(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.equal_flag = org.regs[self._safe_reg(p1)] == org.regs[self._safe_reg(p2)]

    def _op_jz(
        self, org: Organism, p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        if org.equal_flag:
            signed_offset = p1 if p1 < 128 else p1 - 256
            org.pc = (org.pc + signed_offset * 4) % len(org.genome)
        else:
            org.pc = (org.pc + 4) % len(org.genome)

    def _op_jnz(
        self, org: Organism, p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        if not org.equal_flag:
            signed_offset = p1 if p1 < 128 else p1 - 256
            org.pc = (org.pc + signed_offset * 4) % len(org.genome)
        else:
            org.pc = (org.pc + 4) % len(org.genome)

    def _op_jmp(
        self, org: Organism, p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        signed_offset = p1 if p1 < 128 else p1 - 256
        org.pc = (org.pc + signed_offset * 4) % len(org.genome)

    def _op_split(
        self, org: Organism, _p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> list[dict]:
        return []

    # ── 位图映射指令 ──

    def _op_move_bmap(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        bmap = org.regs[self._safe_reg(p1)] & BMAP_MASK
        sum_x = 0
        sum_y = 0
        for bit_idx in range(25):
            if bmap & (1 << bit_idx):
                dx, dy = BMAP_OFFSETS[bit_idx]
                sum_x += dx
                sum_y += dy
        move_x = max(-2, min(2, sum_x))
        move_y = max(-2, min(2, sum_y))
        if move_x == 0 and move_y == 0:
            return
        cost = self._move_cost(move_x, move_y)
        if org.energy < cost:
            return
        new_x = (org.regs[Organism.DP_X] + move_x) % world.w
        new_y = (org.regs[Organism.DP_Y] + move_y) % world.h
        if world.get_entity(new_x, new_y) is not None:
            return
        org.energy -= cost
        self._check_toxin(org, new_x, new_y, world)
        old_x = org.regs[Organism.DP_X]
        old_y = org.regs[Organism.DP_Y]
        world.set_entity(old_x, old_y, None)
        org.regs[Organism.DP_X] = new_x
        org.regs[Organism.DP_Y] = new_y
        world.set_entity(new_x, new_y, org)

    def _op_attack_bmap(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        bmap = org.regs[self._safe_reg(p1)] & BMAP_MASK
        popcount = bin(bmap).count("1")
        cost = C_ATTACK_BASE + popcount * C_ATTACK_PER_BIT
        if org.energy < cost:
            return
        org.energy -= cost
        dp_x = org.regs[Organism.DP_X]
        dp_y = org.regs[Organism.DP_Y]
        for bit_idx in range(25):
            if bmap & (1 << bit_idx):
                dx, dy = BMAP_OFFSETS[bit_idx]
                tx = (dp_x + dx) % world.w
                ty = (dp_y + dy) % world.h
                target = world.get_entity(tx, ty)
                if target is not None and target.alive:
                    target.energy -= C_DAMAGE_PER_HIT
                    org.energy += C_LEECH_PER_HIT

    def _op_scan_nut(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        self._scan_material(org, p1, world, World.NUTRIENT)

    def _op_scan_tox(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        self._scan_material(org, p1, world, World.TOXIN)

    def _op_scan_emp(
        self, org: Organism, p1: int, _p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        self._scan_material(org, p1, world, World.EMPTY)

    def _scan_material(
        self, org: Organism, p1: int, world: World, target_mat: int
    ) -> None:
        dp_x = org.regs[Organism.DP_X]
        dp_y = org.regs[Organism.DP_Y]
        result = 0
        for bit_idx in range(25):
            dx, dy = BMAP_OFFSETS[bit_idx]
            tx = (dp_x + dx) % world.w
            ty = (dp_y + dy) % world.h
            if world.get_material(tx, ty) == target_mat:
                result |= 1 << bit_idx
        org.regs[self._data_reg(p1)] = result

    @staticmethod
    def _emit_bmap_cost(mat_id: int, popcount: int) -> int:
        if mat_id == World.ENZYME:
            per_cell = C_EMIT_ENZ
        elif mat_id == World.TOXIN:
            per_cell = C_EMIT_TOX
        elif mat_id == World.SIGNAL:
            per_cell = C_EMIT_SIG
        else:
            per_cell = C_EMIT_ENZ
        return int(popcount * per_cell)

    def _op_emit_bmap(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, _pop: Population
    ) -> None:
        if p2 < World.NUTRIENT or p2 > World.SIGNAL:
            return
        bmap = org.regs[self._safe_reg(p1)] & BMAP_MASK
        popcount = bin(bmap).count("1")
        cost = self._emit_bmap_cost(p2, popcount)
        if org.energy < cost:
            return
        org.energy -= cost
        dp_x = org.regs[Organism.DP_X]
        dp_y = org.regs[Organism.DP_Y]
        for bit_idx in range(25):
            if bmap & (1 << bit_idx):
                dx, dy = BMAP_OFFSETS[bit_idx]
                tx = (dp_x + dx) % world.w
                ty = (dp_y + dy) % world.h
                world.set_material(tx, ty, p2)
                if p2 == World.SIGNAL:
                    world.signal_life[ty % world.h, tx % world.w] = 50
                elif p2 == World.ENZYME:
                    world.enzyme_life[ty % world.h, tx % world.w] = ENZ_LIFE
                elif p2 == World.TOXIN:
                    world.toxin_life[ty % world.h, tx % world.w] = TOX_LIFETIME
                    world.toxin_signature[ty % world.h, tx % world.w] = org.gene_signature

    # ── 寄存器操作指令 ──

    def _op_wlo(
        self, org: Organism, p1: int, p2: int, p3: int, _w: World, _pop: Population
    ) -> None:
        reg = self._data_reg(p1)
        low16 = (p2 << 8) | p3
        org.regs[reg] = (org.regs[reg] & 0xFFFF0000) | low16

    def _op_whi(
        self, org: Organism, p1: int, p2: int, p3: int, _w: World, _pop: Population
    ) -> None:
        reg = self._data_reg(p1)
        high16 = (p2 << 8) | p3
        org.regs[reg] = (org.regs[reg] & 0x0000FFFF) | (high16 << 16)

    def _op_shl(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] <<= p2

    def _op_shr(
        self, org: Organism, p1: int, p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] >>= p2

    def _op_clr(
        self, org: Organism, p1: int, _p2: int, _p3: int, _w: World, _pop: Population
    ) -> None:
        org.regs[self._data_reg(p1)] = 0

    # ── 生物扫描指令 ──

    def _scan_bio(
        self, org: Organism, p1: int, p2: int, world: World, population: Population, greater: bool
    ) -> None:
        if org.energy < C_SCAN_BIO:
            return
        org.energy -= C_SCAN_BIO

        threshold = p2 / 255.0
        dp_x = org.regs[Organism.DP_X]
        dp_y = org.regs[Organism.DP_Y]
        f_self = org.fingerprint
        result = 0

        for bit_idx in range(25):
            dx, dy = BMAP_OFFSETS[bit_idx]
            if dx == 0 and dy == 0:
                continue
            tx = (dp_x + dx) % world.w
            ty = (dp_y + dy) % world.h
            target = world.get_entity(tx, ty)
            if target is None or not target.alive:
                continue
            f_target = target.fingerprint
            sim = jaccard_similarity(f_self, f_target)
            if greater and sim > threshold:  # noqa: SIM114
                result |= 1 << bit_idx
            elif not greater and sim < threshold:
                result |= 1 << bit_idx

        org.regs[self._data_reg(p1)] = result

    def _op_scan_bio_g(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, population: Population
    ) -> None:
        self._scan_bio(org, p1, p2, world, population, greater=True)

    def _op_scan_bio_l(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, population: Population
    ) -> None:
        self._scan_bio(org, p1, p2, world, population, greater=False)

    # ── 选择性攻击指令 ──

    def _op_attack_l(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, population: Population
    ) -> None:
        self._scan_bio(org, p1, p2, world, population, greater=False)
        self._op_attack_bmap(org, p1, 0, 0, world, population)

    def _op_attack_g(
        self, org: Organism, p1: int, p2: int, _p3: int, world: World, population: Population
    ) -> None:
        self._scan_bio(org, p1, p2, world, population, greater=True)
        self._op_attack_bmap(org, p1, 0, 0, world, population)
