import os

filepath = "/home/isaac-albala/Vantare-Ingeniero/backend/src/services/llm_service.py"

if os.path.exists(filepath):
    os.remove(filepath)
    print(f"Deleted: {filepath}")
else:
    print(f"File does not exist: {filepath}")

# Verify deletion
if os.path.exists(filepath):
    print("FAIL: File still exists")
else:
    print("SUCCESS: File no longer exists")
