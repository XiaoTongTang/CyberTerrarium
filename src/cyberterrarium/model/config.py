"""全局参数配置 - 所有参数支持动态热更新"""

# --- 能量参数 ---
E_NUT: int = 200            # 单格营养能量
E_ENZ_EAT: int = 600        # 酶促进食能量
C_INST: int = 1             # 单条指令消耗（脑力税）
C_MAKE_ENZ: int = 10        # 合成酶消耗
C_MAKE_TOX: int = 1        # 合成毒素消耗
C_TOUCH_TOX: int = 50       # 触碰毒素消耗
C_MAKE_SIG: int = 2         # 合成信号消耗

# --- 移动成本参数 ---
MOVE_BASE: int = 0       # 每次移动的固定启动成本
MOVE_RATE: int = 0.45       # 每格距离的线性成本
MOVE_SPRINT: int = 0.2     # 远距离冲刺的二次惩罚系数

# --- 位图攻击参数 ---
C_ATTACK_BASE: int = 1       # 发动攻击的固定基础消耗
C_ATTACK_PER_BIT: int = 1    # 攻击范围内每个格子的额外消耗
C_DAMAGE_PER_HIT: int = 50   # 每命中一格目标生物损失的能量
C_LEECH_PER_HIT: int = 20    # 每命中一格攻击者恢复的能量

# --- 位图排放参数 ---
C_EMIT_ENZ: int = 1          # 排放一格酶的基础消耗
C_EMIT_TOX: int = 1          # 排放一格毒素的基础消耗
C_EMIT_SIG: float = 0.1      # 排放一格信号的基础消耗

# --- 生命周期参数 ---
E_BIRTH: int = 150          # 出生初始能量
C_BASE: int = 150            # 复制基础消耗
C_PER_INST: int = 1         # 复制单条指令消耗
REPRO_ENERGY_MULTIPLIER: float = 5.0  # 繁殖所需能量的倍数阈值
AGE_LIMIT: int = 3000      # 最大年龄（Tick数）
MAX_POP: int = 10000        # 最大人口

# --- 世界参数 ---
WORLD_WIDTH: int = 200
WORLD_HEIGHT: int = 200
NUTRIENT_SPAWN_RATE: float = 0.03  # 每个空白格在营养生成Tick生成营养的概率
NUTRIENT_LIFE: int = 127  # 营养生命周期（Tick数），归零后变空
ENZ_LIFE: int = 100      # 酶环境衰减寿命（Tick数），归零后变空

# --- 突变引擎参数 ---
MUTATION_ENABLED: bool = True
POINT_MUTATION_RATE: float = 0.05      # 每条指令点突变概率
STRUCT_INSERTION_RATE: float = 0.02   # 片段插入概率
STRUCT_DELETION_RATE: float = 0.02    # 片段缺失概率
MIN_GENOME_LENGTH: int = 8             # 最短基因组（2条指令）
MAX_GENOME_LENGTH: int = 200           # 最长基因组（50条指令）
