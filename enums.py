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

class siacode(Enum):
    none =            -1
    bypass =          0
    unbypass =        1
    group_bypass =    2
    group_unbypass =  3
    present_arm =     4
    present_disarm =  5
    arm =             6
    disarm =          7
    alarm_disarm =    8
    keyboard_arm =    9
    keyboard_disarm = 10
    triggerzone =     11
    restorezone =     12
    trigger =         13
    restore =         14




