"""
Index and player synchronization logic.

Handles mapping between different indexes used in LMU's telemetry and scoring arrays.
"""

INVALID_INDEX = -1


def local_scoring_index(scoring_veh) -> int:
    """Find local player scoring index in the scoring array.

    Args:
        scoring_veh: Iterable of scoring vehicle structures (e.g. vehScoringInfo).

    Returns:
        Index of the local player, or INVALID_INDEX if not found.
    """
    for scor_idx, veh_info in enumerate(scoring_veh):
        if veh_info.mIsPlayer:
            return scor_idx
    return INVALID_INDEX


class TelemetrySync:
    """Synchronize data indices between scoring and telemetry."""

    def __init__(self) -> None:
        # Maps vehicle ID (mID) to telemetry array index
        self._tele_indexes = {}

    def update_tele_indexes(self, veh_total: int, telemetry_data) -> None:
        """Update telemetry index lookup dictionary using mID matching.

        Telemetry indexes can be different from scoring indexes.
        We build a mapping of mID -> telemetry index.
        """
        self._tele_indexes.clear()
        for tele_idx in range(min(veh_total, len(telemetry_data.telemInfo))):
            veh_info = telemetry_data.telemInfo[tele_idx]
            self._tele_indexes[veh_info.mID] = tele_idx

    def sync_tele_index(self, scor_idx: int, scoring_data) -> int:
        """Find telemetry index corresponding to scoring index.

        Uses the scoring index to find the vehicle's mID, then looks up
        the corresponding telemetry index from the mapping dictionary.
        """
        if scor_idx == INVALID_INDEX or scor_idx >= len(scoring_data.vehScoringInfo):
            return INVALID_INDEX

        mID = scoring_data.vehScoringInfo[scor_idx].mID
        return self._tele_indexes.get(mID, INVALID_INDEX)

    def sync_player_data(self, shmm_data):
        """Find player indices and data references in shared memory.

        Args:
            shmm_data: LMUObjectOut ctypes structure containing all shared memory.

        Returns:
            A tuple of (scor_idx, tele_idx, player_scor, player_tele)
        """
        veh_total = shmm_data.scoring.scoringInfo.mNumVehicles
        self.update_tele_indexes(veh_total, shmm_data.telemetry)

        scor_idx = local_scoring_index(shmm_data.scoring.vehScoringInfo)
        if scor_idx == INVALID_INDEX:
            return INVALID_INDEX, INVALID_INDEX, None, None

        tele_idx = self.sync_tele_index(scor_idx, shmm_data.scoring)
        player_scor = shmm_data.scoring.vehScoringInfo[scor_idx]
        player_tele = None

        if tele_idx != INVALID_INDEX:
            player_tele = shmm_data.telemetry.telemInfo[tele_idx]

        return scor_idx, tele_idx, player_scor, player_tele
