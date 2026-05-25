import subprocess
import wave
import numpy as np
import tempfile
import os

llama_bin = r"llama.cpp\build\bin\Release\llama-cli.exe"
model_path = r"models\voxtral-tts\voxtral-tts-q4.gguf"
text = "Hola piloto, ¿cómo va la carrera?"

# Ejecutar llama.cpp con el modelo TTS
cmd = [
    llama_bin,
    "-m", model_path,
    "-p", text,
    "-n", "200",
    "--no-display-prompt",
    "--output-raw"
]
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
