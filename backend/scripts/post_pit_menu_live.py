"""Live LMU PitMenu POST test (requires user in pits / garage menu)."""
import asyncio

from src.intelligence.crewchief_events.pit_menu import PitMenuClient
from src.services import lmu_api


def _fuel_snapshot(menu: list) -> dict | None:
    for item in menu:
        if isinstance(item, dict) and item.get("name") == "FUEL:":
            idx = int(item.get("currentSetting") or 0)
            settings = item.get("settings") or []
            label = settings[idx].get("text") if 0 <= idx < len(settings) else "?"
            return {"index": idx, "label": label}
    return None


async def main() -> None:
    before_menu = await lmu_api.get_pit_menu()
    before = _fuel_snapshot(before_menu)
    print("BEFORE:", before)

    client = PitMenuClient(lmu_api, dry_run=False)
    result = await client.set_fuel_level(18)
    print("POST result:", result)

    after_menu = await lmu_api.get_pit_menu()
    after = _fuel_snapshot(after_menu)
    print("AFTER:", after)

    if before and after:
        if before["index"] != after["index"] or before["label"] != after["label"]:
            print("OK: fuel setting changed in LMU.")
        else:
            print("WARN: fuel setting unchanged — check you are in pit menu / garage.")


if __name__ == "__main__":
    asyncio.run(main())
