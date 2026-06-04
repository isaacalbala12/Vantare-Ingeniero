VERBOSITY_FULL = 3
VERBOSITY_MED = 2
VERBOSITY_LOW = 1
VERBOSITY_SILENT = 0


class PlaybackModerator:
    """Adjusts message playback verbosity based on proximity of nearby traffic."""

    def __init__(self):
        self._verbosity = VERBOSITY_FULL
        self._gap_ahead = 999.0
        self._gap_behind = 999.0

    def update_traffic(self, gap_ahead: float, gap_behind: float) -> None:
        self._gap_ahead = gap_ahead
        self._gap_behind = gap_behind

    @property
    def verbosity(self) -> int:
        return self._verbosity

    def tick(self) -> None:
        min_gap = min(self._gap_ahead, self._gap_behind)
        if min_gap < 1.0:
            self._verbosity = VERBOSITY_SILENT
        elif min_gap < 2.0:
            self._verbosity = VERBOSITY_LOW
        elif min_gap < 5.0:
            self._verbosity = VERBOSITY_MED
        else:
            self._verbosity = VERBOSITY_FULL

    def should_play(self, msg_priority: int) -> bool:
        if self._verbosity >= VERBOSITY_FULL:
            return True
        if self._verbosity == VERBOSITY_MED:
            return msg_priority >= 10
        if self._verbosity == VERBOSITY_LOW:
            return msg_priority >= 15
        if self._verbosity == VERBOSITY_SILENT:
            return msg_priority >= 20
        return True
