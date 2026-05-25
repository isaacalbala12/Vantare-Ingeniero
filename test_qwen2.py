from qwen_tts import Qwen3TTSModel, Qwen3TTSTokenizer

# Descargar modelo y tokenizador
model = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
tokenizer = Qwen3TTSTokenizer.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")

# Generar audio
text = "Hola piloto, ¿cómo va la carrera?"
inputs = tokenizer(text=text, return_tensors="pt")
audio = model.generate(**inputs)

# Guardar audio
import soundfile as sf
sf.write("test_qwen.wav", audio.numpy().squeeze(), 24000)
print("Audio generado: test_qwen.wav")
