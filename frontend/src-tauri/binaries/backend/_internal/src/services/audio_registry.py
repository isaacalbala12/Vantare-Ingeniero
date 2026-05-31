class AudioRegistry:
    """Registro de audios pre-grabados para triggers deterministas.

    Si un trigger tiene audio_file_id registrado aquí, se usa audio pre-grabado.
    Si no, el sistema usa TTS cloud.
    """

    PRE_RECORDED = {
        # Spotter
        "spotter/car_left": True,
        "spotter/car_right": True,
        "spotter/three_wide": True,
        "spotter/three_wide_on_right": True,
        "spotter/three_wide_on_left": True,
        "spotter/still_there": True,
        "spotter/clear_left": True,
        "spotter/clear_right": True,
        "spotter/clear_all_round": True,

        # Posición
        "position/leading": True,
        "position/pole": True,
        "position/p1": True,
        "position/p2": True,
        "position/p3": True,
        "position/last": True,
        "position/good_start": True,
        "position/bad_start": True,
        "position/overtaking": True,
        "position/being_overtaken": True,

        # Tiempo
        "race_time/five_minutes_left": True,
        "race_time/two_minutes_left": True,
        "race_time/zero_minutes_left": True,
        "race_time/half_way": True,
        "race_time/last_lap": True,

        # Vueltas
        "lap_times/personal_best": True,
        "lap_times/best_lap_in_race": True,
        "lap_times/consistent": True,
        "lap_times/improving": True,
        "lap_times/worsening": True,

        # Combustible
        "fuel/low_warning": True,
        "fuel/critical": True,
        "fuel/half_tank": True,
        "fuel/pit_now": True,

        # Neumáticos
        "tyres/cold": True,
        "tyres/hot": True,
        "tyres/cooking": True,
        "tyres/knackered": True,
        "tyres/puncture": True,

        # Daños
        "damage/collision": True,
        "damage/major": True,
        "damage/critical": True,
        "damage/engine": True,
        "damage/suspension": True,

        # Motor
        "engine/overheating": True,
        "engine/stalled": True,
        "engine/low_oil_pressure": True,

        # Banderas
        "flags/yellow": True,
        "flags/green": True,
        "flags/blue_flag": True,
        "flags/fcy_start": True,
        "flags/fcy_green": True,

        # Penalizaciones
        "penalties/cut_track": True,
        "penalties/slow_down": True,

        # Pit Stops
        "pits/pit_window_open": True,
        "pits/box_this_lap": True,
        "pits/engage_limiter": True,
        "pits/disengage_limiter": True,

        # Sesión
        "session/last_lap": True,
        "session/two_to_go": True,
        "session/green_flag": True,
        "session/won_race": True,
        "session/podium_finish": True,
        "session/end_of_session": True,
    }

    @classmethod
    def has_audio(cls, audio_file_id: str) -> bool:
        """¿Existe audio pre-grabado para este trigger?"""
        return audio_file_id in cls.PRE_RECORDED

    @classmethod
    def get_audio_path(cls, audio_file_id: str) -> str | None:
        """Devuelve la ruta del archivo de audio si existe."""
        if cls.has_audio(audio_file_id):
            return f"audio/{audio_file_id}.wav"
        return None

    @classmethod
    def needs_tts(cls, audio_file_id: str | None) -> bool:
        """¿Necesita TTS este trigger?"""
        if audio_file_id is None:
            return True
        return not cls.has_audio(audio_file_id)
