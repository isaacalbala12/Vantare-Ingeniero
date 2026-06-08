# backend/tests/test_lmu_pit_menu_write.py
import pytest

from src.intelligence.crewchief_events.pit_menu import PitMenuClient


class FakeLMUApi:
    def __init__(self):
        self.posted = None
        self.menu = [
            {
                "name": "FUEL:",
                "currentSetting": 0,
                "settings": [{"text": "10"}, {"text": "20"}, {"text": "30"}],
            }
        ]

    async def get_pit_menu(self):
        return self.menu

    async def post_pit_menu(self, menu):
        self.posted = menu
        return True


@pytest.mark.asyncio
async def test_set_fuel_level_posts_smallest_sufficient_choice():
    api = FakeLMUApi()
    client = PitMenuClient(api, dry_run=False)

    result = await client.set_fuel_level(18)

    assert result == "Fuel level set to 20 litres."
    assert api.posted[0]["currentSetting"] == 1


@pytest.mark.asyncio
async def test_dry_run_does_not_post():
    api = FakeLMUApi()
    client = PitMenuClient(api, dry_run=True)

    result = await client.set_fuel_level(18)

    assert result == "Dry run: fuel level would be set to 20 litres."
    assert api.posted is None


@pytest.mark.asyncio
async def test_set_virtual_energy_posts_percentage_choice():
    api = FakeLMUApi()
    api.menu = [
        {
            "name": "VIRTUAL ENERGY:",
            "currentSetting": 0,
            "settings": [{"text": "0"}, {"text": "50"}, {"text": "100"}],
        }
    ]
    client = PitMenuClient(api, dry_run=False)

    result = await client.set_virtual_energy(50)

    assert result == "Virtual energy set to 50 percent."
    assert api.posted[0]["currentSetting"] == 1


@pytest.mark.asyncio
async def test_set_fuel_level_parses_lmu_style_labels():
    api = FakeLMUApi()
    api.menu = [
        {
            "name": "FUEL:",
            "currentSetting": 0,
            "settings": [{"text": "5L/2 laps"}, {"text": "18L/4 laps"}, {"text": "20L/5 laps"}],
        }
    ]
    client = PitMenuClient(api, dry_run=False)

    result = await client.set_fuel_level(18)

    assert result == "Fuel level set to 18 litres."
    assert api.posted[0]["currentSetting"] == 1


@pytest.mark.asyncio
async def test_set_fuel_ratio_posts_percentage_offset():
    api = FakeLMUApi()
    api.menu = [
        {
            "name": "FUEL RATIO:",
            "currentSetting": 0,
            "settings": [{"text": "5"}, {"text": "6"}, {"text": "7"}],
        }
    ]
    client = PitMenuClient(api, dry_run=False)

    result = await client.set_fuel_ratio(7)

    assert result == "Fuel ratio set to 7 percent."
    assert api.posted[0]["currentSetting"] == 2
