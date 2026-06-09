from __future__ import annotations

import re


def _parse_litres(text: str) -> int | None:
    raw = str(text).strip()
    match = re.match(r"^(\d+)", raw)
    if match:
        return int(match.group(1))
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else None


class PitMenuClient:
    def __init__(self, lmu_api, *, dry_run: bool = True) -> None:
        self._lmu_api = lmu_api
        self._dry_run = dry_run

    async def set_fuel_level(self, required_litres: int) -> str:
        menu = await self._lmu_api.get_pit_menu()
        fuel = next((item for item in menu if item.get("name") == "FUEL:"), None)
        if not fuel:
            return "Fuel menu is not available."
        settings = list(fuel.get("settings") or [])
        selected_index = None
        selected_litres = None
        for index, setting in enumerate(settings):
            litres = _parse_litres(setting.get("text", ""))
            if litres is not None and litres >= required_litres:
                selected_index = index
                selected_litres = litres
                break
        if selected_index is None:
            selected_index = max(0, len(settings) - 1)
            selected_litres = _parse_litres(settings[selected_index].get("text", "")) or required_litres
        fuel["currentSetting"] = selected_index
        if self._dry_run:
            return f"Dry run: fuel level would be set to {selected_litres} litres."
        ok = await self._lmu_api.post_pit_menu(menu)
        if not ok:
            return "LMU rejected the pit menu update."
        return f"Fuel level set to {selected_litres} litres."

    async def set_virtual_energy(self, percentage: int) -> str:
        return await self._set_numeric_category("VIRTUAL ENERGY:", percentage, "Virtual energy", "percent")

    async def set_fuel_ratio(self, percentage: int) -> str:
        return await self._set_numeric_category("FUEL RATIO:", percentage, "Fuel ratio", "percent")

    async def set_tyre_compound(self, label: str) -> str:
        menu = await self._lmu_api.get_pit_menu()
        item = next((entry for entry in menu if str(entry.get("name", "")).upper().startswith("TYRE")), None)
        if not item:
            return "Tyre menu is not available."
        label_lower = label.strip().lower()
        for index, setting in enumerate(item.get("settings") or []):
            text = str(setting.get("text", ""))
            if label_lower in text.lower():
                item["currentSetting"] = index
                if self._dry_run:
                    return f"Dry run: tyres would be set to {text}."
                ok = await self._lmu_api.post_pit_menu(menu)
                if not ok:
                    return "LMU rejected the pit menu update."
                return f"Tyres set to {text}."
        return f"Tyre option '{label}' is not available."

    async def _set_numeric_category(self, category: str, required: int, label: str, unit: str) -> str:
        menu = await self._lmu_api.get_pit_menu()
        item = next((entry for entry in menu if entry.get("name") == category), None)
        if not item:
            return f"{label} menu is not available."
        selected_index = None
        selected_value = None
        for index, setting in enumerate(item.get("settings") or []):
            value = _parse_litres(setting.get("text", ""))
            if value == required:
                selected_index = index
                selected_value = value
                break
        if selected_index is None:
            return f"{label} value {required} {unit} is not available."
        item["currentSetting"] = selected_index
        if self._dry_run:
            return f"Dry run: {label.lower()} would be set to {selected_value} {unit}."
        ok = await self._lmu_api.post_pit_menu(menu)
        if not ok:
            return "LMU rejected the pit menu update."
        return f"{label} set to {selected_value} {unit}."
