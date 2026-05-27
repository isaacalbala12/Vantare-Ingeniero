"""Tests for backend/src/services/msgpack_codec.py — MessagePack + Delta encoding."""
import pytest
import time

# Importamos msgpack directamente para verificar compatibilidad
import msgpack


class TestEncodeDecode:
    """Roundtrip encode → decode."""

    def test_encode_decode_roundtrip_flat(self) -> None:
        """Dict plano sobrevive encode→decode sin pérdida."""
        from src.services.msgpack_codec import encode, decode

        data = {"fuel": 42.3, "speed": 180, "gear": 3, "lap": 26}
        raw = encode(data)
        assert isinstance(raw, bytes)
        result = decode(raw)
        assert result == data

    def test_encode_decode_roundtrip_nested(self) -> None:
        """Dict anidado sobrevive encode→decode."""
        from src.services.msgpack_codec import encode, decode

        data = {
            "player": {"fuel": 42.3, "lap": 26},
            "tyres": {"wear": [72, 68, 65, 63]},
        }
        raw = encode(data)
        result = decode(raw)
        assert result == data

    def test_encode_decode_empty(self) -> None:
        """Dict vacío sobrevive roundtrip."""
        from src.services.msgpack_codec import encode, decode

        data: dict = {}
        raw = encode(data)
        result = decode(raw)
        assert result == data

    def test_encode_returns_bytes_not_str(self) -> None:
        """encode siempre retorna bytes, nunca str."""
        from src.services.msgpack_codec import encode

        raw = encode({"x": 1})
        assert isinstance(raw, bytes)
        assert not isinstance(raw, str)

    def test_decode_raises_on_invalid_bytes(self) -> None:
        """Bytes corruptos lanzan excepción controlada."""
        from src.services.msgpack_codec import decode

        with pytest.raises((ValueError, msgpack.exceptions.ExtraData, msgpack.exceptions.FormatError)):
            decode(b"\xff\xfe\xfd\x00INVALID")


class TestApplyDelta:
    """Merge de delta sobre frame base."""

    def test_apply_delta_merges_new_fields(self) -> None:
        """Campos del delta se aplican sobre la base."""
        from src.services.msgpack_codec import apply_delta

        base = {"fuel": 42.3, "speed": 180, "gear": 3}
        delta = {"speed": 178, "gear": 4}
        result = apply_delta(base, delta)
        assert result["fuel"] == 42.3  # sin cambios
        assert result["speed"] == 178  # actualizado
        assert result["gear"] == 4  # actualizado

    def test_apply_delta_adds_new_keys(self) -> None:
        """Keys que no existen en la base se agregan."""
        from src.services.msgpack_codec import apply_delta

        base = {"fuel": 42.3}
        delta = {"speed": 180}
        result = apply_delta(base, delta)
        assert result["fuel"] == 42.3
        assert result["speed"] == 180

    def test_apply_delta_preserves_unrelated(self) -> None:
        """Campos no mencionados en el delta permanecen intactos."""
        from src.services.msgpack_codec import apply_delta

        base = {"fuel": 42.3, "speed": 180, "gear": 3, "lap": 26}
        delta = {"speed": 178}
        result = apply_delta(base, delta)
        assert result["fuel"] == 42.3
        assert result["speed"] == 178
        assert result["gear"] == 3
        assert result["lap"] == 26

    def test_apply_delta_does_not_mutate_base(self) -> None:
        """La función no muta el dict base original."""
        from src.services.msgpack_codec import apply_delta

        base = {"fuel": 42.3, "speed": 180}
        delta = {"speed": 178}
        result = apply_delta(base, delta)
        assert base["speed"] == 180  # sin cambios
        assert result is not base  # nuevo dict

    def test_apply_delta_nested_dict_merge(self) -> None:
        """Delta anidado hace merge superficial del sub-dict."""
        from src.services.msgpack_codec import apply_delta

        base = {"player": {"fuel": 42.3, "lap": 26}}
        delta = {"player": {"fuel": 40.1}}
        result = apply_delta(base, delta)
        assert result["player"]["fuel"] == 40.1
        # Shallow merge: lap se pierde porque el sub-dict se reemplaza
        # (decisión de diseño: delta es plano, no hace deep merge)


class TestComputeDelta:
    """Cálculo de delta entre dos frames."""

    def test_compute_delta_identical_frames(self) -> None:
        """Frames idénticos producen delta solo con _t."""
        from src.services.msgpack_codec import compute_delta

        curr = {"fuel": 42.3, "speed": 180, "gear": 3}
        prev = {"fuel": 42.3, "speed": 180, "gear": 3}
        delta = compute_delta(prev, curr)
        assert "_t" in delta
        assert "fuel" not in delta
        assert "speed" not in delta
        assert "gear" not in delta

    def test_compute_delta_only_changed_fields(self) -> None:
        """Solo campos que cambiaron aparecen en el delta."""
        from src.services.msgpack_codec import compute_delta

        curr = {"fuel": 40.1, "speed": 180, "gear": 3}
        prev = {"fuel": 42.3, "speed": 180, "gear": 3}
        delta = compute_delta(prev, curr)
        assert delta["fuel"] == 40.1
        assert "speed" not in delta
        assert "gear" not in delta

    def test_compute_delta_all_changed(self) -> None:
        """Si todos los campos cambiaron, el delta contiene todos."""
        from src.services.msgpack_codec import compute_delta

        curr = {"fuel": 40.1, "speed": 178, "gear": 4}
        prev = {"fuel": 42.3, "speed": 180, "gear": 3}
        delta = compute_delta(prev, curr)
        assert delta["fuel"] == 40.1
        assert delta["speed"] == 178
        assert delta["gear"] == 4

    def test_compute_delta_null_previous(self) -> None:
        """Sin frame previo, retorna frame completo con _full=true."""
        from src.services.msgpack_codec import compute_delta

        curr = {"fuel": 42.3, "speed": 180}
        delta = compute_delta(None, curr)
        assert delta == {"fuel": 42.3, "speed": 180, "_full": True, "_t": delta["_t"]}
        assert isinstance(delta["_t"], float)

    def test_compute_delta_respects_full_flag(self) -> None:
        """Con force_full=True, todos los campos se incluyen con _full."""
        from src.services.msgpack_codec import compute_delta

        curr = {"fuel": 42.3, "speed": 180}
        prev = {"fuel": 42.3, "speed": 180}
        delta = compute_delta(prev, curr, force_full=True)
        assert delta.get("_full") is True
        assert delta["fuel"] == 42.3
        assert delta["speed"] == 180

    def test_compute_delta_timestamp_is_float(self) -> None:
        """_t es siempre un float (timestamp Unix)."""
        from src.services.msgpack_codec import compute_delta

        delta = compute_delta(None, {"x": 1})
        assert isinstance(delta["_t"], float)
        assert delta["_t"] > 0

    def test_compute_delta_does_not_mutate_inputs(self) -> None:
        """Los dicts de entrada no son mutados."""
        from src.services.msgpack_codec import compute_delta

        curr = {"fuel": 40.1}
        prev = {"fuel": 42.3}
        delta = compute_delta(prev, curr)
        assert prev["fuel"] == 42.3
        assert curr["fuel"] == 40.1
        assert delta is not curr
        assert delta is not prev


class TestIsFullFrame:
    """Detección de frame completo vs delta."""

    def test_full_frame_detected(self) -> None:
        """Frame con _full=true se detecta como completo."""
        from src.services.msgpack_codec import is_full_frame

        assert is_full_frame({"_full": True, "fuel": 42.3, "_t": 123.0})

    def test_delta_frame_not_full(self) -> None:
        """Frame sin _full se detecta como delta."""
        from src.services.msgpack_codec import is_full_frame

        assert not is_full_frame({"fuel": 42.3, "_t": 123.0})

    def test_full_frame_false_value(self) -> None:
        """Frame con _full=False NO es completo."""
        from src.services.msgpack_codec import is_full_frame

        assert not is_full_frame({"_full": False, "fuel": 42.3, "_t": 123.0})

    def test_empty_frame_not_full(self) -> None:
        """Frame vacío no es completo."""
        from src.services.msgpack_codec import is_full_frame

        assert not is_full_frame({})
