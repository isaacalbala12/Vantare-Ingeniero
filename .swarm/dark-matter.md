## Dark Matter: Hidden Couplings

Found 20 file pairs that frequently co-change but have no import relationship:

| File A | File B | NPMI | Co-Changes | Lift |
|--------|--------|------|------------|------|
| backend/src/intelligence/events/session_monitor.py | backend/tests/test_base_events.py | 1.000 | 3 | 31.33 |
| backend/build.py | sidecar/build.py | 0.916 | 3 | 23.50 |
| backend/src/services/llm_service.py | frontend/package-lock.json | 0.852 | 3 | 18.80 |
| backend/.env | backend/src/services/llm_service.py | 0.801 | 4 | 12.53 |
| backend/.env | frontend/package-lock.json | 0.799 | 3 | 15.67 |
| .gitignore | backend/src/services/llm_service.py | 0.768 | 3 | 14.10 |
| backend/src/intelligence/llm_client.py | frontend/package-lock.json | 0.754 | 3 | 13.43 |
| frontend/package-lock.json | frontend/src/App.tsx | 0.754 | 3 | 13.43 |
| backend/src/intelligence/llm_client.py | backend/src/services/llm_service.py | 0.752 | 4 | 10.74 |
| backend/src/intelligence/context_builder.py | backend/src/intelligence/engine.py | 0.715 | 3 | 11.75 |
| backend/src/intelligence/engine.py | backend/src/intelligence/prompt_templates.py | 0.715 | 3 | 11.75 |
| .gitignore | backend/.env | 0.715 | 3 | 11.75 |
| backend/.env | backend/src/intelligence/llm_client.py | 0.694 | 4 | 8.95 |
| backend/src/intelligence/prompt_templates.py | docs/ai/tasks/2026-05-26-orquestador.md | 0.694 | 4 | 8.95 |
| backend/src/intelligence/llm_client.py | backend/src/intelligence/prompt_templates.py | 0.694 | 4 | 8.95 |
| .gitignore | backend/src/intelligence/llm_client.py | 0.671 | 3 | 10.07 |
| backend/src/intelligence/llm_client.py | docs/ai/tasks/2026-05-26-orquestador.md | 0.645 | 4 | 7.67 |
| backend/src/services/llm_service.py | frontend/src/App.tsx | 0.606 | 3 | 8.06 |
| backend/src/intelligence/context_builder.py | backend/src/intelligence/prompt_templates.py | 0.598 | 3 | 7.83 |
| .github/workflows/release.yml | installer/windows.nsi | 0.581 | 4 | 6.27 |

These pairs likely share an architectural concern invisible to static analysis.
Consider adding explicit documentation or extracting the shared concern.