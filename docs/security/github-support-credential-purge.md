# GitHub Support — Purga de credenciales (borrador ticket)

Enviar en: https://support.github.com/request

## Datos del repositorio

- **Owner/repo:** `isaacalbala12/Vantare-Ingeniero`
- **Motivo:** Eliminación de credenciales tras `git filter-repo` (2 pasadas)
- **PRs afectados:** 10 (`refs/pull/1/head` … `refs/pull/10/head`)

## Qué se eliminó del historial

- Archivos: `backend/.env`, `frontend/src-tauri/binaries/backend/.env`, `frontend/src-tauri/binaries/backend/_internal/.env`
- Cadenas en docs/código: claves Gemini, StepFun y LiteLLM local

## Estado actual

- Ramas y tags principales reescritos y force-pushed
- `.env` en `.gitignore`; solo `backend/.env.example` (plantilla vacía) permanece trackeado
- Credenciales rotadas por el propietario

## Solicitud

1. Dereferenciar o eliminar PRs #1–#10 que aún apuntan a commits pre-purge
2. Ejecutar garbage collection en el servidor
3. Eliminar vistas cacheadas de commits antiguos

## Notas

- No hay objetos LFS huérfanos
- Forks externos: ninguno conocido con datos sensibles
