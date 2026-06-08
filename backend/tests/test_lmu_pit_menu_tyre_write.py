import pytest

from src.intelligence.crewchief_events.pit_menu import PitMenuClient


class FakeLMUApi:
    def __init__(self):
        self.menu = [
            {
                "name": "TYRES:",
                "currentSetting": 0,
                "settings": [{"text": "Primary"}, {"text": "Alternate"}],
            }
        ]
        self.posted = None

    async def get_pit_menu(self):
        return self.menu

    async def post_pit_menu(self, menu):
        self.posted = menu
        return True


@pytest.mark.asyncio
async def test_set_tyre_compound_posts_menu():
    api = FakeLMUApi()
    client = PitMenuClient(api, dry_run=False)
    result = await client.set_tyre_compound("Alternate")
    assert "Alternate" in result
    assert api.posted[0]["currentSetting"] == 1
