"""Stepfun PTT tool parsing and sanitizer guards."""

from src.intelligence.llm_client import VLLMClient
from src.intelligence.llm_speech_sanitize import sanitize_llm_speech


def test_parse_stepfun_tool_xml_maps_fuel_alias():
    raw = (
        '<tool_call>\n<function=consultar_estado_combustible>\n'
        "<parameter=tipo_consulta>\nvueltas_restantes\n</parameter>\n"
        "</function>\n</tool_call>"
    )
    parsed = VLLMClient._parse_stepfun_tool_markup(raw)
    assert parsed is not None
    assert parsed.name == "get_fuel_status"


def test_sanitize_rejects_ticker_line():
    assert sanitize_llm_speech("DRV:P3|L5|F:42L") == ""


def test_sanitize_strips_tool_call_markup():
    raw = '<tool_call><function=get_fuel_status></function></tool_call>'
    assert sanitize_llm_speech(raw) == ""
