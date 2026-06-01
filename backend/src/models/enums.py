from enum import Enum


class SessionType(str, Enum):
    UNAVAILABLE = "Unavailable"
    PRACTICE = "Practice"
    QUALIFY = "Qualify"
    PRIVATE_QUALIFY = "PrivateQualify"
    RACE = "Race"
    HOT_LAP = "HotLap"
    LONE_PRACTICE = "LonePractice"


class SessionPhase(str, Enum):
    UNAVAILABLE = "Unavailable"
    GARAGE = "Garage"
    GRIDWALK = "Gridwalk"
    FORMATION = "Formation"
    COUNTDOWN = "Countdown"
    GREEN = "Green"
    FULL_COURSE_YELLOW = "FullCourseYellow"
    CHECKERED = "Checkered"
    FINISHED = "Finished"


class FlagEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    DOUBLE_YELLOW = "DOUBLE_YELLOW"
    BLUE = "BLUE"
    WHITE = "WHITE"
    BLACK = "BLACK"
    CHEQUERED = "CHEQUERED"


class FullCourseYellowPhase(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    PITS_CLOSED = "PITS_CLOSED"
    PITS_OPEN_LEAD_LAP = "PITS_OPEN_LEAD_LAP"
    PITS_OPEN = "PITS_OPEN"
    LAST_LAP_NEXT = "LAST_LAP_NEXT"
    LAST_LAP_CURRENT = "LAST_LAP_CURRENT"
    RACING = "RACING"


class FrozenOrderPhase(str, Enum):
    NONE = "None"
    FCY = "FullCourseYellow"
    FORMATION = "FormationStanding"
    ROLLING = "Rolling"


class FrozenOrderColumn(str, Enum):
    NONE = "None"
    LEFT = "Left"
    RIGHT = "Right"


class FrozenOrderAction(str, Enum):
    NONE = "None"
    FOLLOW = "Follow"
    CATCH_UP = "CatchUp"
    ALLOW_TO_PASS = "AllowToPass"


class PitWindow(str, Enum):
    UNAVAILABLE = "Unavailable"
    CLOSED = "Closed"
    OPEN = "Open"


class ControlType(str, Enum):
    PLAYER = "Player"
    AI = "AI"
    REMOTE = "Remote"
    REPLAY = "Replay"


class TyreType(str, Enum):
    SOFT = "Soft"
    MEDIUM = "Medium"
    HARD = "Hard"
    WET = "Wet"
    INTERMEDIATE = "Intermediate"
