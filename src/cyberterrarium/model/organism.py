"""生物实体 - 扁平化数据容器"""

from dataclasses import dataclass


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

    # 寄存器索引常量
    R0: int = 0
    R1: int = 1
    R2: int = 2
    R3: int = 3
    INV: int = 4
    DP_X: int = 5
    DP_Y: int = 6
    REG_COUNT: int = 7
