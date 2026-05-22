"""生物实体 - 扁平化数据容器"""

from dataclasses import dataclass

from cyberterrarium.model.isa import REG_BY_NAME
from cyberterrarium.model.isa import REG_COUNT as _REG_COUNT


@dataclass
class Organism:
    """生物个体状态容器，仅包含基础数据类型，无嵌套对象。"""

    org_id: int           # 唯一标识符
    alive: bool           # 生死标记
    pc: int               # 程序计数器（genome字节索引）
    regs: list[int]       # 寄存器组 [R0, R1, R2, R3, INV, DP_X, DP_Y]
    equal_flag: bool      # CMP 比较结果
    energy: int           # 当前能量
    age: int              # 存活Tick数
    genome: bytearray     # 基因代码段
    fingerprint: set[int] | None = None  # Winnowing基因指纹缓存

    # 寄存器索引常量（从 isa.REG_TABLE 派生，唯一定义源）
    R0: int = REG_BY_NAME["R0"].index
    R1: int = REG_BY_NAME["R1"].index
    R2: int = REG_BY_NAME["R2"].index
    R3: int = REG_BY_NAME["R3"].index
    INV: int = REG_BY_NAME["INV"].index
    DP_X: int = REG_BY_NAME["DP_X"].index
    DP_Y: int = REG_BY_NAME["DP_Y"].index
    REG_COUNT: int = _REG_COUNT
