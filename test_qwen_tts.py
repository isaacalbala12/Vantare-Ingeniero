import torch
from transformers import AutoModel, AutoProcessor
import soundfile as sf

# Descargar modelo y processor
model = AutoModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
processor = AutoProcessor.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")

# Usar GPU si está disponible (ROCm en AMD)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

# Generar audio
text = "Hola piloto, ¿cómo va la carrera?"
inputs = processor(text=text, return_tensors="pt").to(device)
with torch.no_grad():
    audio = model.generate(**inputs)

# Guardar audio
sf.write("test_qwen.wav", audio.cpu().numpy().squeeze(), 24000)
print("Audio generado: test_qwen.wav")
