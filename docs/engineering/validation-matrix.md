# Matriz de validação de contratos protegidos

Esta matriz liga cada contrato a uma verificação existente. Os comandos devem ser executados no commit sob avaliação; resultados históricos não são herdados automaticamente.

| ID | Validação direcionada | Nível exigido | Estado/lacuna |
|---|---|---|---|
| `DESKTOP-PYWEBVIEW-001` | `python -m pytest -q tests/test_ragv_desktop.py`; smoke Windows com WebView2 quando houver alteração do executável/launcher. | Unitário + Windows real | Coberto unitariamente; smoke depende do ambiente Windows. |
| `AUTH-HML-001` | `python -m pytest -q tests/test_auth.py tests/test_windows_homologation.py`; smoke de abertura sem senha e autenticação automática. | Unitário + contrato Windows | Coberto; não é aprovação de produção. |
| `API-FASTAPI-001` | `python -m pytest -q tests/test_auth.py tests/test_datajud_api.py`; integração PostgreSQL aplicável. | API + PostgreSQL | Coberto pelos testes existentes. |
| `HISTORY-001` | `node tests/frontend_behavior_test.mjs`; `python tests/windows_installer_smoke.py` quando houver artefato; integração PostgreSQL para persistência. | Frontend + Windows + PostgreSQL | Cobertura existente; execução real depende de artefato/ambiente. |
| `TENANT-001` | `python -m pytest -q tests/test_auth.py tests/integration/`; bootstrap idempotente no projeto de homologação. | API + PostgreSQL | Coberto; não usar volume habitual. |
| `QUEUE-WORKER-001` | `python -m pytest -q tests/test_queue*.py tests/integration/` (selecionar o arquivo existente). | PostgreSQL | Cobertura depende de PostgreSQL disponível. |
| `DATAJUD-STATE-001` | `python -m pytest -q tests/test_datajud_client.py tests/test_datajud_api.py tests/test_local_compose_contract.py`; Compose efetivo e `/capabilities` após ativação autorizada. | Unitário + Compose + API real | Gates cobertos; ativação real atual não aprovada. |
| `DATAJUD-RESTART-001` | Persistir configuração em cópia de homologação, recriar serviços, consultar flags efetivos em API/workers, consultar `/capabilities`, fechar/reabrir e repetir. | Windows + Compose + API/workers | **Lacuna prioritária**; não declarar PASS sem chave/autorização e ciclo real. |
| `JUDIT-BOUNDARY-001` | Testes de autorização/frontend; nenhum smoke pago sem autorização específica. | Unitário + frontend; real somente autorizado | Coberto por testes; consulta real não executada neste bloco. |
| `ENV-ISOLATION-001` | `python -m pytest -q tests/test_windows_homologation.py`; smoke Windows verifica projeto, volume, porta loopback e ausência de checkout habitual. | Static + Windows real | Cobertura existente; não executar limpeza Docker global. |

## Comandos de mudança

- Guardrails rápidos: `python -m pytest -q tests/test_auth.py tests/test_ragv_desktop.py tests/test_windows_homologation.py tests/test_local_compose_contract.py`.
- Frontend: `node tests/frontend_behavior_test.mjs`.
- Qualidade: `python -m ruff check app scripts tests`.
- Harness: `python scripts/project_harness.py`.
- Integração PostgreSQL: `python -m pytest -q tests/integration` quando a mudança atravessar persistência/SQL/queue.

A suíte completa e os smokes podem ter pré-requisitos de plataforma; a falha deve ser registrada com a causa, não mascarada como PASS.
