# RagV Homologação — Grupo Villela

Pacote de homologação, **não é release de produção**. Base da aplicação: `a414b2a1d478ccfbf33611a7c40437dd3f90f3b7`. A revisão do pacote fica no nome do instalador e no diagnóstico instalado.

## Pré-requisitos

Windows 10/11 x64, WebView2 Runtime e Docker Desktop iniciado no modo **containers Linux**, com Compose 2.24.4 ou superior. Internet é necessária na primeira abertura para baixar dependências e construir a imagem. Não é necessário instalar Python, Git ou executar comandos.

## Instalar e utilizar

1. Execute `RagVDesktop-Homologacao-0.1.2-hml-<SHA>-Setup.exe`. Pode escolher uma pasta com espaços. A instalação é por usuário, sem elevação de administrador.
2. O pacote completo fica na pasta escolhida: executável, scripts e subpasta `runtime`. A cópia é verificada pelo instalador antes de oferecer a abertura. Não selecione um checkout Git nem a pasta da instalação habitual.
3. Inicie Docker Desktop e abra o atalho **RagV Homologação**. Uma janela de progresso acompanha o preparo inicial; pode demorar no primeiro build. Nas próximas aberturas, a imagem desta revisão é reutilizada.
4. Use o atalho **Copiar token - RagV Homologação**. Na janela RagV, abra **Configurar acesso**, cole o Bearer e clique em **Verificar**. Não compartilhe esse token nem deixe a área de transferência exposta.
5. O Histórico começa vazio e persiste no banco próprio. Fechar a janela não remove banco, dados ou serviços. Reabrir usa o mesmo tenant.

O perfil `%LOCALAPPDATA%\RagV-Homologacao` guarda `.env`, token e diagnósticos com permissões limitadas ao usuário e SYSTEM. O instalador **nunca** inclui credenciais reais. Um perfil de homologação anterior válido é preservado; nunca se importa configuração do projeto habitual. O nome Compose é `ragv-hml-<identificador aleatório>`, com volume PostgreSQL exclusivo. PostgreSQL não publica porta; a API usa somente loopback, escolhendo porta livre na primeira abertura. Se uma porta anteriormente escolhida passar a ser ocupada, não remova volumes: feche o serviço conflitante e reabra a homologação.

## Configurar DataJud sem terminal

1. Confirme que sua finalidade e seu uso são autorizados pelas regras atuais do CNJ.
2. Abra o atalho **Configurar DataJud - RagV Homologação**. O link da janela aponta para a fonte oficial: <https://www.cnj.jus.br/sistemas/datajud/api-publica/>. Obtenha a chave vigente manualmente; o RagV não faz consultas automáticas na instalação.
3. Cole a chave no campo mascarado, marque a confirmação de uso autorizado e clique **Salvar e ativar**. A chave fica restrita aos workers; API, scheduler e desktop não a recebem. Não é necessária chave Judit.
4. Na janela RagV, selecione DataJud em **Configurar acesso** e consulte somente CNJ autorizado. Nenhuma consulta paga ou processual é feita pelo configurador.

## Diagnóstico e recuperação

- `runtime/HOMOLOGACAO.txt`, na pasta instalada: versão, SHA base e SHA do pacote.
- `%LOCALAPPDATA%\RagV-Homologacao\diagnostics.txt`: revisão, projeto, porta e runtime efetivos.
- `startup.jsonl`: etapas, códigos de saída e versão/edição do PowerShell; sem tokens, DSN, saída de containers ou dados processuais.
- `last-error.txt`: última falha de inicialização. O aplicativo não abre se não conseguir validar o tenant.

Os atalhos usam explicitamente Windows PowerShell 5.1. As ACLs são aplicadas e verificadas pelas APIs .NET, sem dependência de `Get-Acl` ou do módulo `Microsoft.PowerShell.Security`. Scripts têm UTF-8 com BOM para preservar acentos nesse PowerShell.

Reinstalar o pacote recompõe `runtime` sem excluir o perfil/banco. Desinstalar não remove volumes automaticamente. Não use comandos globais de limpeza Docker nem remova o projeto/volume habitual `ragv` / `ragv_rpy_pgdata`.

## Build reproduzível (mantenedores)

Na revisão identificada do pacote, use PowerShell 7 e execute `scripts/package_windows_homologation.ps1 -PackageSha <SHA completo>`. O build cria venv descartável, usa dependências fixadas e verifica Inno Setup engine 6.7.3. O SHA-256 gerado identifica o executável efetivamente produzido; builds em momentos diferentes não prometem identidade binária das imagens reconstruídas a partir de repositórios externos.
