import os
filepath = os.path.join(os.path.dirname(__file__), "src", "services", "llm_service.py")
if os.path.exists(filepath):
    os.remove(filepath)
    print(f"Deleted: {filepath}")
else:
    print(f"File not found: {filepath}")
print(f"Still exists: {os.path.exists(filepath)}")
