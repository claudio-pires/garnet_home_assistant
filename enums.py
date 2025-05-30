from enum import Enum

class arm_modes(Enum):
    home = 1
    away = 2


class zonestatus(Enum):
    unknown = -1
    true = 1
    false = 0


class emergencytype(Enum):
    medical = 1
    unknown = 2
    fire = 3
    panic = 4
    





