"""Check available models on LM Studio server."""
import httpx
r = httpx.get("http://192.168.1.41:1234/api/v1/models", timeout=5)
data = r.json()
print(f"Status: {r.status_code}")
for m in data.get("models", []):
    key = m.get("key", "?")
    display = m.get("display_name", "?")
    loaded = len(m.get("loaded_instances", [])) > 0
    print(f"  {key} | {display} | loaded={loaded}")
