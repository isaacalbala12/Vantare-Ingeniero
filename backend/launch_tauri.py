import subprocess, time

log = open(r"C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\frontend\tauri_dev_log.txt", "w")
proc = subprocess.Popen(
    ["cargo", "tauri", "dev"],
    stdout=log,
    stderr=subprocess.STDOUT,
    cwd=r"C:\Users\isaac\Desktop\Apps\Vantare Ingeniero\frontend",
    creationflags=subprocess.CREATE_NO_WINDOW,
)
time.sleep(15)

import urllib.request, json
try:
    r = urllib.request.urlopen("http://127.0.0.1:1420", timeout=3)
    print("Vite OK")
except Exception as e:
    print(f"Vite: {e}")

try:
    r = urllib.request.urlopen("http://127.0.0.1:8008/health", timeout=5)
    h = json.loads(r.read().decode())
    sm = h["shared_memory"]["status"]
    tts = "yes" if any("tts_service" in str(k) for k in []) else "?"
    print(f"Backend: shared_memory={sm}")
except Exception as e:
    print(f"Backend: {e}")

log.close()
