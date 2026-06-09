"""Probe live LMU PitMenu REST (dry-run only)."""
import asyncio

from src.intelligence.crewchief_events.pit_menu import PitMenuClient
from src.services import lmu_api


async def main() -> None:
    menu = await lmu_api.get_pit_menu()
    names = [item.get("name") for item in menu if isinstance(item, dict)]
    print("Menu categories:", names[:25], "... total", len(names))

    for item in menu:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "")
        if name in ("FUEL:", "VIRTUAL ENERGY:", "FUEL RATIO:"):
            settings = [s.get("text") for s in (item.get("settings") or [])[:10]]
            cur = item.get("currentSetting")
            print(f"  {name} current={cur} options={settings}")

    client = PitMenuClient(lmu_api, dry_run=True)
    print("--- dry_run ---")
    print(await client.set_fuel_level(18))
    print(await client.set_virtual_energy(50))
    print(await client.set_fuel_ratio(7))


if __name__ == "__main__":
    asyncio.run(main())
