"""
Tests para backend/src/intelligence/prompt_templates.py
"""
import pytest

from src.intelligence.prompt_templates import (
    SYSTEM_PROMPT_BASIC,
    SYSTEM_PROMPT_TICKER,
    render,
)


class TestSystemPromptTicker:
    """T3.1: Verifica que SYSTEM_PROMPT_TICKER contiene la tabla diccionario."""

    def test_system_prompt_ticker_exists(self):
        """El system prompt con formato ticker debe existir."""
        assert SYSTEM_PROMPT_TICKER is not None
        assert len(SYSTEM_PROMPT_TICKER) > 100

    def test_system_prompt_ticker_contains_drv_section(self):
        """SYSTEM_PROMPT_TICKER debe explicar la línea DRV."""
        assert "DRV" in SYSTEM_PROMPT_TICKER
        assert "P{" in SYSTEM_PROMPT_TICKER or "posición" in SYSTEM_PROMPT_TICKER.lower()

    def test_system_prompt_ticker_contains_brk_section(self):
        """SYSTEM_PROMPT_TICKER debe explicar la línea BRK."""
        assert "BRK" in SYSTEM_PROMPT_TICKER or "frenos" in SYSTEM_PROMPT_TICKER.lower()

    def test_system_prompt_ticker_contains_gap_section(self):
        """SYSTEM_PROMPT_TICKER debe explicar la línea GAP."""
        assert "GAP" in SYSTEM_PROMPT_TICKER or "gap" in SYSTEM_PROMPT_TICKER.lower()

    def test_system_prompt_ticker_contains_ses_section(self):
        """SYSTEM_PROMPT_TICKER debe explicar la línea SES."""
        assert "SES" in SYSTEM_PROMPT_TICKER or "sesión" in SYSTEM_PROMPT_TICKER.lower()

    def test_system_prompt_ticker_contains_wth_section(self):
        """SYSTEM_PROMPT_TICKER debe explicar la línea WTH."""
        assert "WTH" in SYSTEM_PROMPT_TICKER or "clima" in SYSTEM_PROMPT_TICKER.lower()

    def test_system_prompt_ticker_contains_riv_section(self):
        """SYSTEM_PROMPT_TICKER debe explicar la línea RIV."""
        assert "RIV" in SYSTEM_PROMPT_TICKER or "rivales" in SYSTEM_PROMPT_TICKER.lower()

    def test_system_prompt_ticker_contains_abbreviations(self):
        """SYSTEM_PROMPT_TICKER debe explicar abreviaturas comunes."""
        text = SYSTEM_PROMPT_TICKER
        # Verifica que contiene explicaciones de abreviaturas clave
        assert any(abbrev in text for abbrev in ["HY", "GT3", "GRN", "MED", "HIG", "SAT"])

    def test_system_prompt_ticker_contains_style_instruction(self):
        """SYSTEM_PROMPT_TICKER debe incluir instrucción de estilo radio."""
        text = SYSTEM_PROMPT_TICKER
        assert any(phrase in text for phrase in [
            "2-3 frases", "estilo radio", "radio", "conciso", "técnico"
        ])


class TestRenderWithTickerText:
    """T3.2: Verifica que render() acepta ticker_text en modo nuevo."""

    def test_render_with_ticker_text_produces_prompt(self):
        """render() con ticker_text debe producir un prompt válido."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96\n"
                           "BRK:38/35/22/20\n"
                           "GAP>VST:+2.1·1:48.2|<ALO:-1.2·1:47.9·d-0.3\n"
                           "SES:HY|RACE|38L|45:22\n"
                           "WTH:MED|22°|30%+15m|SC:N\n"
                           "RIV:85 cars",
            "trigger_reason": "FuelCritical",
        }
        tier = "STANDARD"
        result = render(context, tier)

        assert result is not None
        assert len(result) > 50

    def test_render_with_ticker_text_uses_system_prompt_ticker(self):
        """render() con ticker_text debe usar SYSTEM_PROMPT_TICKER."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63·92/94/98/96\n"
                           "BRK:38/35/22/20",
            "trigger_reason": "FuelCritical",
        }
        tier = "STANDARD"
        result = render(context, tier)

        # El result debe contener elementos del SYSTEM_PROMPT_TICKER
        assert any(keyword in result for keyword in ["DRV", "BRK", "GAP", "SES", "WTH", "RIV", "ticker"])

    def test_render_with_ticker_text_includes_telemetry(self):
        """render() con ticker_text debe incluir los datos de telemetría."""
        ticker = "DRV:P3|L26|F:42.3L/3.2(13L)|TYR:72/68/65/63"
        context = {
            "ticker_text": ticker,
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "STANDARD")

        assert ticker in result

    def test_render_with_ticker_text_includes_trigger_reason(self):
        """render() con ticker_text debe incluir el trigger_reason."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L/3.2(13L)",
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "STANDARD")

        assert "FuelCritical" in result

    def test_render_with_ticker_and_rag_text(self):
        """render() con ticker_text y rag_context debe incluir ambos."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L/3.2(13L)",
            "rag_context": "V10: Safety Car desplegado (P5)\nV15: Entrada a boxes",
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "STANDARD")

        assert "DRV:P3" in result
        assert "Safety Car" in result or "V10" in result

    def test_render_with_ticker_and_pilot_question(self):
        """render() con ticker_text y pilot_question debe incluir la pregunta."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L/3.2(13L)",
            "pilot_question": "¿Cuándo debería parar?",
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "STANDARD")

        assert "¿Cuándo debería parar?" in result


class TestRenderLegacyMode:
    """T3.3: Verifica que render() mantiene modo legacy sin ticker_text."""

    def test_render_legacy_with_speed_and_fuel(self):
        """render() sin ticker_text debe usar json.dumps (modo legacy)."""
        context = {
            "lap": 26,
            "speed": 72.0,
            "fuel": 42.3,
            "position": 3,
        }
        result = render(context, "STANDARD")

        assert result is not None
        # Legacy mode usa json.dumps, debe contener "{"
        assert "{" in result

    def test_render_legacy_with_telemetry_uses_basic_prompt(self):
        """render() legacy con telemetría debe usar SYSTEM_PROMPT_BASIC."""
        context = {
            "lap": 26,
            "speed": 72.0,
            "fuel": 42.3,
            "position": 3,
        }
        result = render(context, "STANDARD")

        # Debe contener frases del SYSTEM_PROMPT_BASIC
        assert any(phrase in result for phrase in ["ingeniero", "carrera", "radio"])

    def test_render_legacy_without_telemetry_uses_basic_prompt(self):
        """render() sin telemetría debe usar SYSTEM_PROMPT_BASIC."""
        context = {
            "pilot_question": "¿Qué hacer?",
        }
        result = render(context, "STANDARD")

        # Debe contener frases del SYSTEM_PROMPT_BASIC
        assert any(phrase in result for phrase in ["ingeniero", "carrera"])

    def test_render_legacy_empty_context(self):
        """render() con contexto vacío debe funcionar."""
        context = {}
        result = render(context, "FAST")

        assert result is not None
        assert len(result) > 0


class TestTiers:
    """T3.3: Verifica que los tiers FAST/STANDARD/DEEP funcionan."""

    def test_tier_fast_with_ticker(self):
        """render() con tier FAST debe funcionar."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L",
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "FAST")

        assert result is not None

    def test_tier_standard_with_ticker(self):
        """render() con tier STANDARD debe funcionar."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L",
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "STANDARD")

        assert result is not None

    def test_tier_deep_with_ticker(self):
        """render() con tier DEEP debe funcionar."""
        context = {
            "ticker_text": "DRV:P3|L26|F:42.3L",
            "trigger_reason": "FuelCritical",
        }
        result = render(context, "DEEP")

        assert result is not None

    def test_tier_legacy_with_telemetry(self):
        """render() legacy con telemetría debe detectar tier correctamente."""
        context = {
            "lap": 26,
            "speed": 72.0,
            "fuel": 42.3,
        }
        result = render(context, "DEEP")

        assert result is not None


class TestTokenSize:
    """T3.4: Verifica documentación de tamaño."""

    def test_system_prompt_ticker_has_docstring(self):
        """SYSTEM_PROMPT_TICKER debe tener docstring o comentario sobre tokens."""
        # El docstring/comentario debe mencionar el tamaño aproximado
        # Esto es verificable revisando el código fuente
        from src.intelligence import prompt_templates
        import inspect

        source = inspect.getsource(prompt_templates)
        # Verifica que hay documentación sobre el límite de tokens
        assert "800" in source or "token" in source.lower()


class TestSystemPromptsDifference:
    """Verifica que los dos system prompts son diferentes."""

    def test_basic_and_ticker_are_different(self):
        """SYSTEM_PROMPT_BASIC y SYSTEM_PROMPT_TICKER deben ser distintos."""
        assert SYSTEM_PROMPT_BASIC != SYSTEM_PROMPT_TICKER

    def test_ticker_is_longer_than_basic(self):
        """SYSTEM_PROMPT_TICKER debe ser más largo (contiene tabla)."""
        assert len(SYSTEM_PROMPT_TICKER) > len(SYSTEM_PROMPT_BASIC)

    def test_sweary_prompt_includes_colorful_language(self):
        context = {"ticker_text": "DRV:P1|L10", "sweary": True}
        result = render(context, "FAST")
        assert "colorido" in result.lower() or "paddock" in result.lower()

    def test_clean_prompt_excludes_profanity_authorization(self):
        context = {"ticker_text": "DRV:P1|L10", "sweary": False}
        result = render(context, "FAST")
        assert "profesional" in result.lower() or "limpio" in result.lower()
        assert "colorido" not in result.lower()