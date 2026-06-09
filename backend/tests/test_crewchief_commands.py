import pytest

from src.intelligence.crewchief_events.commands import count_fast_intent_groups, match_fast_command, match_radio_check
from src.intelligence.engine import IntelligenceEngine
from src.models.messages import AlertMessage


def test_match_fuel_status_spanish():
    command = match_fast_command("cuanto combustible queda")

    assert command is not None
    assert command.intent == "fuel_status"


def test_match_keep_quiet_no_digas_nada():
    command = match_fast_command("Por favor, no digas nada.")
    assert command is not None
    assert command.intent == "speak_only_on"

    command = match_fast_command("callate hasta que te pregunte")

    assert command is not None
    assert command.intent == "speak_only_on"


def test_count_fast_intent_groups_mixed():
    assert count_fast_intent_groups("cállate y dime el gap") >= 2


def test_count_fast_intent_groups_open():
    assert count_fast_intent_groups("explicame la estrategia completa de carrera") == 0


def test_unknown_command_falls_back_to_llm():
    assert match_fast_command("explicame la estrategia completa de carrera") is None


def test_match_spotter_disable():
    from src.intelligence.crewchief_events.commands import match_spotter_fast_command

    assert match_spotter_fast_command("don't spot") == "disable"


def test_match_spotter_enable_command():
    command = match_fast_command("spot")
    assert command is not None
    assert command.intent == "spotter_enable"


def test_match_radio_check_pure():
    assert match_radio_check("¿me escuchas?") is True
    assert match_radio_check("Hola ingeniero, me oyes") is True
    assert match_radio_check("radio check") is True


def test_match_radio_check_rejects_mixed():
    assert match_radio_check("me escuchas, ¿cómo van los neumáticos?") is False
    assert match_radio_check("¿me escuchas? dime el combustible") is False


@pytest.mark.asyncio
async def test_handle_pilot_question_radio_check_fast_path():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    await eng.handle_pilot_question("¿me escuchas?")

    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert len(alerts) == 1
    assert "recepción clara" in alerts[0].message.lower()
    assert alerts[0].payload.get("fast_command") is True


@pytest.mark.asyncio
async def test_handle_pilot_question_speak_only_on_fast_path():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    spotter = type("SpotterStub", (), {"enabled": True})()
    eng.set_spotter_service(spotter)
    await eng.handle_pilot_question("cállate hasta que te pregunte")

    assert eng.verbosity.speak_only_when_spoken_to is True
    assert spotter.enabled is False
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert any("solo hablaré" in a.message.lower() for a in alerts)
    assert alerts[-1].category == "voice_response"


@pytest.mark.asyncio
async def test_speak_only_off_restores_spotter():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    spotter = type("SpotterStub", (), {"enabled": True})()
    eng.set_spotter_service(spotter)
    eng.apply_speak_only(True, emit_voice=False)
    assert spotter.enabled is False

    eng.apply_speak_only(False, emit_voice=False)
    assert spotter.enabled is True
    assert eng.verbosity.speak_only_when_spoken_to is False


@pytest.mark.asyncio
async def test_handle_pilot_question_speak_only_off_fast_path():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.verbosity.set_speak_only_when_spoken_to(True)
    await eng.handle_pilot_question("puedes hablar normal")

    assert eng.verbosity.speak_only_when_spoken_to is False
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert any("modo normal" in a.message.lower() for a in alerts)
