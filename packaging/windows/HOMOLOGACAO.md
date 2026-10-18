# RagV Homologação — Grupo Villela

Este instalador é somente para homologação, não é release de produção. Base da aplicação: `a414b2a1d478ccfbf33611a7c40437dd3f90f3b7`.

## Requisitos

- Windows 10/11 x64 e Docker Desktop instalado, iniciado e configurado para containers Linux.
- Conexão à internet na primeira abertura para baixar a imagem PostgreSQL e construir a imagem RagV incluída no pacote. Python e Git não são necessários.
- Recursos disponíveis para Docker Desktop executar PostgreSQL, API, dois workers e scheduler.

## Instalar e abrir

1. Execute `RagVDesktop-Homologacao-0.1.1-hml-<SHA-do-pacote>-Setup.exe`. Instala em `%LOCALAPPDATA%` e cria atalho **RagV Homologação**; não substitui a instalação habitual.
2. Inicie Docker Desktop e abra o atalho. Na primeira abertura, o launcher gera senha/tokens aleatórios, escolhe porta API livre, constrói uma única imagem da revisão e inicia PostgreSQL, migração 001–034, API, dois workers e scheduler.
3. O ambiente usa um identificador Compose aleatório persistido em `%LOCALAPPDATA%\RagV-Homologacao\project\.env`; o volume criado é exclusivo desse projeto. PostgreSQL não publica porta no host. A API liga somente em `127.0.0.1`. Não aponta para `D:\projetos\ragv` nem lê seu `.env`.
4. Use o atalho **Copiar token - RagV Homologação**, abra **Configurar acesso**, cole o token no campo Bearer e clique **Verificar**. O token gerado fica restrito ao usuário local. Não compartilhe o token.
5. A primeira tela fica sem processo/histórico até inclusão de dados de teste autorizados. A área **Histórico** lista somente registros desse perfil isolado.

Para remover depois, desinstale pelo Windows e, se quiser apagar os dados descartáveis, remova somente o projeto cujo nome está em `%LOCALAPPDATA%\RagV-Homologacao\project\.env`. Não use comandos globais de remoção de volumes; não remova o projeto/volume habitual `ragv` / `ragv_rpy_pgdata`.

## DataJud opt-in

DataJud começa desabilitado e nenhuma consulta é enviada na instalação/abertura. Confirme finalidade e autorização segundo as regras atuais do CNJ. Obtenha manualmente a chave vigente na fonte oficial: <https://www.cnj.jus.br/sistemas/datajud/api-publica/>. Use o atalho **Configurar DataJud - RagV Homologação**, confirme `AUTORIZO` e informe a chave no prompt mascarado. O script guarda a chave no `.env` restrito do perfil e recria API, workers e scheduler para aplicar os gates; somente os workers recebem a chave; a chave não é entregue à API, desktop ou scheduler. Não é necessária credencial Judit. Não registre a chave em chamados ou logs.

Depois, abra **Configurar acesso**, selecione DataJud e use CNJ para o qual você tem finalidade autorizada. A API pública tem limites e termos próprios; erro de chave/fonte não é prova de indisponibilidade do RagV. Não há consulta automática nem paga por instalar.

## Diagnóstico

A base da aplicação é o SHA indicado acima; alterações de empacotamento têm SHA separado no nome do instalador e em `project/HOMOLOGACAO.txt`, distribuído no artefato. Imagens Docker de homologação são identificadas pelo SHA do pacote. Docker Compose 2.24.4 ou superior é necessário (`!override`). WebView2 Runtime do Microsoft Edge também é pré-requisito da janela nativa.

Revisão e porta ficam em `%LOCALAPPDATA%\RagV-Homologacao\diagnostics.txt`. Arquivos de aplicação e Compose estão em `%LOCALAPPDATA%\RagV-Homologacao\project`. O instalador não contém banco, credenciais reais ou `.env` do desenvolvedor.
