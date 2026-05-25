import torch
from transformers import AutoModelForTextToSpeech, AutoProcessor
import soundfile as sf

# Descargar modelo y processor
model = AutoModelForTextToSpeech.from_pretrained("mistralai/Voxtral-Mini-4B-TTS-2603")
processor = AutoProcessor.from_pretrained("mistralai/Voxtral-Mini-4B-TTS-2603")

# Usar GPU si está disponible
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)

# Generar audio
text = "Hola piloto, ¿cómo va la carrera?"
inputs = processor(text=text, return_tensors="pt").to(device)
with torch.no_grad():
    audio = model.generate(**inputs)

# Guardar
sf.write("test_voxtral.wav", audio.cpu().numpy().squeeze(), 24000)
print("Audio generado: test_voxtral.wav")
