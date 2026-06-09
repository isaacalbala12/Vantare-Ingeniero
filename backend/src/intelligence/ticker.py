"""
Generador de ticker compacto para prompts del LLM.

Transforma un dict canónico de telemetría en texto compacto (~400 tokens)
que reemplaza el JSON verboso en los prompts.

Formato completo documentado en LMU/rag-dictionary.md
"""

from typing import Any, Optional


# ============================================================================
# Mapeos de abreviaturas
# ============================================================================

CLASS_ABBREV = {
    "hypercar": "HY",
    "lmh": "HY",
    "lmdh": "HY",
    "gt3": "GT3",
    "lmp2": "LMP2",
    "lmp3": "LMP3",
    "gte": "GTE",
}

SESSION_ABBREV = {
    "race": "RACE",
    "qualifying": "QUALI",
    "qual": "QUALI",
    "practice": "PRACTICE",
    "test": "TEST",
    "warmup": "WUP",
}

GRIP_ABBREV = {
    0: "GRN",
    1: "LOW",
    2: "MED",
    3: "HIG",
    4: "SAT",
}


# ============================================================================
# Funciones principales
# ============================================================================

def abbreviate_name(name: str) -> str:
    """Abrevia nombre de piloto a 3 caracteres.

    Args:
        name: Nombre completo del piloto.

    Returns:
        Nombre abreviado a 3 caracteres (mayúsculas).
        Si está vacío o es 'Driver', retorna 'DRV'.
    """
    if not name or name.lower() == "driver":
        return "DRV"

    # Tomar primeras letras de cada palabra
    parts = name.strip().split()
    if len(parts) >= 2:
        # Primera letra del nombre + primera del apellido (máx 3 chars)
        result = "".join(p[0].upper() for p in parts[:2] if p)
    else:
        result = name.strip()[:3]

    # Padding si es muy corto
    result = result.upper()
    if len(result) < 3:
        result = result.ljust(3, "X")

    return result[:3]


def _format_time(seconds: float) -> str:
    """Formatea segundos a MM:SS o H:MM:SS.

    Args:
        seconds: Tiempo en segundos.

    Returns:
        Tiempo formateado. Si >= 3600s, incluye horas.
    """
    total_seconds = int(seconds)
    if total_seconds >= 3600:
        hours = total_seconds // 3600
        remaining = total_seconds % 3600
        minutes = remaining // 60
        secs = remaining % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        minutes = total_seconds // 60
        secs = total_seconds % 60
        return f"{minutes}:{secs:02d}"


def _format_laptime(seconds: float) -> str:
    """Formatea tiempo de vuelta para ticker/TTS (coloquial si < 60s)."""
    from src.intelligence.time_format import format_laptime
    return format_laptime(seconds, colloquial=True)


def _format_drv(data: dict) -> str:
    """Formatea línea DRV (Datos del piloto).

    Formato:
        DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{w}/{w}/{w}/{w}·{t}/{t}/{t}/{t}

    Nota: TYR se omite si lap <= 3
    """
    lap = data.get("lap", 0)
    pos = data.get("position", 0)
    fuel = data.get("fuel", 0.0)
    consumo = data.get("fuel_rate_trend", 0.0)
    laps_rest = data.get("laps_rest", 0)
    wear = data.get("tyre_wear", [0, 0, 0, 0])
    temps = data.get("tyre_temps", [0, 0, 0, 0])

    # Asegurar que tenemos 4 valores
    while len(wear) < 4:
        wear.append(0)
    while len(temps) < 4:
        temps.append(0)

    parts = [
        f"DRV:P{pos}",
        f"L{lap}",
        f"F:{fuel}L/{consumo}({laps_rest}L)",
    ]

    # TYR solo si lap > 3
    if lap > 3:
        tyrr = f"TYR:{int(wear[0])}/{int(wear[1])}/{int(wear[2])}/{int(wear[3])}·{int(temps[0])}/{int(temps[1])}/{int(temps[2])}/{int(temps[3])}"
        parts.append(tyrr)

    return "|".join(parts)


def _format_brk(data: dict) -> str:
    """Formatea línea BRK (Desgaste de frenos).

    Formato:
        BRK:{wFL}/{wFR}/{wRL}/{wRR}

    Retorna string vacío si todos los valores son 0.
    """
    brake = data.get("brake_wear", [0, 0, 0, 0])

    # Asegurar que tenemos 4 valores
    while len(brake) < 4:
        brake.append(0)

    # Omitir si todos son 0
    if all(w == 0 for w in brake):
        return ""

    return f"BRK:{int(brake[0])}/{int(brake[1])}/{int(brake[2])}/{int(brake[3])}"


def _format_gap(data: dict) -> str:
    """Formatea línea GAP (Diferencias con rivales).

    Formato:
        GAP>{ahead}:+{gap}·{best}|<{behind}:{gap}·{best}·d{delta}

    Se omiten secciones si no hay rival.
    """
    ahead_name = data.get("ahead_name")
    ahead_gap = data.get("ahead_gap")
    ahead_best = data.get("ahead_best")
    behind_name = data.get("behind_name")
    behind_gap = data.get("behind_gap")
    behind_best = data.get("behind_best")
    delta = data.get("delta", 0.0)

    parts = ["GAP"]

    # Sección adelante (>)
    if ahead_name and ahead_gap is not None:
        best_str = _format_laptime(ahead_best) if ahead_best else "0:00.0"
        parts.append(f">{abbreviate_name(ahead_name)}:+{ahead_gap}·{best_str}")

    # Sección atrás (<)
    if behind_name and behind_gap is not None:
        best_str = _format_laptime(behind_best) if behind_best else "0:00.0"
        # Gap detrás siempre es negativo (estás por delante)
        parts.append(f"|<{abbreviate_name(behind_name)}:-{behind_gap}·{best_str}·d{delta}")

    return "".join(parts)


def _format_ses(data: dict) -> str:
    """Formatea línea SES (Información de sesión).

    Formato:
        SES:{clase}|{tipo}|{total}L|{tiempo}
    """
    clase = data.get("session_class", "GT3")
    tipo = data.get("session_type", "RACE")
    total = data.get("total_laps", 0)
    time_left = data.get("time_left", 0)

    # Abreviar clase
    clase_abbr = CLASS_ABBREV.get(clase.lower(), clase.upper()[:3])

    # Abreviar tipo de sesión
    tipo_abbr = SESSION_ABBREV.get(tipo.lower(), tipo.upper()[:7])

    # Formatear tiempo
    time_str = _format_time(time_left)

    return f"SES:{clase_abbr}|{tipo_abbr}|{total}L|{time_str}"


def _format_wth(data: dict) -> str:
    """Formatea línea WTH (Clima y condiciones).

    Formato:
        WTH:{grip}|{temp}°|{rain}%+{min}|SC:{S/N}
    """
    grip = data.get("grip", 0)
    temp = data.get("ambient_temp", 20)
    rain_chance = data.get("rain_chance", 0)
    rain_min = data.get("rain_min", 0)
    sc = data.get("safety_car_active", False)

    grip_str = GRIP_ABBREV.get(grip, "MED")
    sc_str = "S" if sc else "N"

    return f"WTH:{grip_str}|{temp}°|{rain_chance}%+{rain_min}m|SC:{sc_str}"


def _format_riv(data: dict) -> str:
    """Formatea línea RIV (Rivales).

    Formato:
        RIV:{total} cars
        CLS1({n}):{detalle}·...
        CLS2({n}):{detalle}·...
        FAR({n}):+{max_gap}s behind
        LAP({n}):{name}(-{n}L)·...
    """
    total = data.get("total_cars", 0)
    competitors = data.get("competitors", [])

    lines = [f"RIV:{total} cars"]

    # Clasificar competidores
    cls1 = []  # gap < 5s
    cls2 = []  # gap 5-30s
    far = []   # gap > 30s
    lap = []   # laps_behind >= 1

    max_far_gap = 0

    for comp in competitors:
        name = abbreviate_name(comp.get("name", "DRV"))
        cls = comp.get("class", "GT3")
        gap = comp.get("gap", 0.0)
        laps = comp.get("laps", 0)
        laps_behind = comp.get("laps_behind", 0)

        # Rivales doblados
        if laps_behind >= 1:
            lap.append(f"{name}(-{laps_behind}L)")
            continue

        # Clasificar por gap
        if gap < 5:
            cls1.append(f"{name}|{cls}|+{gap}|V{laps}")
        elif gap <= 30:
            cls2.append(f"{name}|{cls}|+{gap}|V{laps}")
        else:
            far.append(gap)
            max_far_gap = max(max_far_gap, gap)

    # Construir líneas
    if cls1:
        max_cls = int(data.get("max_cls_rivals", 0) or 0)
        cls1_display = cls1[:max_cls] if max_cls > 0 else cls1
        suffix = "·…" if max_cls > 0 and len(cls1) > max_cls else ""
        lines.append(f"CLS1({len(cls1)}):" + "·".join(cls1_display) + suffix)
    else:
        lines.append("CLS1(0):—")

    if cls2:
        lines.append(f"CLS2({len(cls2)}):" + "·".join(cls2))
    else:
        lines.append("CLS2(0):—")

    if far:
        lines.append(f"FAR({len(far)}):+{int(max_far_gap)}s behind")
    else:
        lines.append("FAR(0):—")

    if lap:
        lines.append(f"LAP({len(lap)}):" + "·".join(lap))
    else:
        lines.append("LAP(0):—")

    return "\n".join(lines)


def generate_ticker(data: dict) -> str:
    """Genera el ticker completo a partir del dict canónico.

    Args:
        data: Diccionario con campos de telemetría:

            DRV: lap, position, fuel, fuel_rate_trend, laps_rest,
                 tyre_wear, tyre_temps
            BRK: brake_wear
            GAP: ahead_name, ahead_gap, ahead_best,
                 behind_name, behind_gap, behind_best, delta
            SES: session_class, session_type, total_laps, time_left
            WTH: grip, ambient_temp, rain_chance, rain_min, safety_car_active
            RIV: total_cars, competitors

    Returns:
        String con ticker formateado (~400 tokens).
    """
    sections = []

    # DRV
    sections.append(_format_drv(data))

    # BRK (puede estar vacío)
    brk = _format_brk(data)
    if brk:
        sections.append(brk)

    # GAP
    sections.append(_format_gap(data))

    # SES
    sections.append(_format_ses(data))

    # WTH
    sections.append(_format_wth(data))

    # RIV
    sections.append(_format_riv(data))

    return "\n".join(sections)
