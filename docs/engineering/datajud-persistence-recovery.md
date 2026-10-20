# Recuperação e persistência DataJud — 2026-10-20

**Gate: DATAJUD_PERSISTENCE_E2E_BLOCKED.** Correção implementada e validação estrutural/sintética aprovada; não há aceite de aquisição real nem deployment do candidato.

Checkout original preservado: `cf8e69af7a02bfdf8d685c9128d6926f5425731e`, com todas as alterações preexistentes. Worktree isolada: `D:/projetos/ragv-datajud-persistence`, branch `fix/datajud-persistence-main`, base pública `0d2184f53315ced96953624b58afddfd9ef2d5e8`. Implementação: **`f0a2835b077f1a225cbac504186692ed154c8211`**. Nenhuma instalação foi reinstalada, nenhum volume removido, nenhuma credencial real gerada/copiada e nenhum merge realizado.

## Diagnóstico comprovado, sem presumir perda de chave

Inventário read-only em `staging_evidence_datajud_persistence/local-before.json` e `local-after.json` (artefatos locais, sem valores de credenciais). A comparação final preservou os estados de perfis, serviços e capabilities. Registro sanitizado/hashes/comandos: [evidence/datajud-persistence-results.json](evidence/datajud-persistence-results.json).

| Instalação/perfil | Inicializador/configuração efetiva | Projeto/backend observado |
|---|---|---|
| `D:/projetos/RagV` | Atalho Desktop → `scripts/start-ragv-hidden.vbs` → `start-ragv-desktop.ps1`; `docker compose` no checkout, `.env` local implícito, sujeito à precedência normal do ambiente Compose | `ragv`, API `8000`; flags false, chave ausente do perfil e workers. Isso não demonstra perda da chave da homologação |
| `%LOCALAPPDATA%/RagV-Homologacao` | Perfil persistente `.env`, selecionado explicitamente por `--env-file` | `ragv-hml-76460759f1c0`, API `62427`; chave persistida e flags true |
| `%LOCALAPPDATA%/Programs/RagV Homologacao 198` | `homologacao-common.ps1:2-4` seleciona o perfil acima; `Get-HmlComposeArgs` fixa projeto, runtime do pacote e env. Os scripts common/start têm os mesmos hashes da instalação sem sufixo | Selecionaria o projeto persistido `ragv-hml-76460759f1c0`; os containers ativos atualmente apontam para o runtime **sem sufixo 198**, não para esta pasta |
| `%LOCALAPPDATA%/Programs/RagV Homologacao` | Mesmo perfil persistente; o atalho do menu Iniciar aponta para este launcher | Labels Docker confirmam runtime desta instalação, projeto `76460759f1c0`, env explícito em `RagV-Homologacao/.env` |
| Histórico 196C | Containers antigos ainda existem; seus labels guardam o caminho histórico do mesmo env | `ragv-hml-9eff27d2c68d`, API `18080`, DataJud false. Não é o projeto selecionado pelo perfil atual; não foi reiniciado/alterado |

No projeto ativo de homologação, **API, worker-1, worker-2 e scheduler** receberam flags true. Somente os dois workers possuem a chave; a comparação em memória confirmou igualdade com a chave persistida. API, scheduler e PostgreSQL não a possuem. `/capabilities` retorna enabled=true em `62427`, false em `8000` e `18080`. Isso é confirmação de configuração, **não aquisição real**.

Não foi reproduzida perda/sobrescrita do `.env` de homologação. Bootstrap mantém defaults dentro do ramo de primeira criação (`start-homologacao.ps1:21-55`); o instalador usa payload versionado, não o perfil em LOCALAPPDATA. A escrita de DataJud ocorre no configurador após ação autorizada. O teste novo demonstra preservação byte a byte na reabertura e troca sintética do runtime, inclusive com caminhos contendo espaços e variáveis de outro ambiente no processo pai. Não se generaliza essa evidência para todo incidente histórico ou atualização real do instalador.

## Defeitos e correções mínimas

1. **Ambientes visualmente indistinguíveis.** O atalho Desktop seleciona o desenvolvimento, enquanto o configurador do menu seleciona homologação. Não há evidência de que a configuração tenha sido perdida entre esses ambientes. `app/api.py:175` e `app/api_v1.py:943` agora informam apenas `homologation`/`standalone`, usando marcadores existentes; `app/frontend/app.js:229` e `index.html:8` exibem ambiente e **origem da API**, sem paths, tenant ou chave. Backend antigo sem esse campo aparece como não identificado. A interface fora do desktop não manda mais configurar outro perfil como se fosse o mesmo backend.
2. **Atualização prematura do seletor.** Antes, `scripts/ragv_desktop.py` usava Popen e retornava imediatamente; `openDataJudConfigurator` consultava capabilities uma única vez após três segundos, independentemente do término do diálogo. Uma configuração concluída depois desse instante deixava a tela desabilitada. Agora o bridge aguarda o encerramento do processo (`scripts/ragv_desktop.py:51`), descarta stdout/stderr, e a interface aguarda o resultado e reconsulta imediatamente (`app/frontend/app.js:199-218`). Duplo clique é bloqueado; cancelamento/falha não habilita o seletor artificialmente. O teste de regressão novo falhou contra o frontend anterior e passa após a correção.
3. **Configurador exigia buscar outra chave mesmo quando já persistida.** `configurar-datajud.ps1:79,98` reutiliza chave mascarada/autorização existentes. Buscar substituição é opcional; falha dessa busca não apaga o valor existente. A escrita foi extraída para uma função no **mesmo configurador** (`:26`), preservando validação, consentimento, escrita temporária com ACL e demais linhas do perfil. Instalações novas continuam desabilitadas e sem autorização.
4. **Startup podia abrir a janela sem comparar ativação persistida com a API.** `homologacao-common.ps1:101` e `start-homologacao.ps1:86-87` rejeitam abertura silenciosa quando um perfil habilitado está incompleto ou não é confirmado por capabilities. A mensagem preserva o perfil e não expõe valores. Teste sintético comprova rejeição da divergência e de autorização/chave ausentes. Não há configuração paralela, autoativação, compartilhamento entre ambientes ou fallback para outro projeto.

Não foram modificados Compose, SQL, aquisição DataJud, Judit, seleção de projetos persistidos, volumes ou autorização de tenant. Os contratos existentes `CONFIG-PERSIST-001`, `DATAJUD-STATE/RESTART/SELECTOR-001`, `DESKTOP-BACKEND/AUTH/PYWEBVIEW-001`, `ENV-ISOLATION-001` e `JUDIT-BOUNDARY-001` orientaram a seleção de testes.

## Validação executada

Ambiente: Windows, Python 3.12.10, pytest 9.0.3, PowerShell 7.6.7, Node 26.10.0. Evidência local, não CI remota.

- **97 testes direcionados passam:** auth, desktop, DataJud API/client, persistência PowerShell/Compose, homologação, contratos de atualização/regressão e Compose local. `tests/datajud_persistence_contract.ps1` executa funções reais do configurador/common e o ramo real de criação do launcher em diretório descartável; somente a aplicação de ACL e as respostas HTTP de confirmação são doubles explícitos. Executa também `docker compose config --format json`, sem chamada externa.
- **49 cenários DOM passam**, incluindo espera de conclusão, duplo clique, cancelamento/falha, identidade de ambiente e ausência de redirecionamento para outro perfil.
- **Chromium smoke passa**, com API sintética local. Não é teste do executável instalado/WebView2.
- **14 integrações PostgreSQL passam:** jobs DataJud, pipeline e proveniência. PostgreSQL real 16.15, pgvector 0.8.6, banco UTF8 descartável; provider simulado. Verificam aquisição/persistência/idempotência/histórico/isolamento **sintéticos**, não aquisição CNJ real.
- Ruff, harness (26 observações guardrail/wiring) e `git diff --check`: passam.
- Suíte unitária Windows completa: **12 falhas já conhecidas de Unix socket/POSIX**, 1165 passes, 1 skip. As correções independentes do bloco 268 não foram importadas para este PR nem as verificações enfraquecidas. Portanto não há declaração de suíte completa verde.

A primeira tentativa PostgreSQL teve 12 passes/2 falhas devido a banco descartável SQL_ASCII. Foi criado **outro banco UTF8**, sem mudar aplicação ou fixtures; os 14 passaram. Cluster temporário próprio `/tmp/ragv-datajud-persistence-pg`, porta interna 55434, dentro do container de desenvolvimento PostgreSQL; runner local encaminha stdin/stdout de `docker exec`, sem publicar porta nem acessar o banco original. O cluster temporário deixou de ter postmaster.pid após o shutdown solicitado; não houve restart do PostgreSQL original. Logs/hashes distinguem as duas tentativas.

## Aceitação funcional — estados separados

| Etapa | Estado/evidência |
|---|---|
| Configuração persistida | **Confirmada na instalação existente**, chave/flags presentes; valores não revelados |
| Serviços configurados | **Confirmado na instalação existente**, chave somente nos workers; sem alterar desenvolvimento |
| API disponível | **Confirmado**, `/capabilities` de `62427` enabled=true; não significa provider alcançável |
| Consulta real executada | **BLOQUEADA:** nenhum CNJ específico foi fornecido para a consulta autorizada/controlada. Nenhum número foi extraído de arquivos privados, fixtures ou histórico para substituir essa seleção |
| Dados reais adquiridos/persistidos | **Não demonstrado** neste bloco; PostgreSQL com provider simulado não substitui esse aceite |
| Funcionamento após restart real | **Não demonstrado no candidato.** Restart/reabertura/troca de runtime são sintéticos; novo `docker run --network none` descartável excedeu 20 segundos. Não se arriscou parar a homologação funcional com Docker incapaz de iniciar um teste isolado |
| Atualização real instalada | **Não executada.** Candidato exige artefato coordenado atualizado; nenhum executável/instalador sem assinatura foi aplicado |

Para fechar o gate: fornecer um CNJ específico e autorização aplicável, normalizar o startup Docker sem remover volumes, validar o candidato instalado, executar uma única aquisição controlada pela API/fila/worker, verificar apenas metadados/IDs de persistência e histórico, reiniciar/reabrir e comprovar conservação da configuração e do registro. Não usar Judit nem fazer consultas durante configuração. Não há novas consultas externas neste bloco.

## Handoff, PR e rollback

PR draft de revisão: [#518](https://github.com/oigorbrito/RagV/pull/518), branch `fix/datajud-persistence-main`. Após o commit funcional, `ab94176eedb13bbac1979fddbf8ca66d9c9ffebc` isolou também LOCALAPPDATA do teste PowerShell em hosts CI Linux. Nesse head, os 97 direcionados, 49 DOM, Chromium, Ruff, harness e diff-check passaram localmente.

A CI remota desse SHA **falhou sem iniciar o job**: run `39443203801`, check `118698189103`, lista de steps vazia. A anotação do GitHub informa pagamentos recentes falhos ou limite de gastos insuficiente. Isso comprova bloqueio administrativo de execução desse run, não falha dos testes nem aprovação do código. Nenhum billing/check/proteção foi alterado. Commits posteriores apenas de evidência não herdam aprovação desse run; SHA final e estado observado constam no handoff. Sem merge automático.

Aplicar futuramente somente por atualização coordenada aprovada do desktop e runtime/API; não substituir manualmente arquivos da instalação 198 nesta investigação. Reverter o commit funcional remove a espera/identidade/guardrail novos sem tocar no perfil ou banco, mas reintroduz o risco visual anterior. **Não apagar `.env`, regenerar chave, copiar homologação para desenvolvimento, remover volumes ou desativar checks como rollback.**
