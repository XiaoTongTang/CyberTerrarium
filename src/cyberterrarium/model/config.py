"""全局参数配置 - 所有参数支持动态热更新"""

# --- 能量参数 ---
E_NUT: int = 100            # 单格营养能量
E_ENZ_EAT: int = 400        # 酶促进食能量
C_INST: int = 1             # 单条指令消耗（脑力税）
C_MAKE_ENZ: int = 30        # 合成酶消耗
C_MAKE_TOX: int = 20        # 合成毒素消耗
C_TOUCH_TOX: int = 50       # 触碰毒素消耗
C_MAKE_SIG: int = 5         # 合成信号消耗

# --- 生命周期参数 ---
E_BIRTH: int = 150          # 出生初始能量
C_BASE: int = 50            # 复制基础消耗
C_PER_INST: int = 5         # 复制单条指令消耗
AGE_LIMIT: int = 20000      # 最大年龄（Tick数）
MAX_POP: int = 10000        # 最大人口

# --- 世界参数 ---
WORLD_WIDTH: int = 200
WORLD_HEIGHT: int = 200
NUTRIENT_SPAWN_RATE: float = 0.05  # 每个空白格在营养生成Tick生成营养的概率
NUTRIENT_LIFE: int = 50  # 营养生命周期（Tick数），归零后变空

# --- 突变引擎参数 ---
MUTATION_ENABLED: bool = True
POINT_MUTATION_RATE: float = 0.02      # 每条指令点突变概率
STRUCT_INSERTION_RATE: float = 0.005   # 片段插入概率
STRUCT_DELETION_RATE: float = 0.005    # 片段缺失概率
MIN_GENOME_LENGTH: int = 8             # 最短基因组（2条指令）
MAX_GENOME_LENGTH: int = 200           # 最长基因组（50条指令）
