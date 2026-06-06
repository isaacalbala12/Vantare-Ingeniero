# Inicia el servidor dummy de la REST API de LMU en el puerto 6397
Set-Location $PSScriptRoot\..\backend
python -m uvicorn src.debug.lmu_dummy_server:app --host 127.0.0.1 --port 6397
