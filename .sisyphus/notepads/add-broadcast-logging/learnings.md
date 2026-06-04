## 2026-06-02: AudioPlayer broadcast logging + tests

- Added logger.debug("Broadcasting crewchief event: %s", msg.name) at line 215 of audio_player.py
- Created ackend/tests/test_audio_player_broadcast.py with 3 tests:
  1. 	est_broadcast_called_when_callback_set — verifies callback is invoked
  2. 	est_broadcast_not_called_when_callback_none — verifies graceful skip when callback=None
  3. 	est_broadcast_exception_does_not_crash — verifies exception in callback is caught
- Test pattern: mock SoundCache returns a SoundEntry, use NullAudioOutput to avoid PyAudio dependency
- All 3 tests pass: `3 passed in 1.31s`
