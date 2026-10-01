# Registro de alterações

Este arquivo registra as alterações realizadas no GridScope Core. Toda mudança
posterior deve acrescentar uma entrada aqui, incluindo arquivos afetados,
motivo, validação executada e pendências conhecidas.

## 2026-09-29 — ingestão, API, frontend e infraestrutura

### Objetivo

Preparar a substituição do Streamlit por React/Vite/PWA e separar a aquisição
de dados da publicação do snapshot operacional, mantendo a distribuidora como
fonte primária planejada sem inventar um endpoint ainda não fornecido.

### Alterações realizadas

#### Planejamento

- Expandido `PLANO_MELHORIAS.md` com arquitetura, prioridades, critérios de
  aceite, PWA, integração da distribuidora e estratégia de substituição.

#### Configuração e aquisição de dados

- Adicionadas configurações de fonte, limites de download, timeout, token,
  ingestão no boot, treino no boot e Redis em `src/config.py`.
- Criado contrato `DataDelivery`/`DataSource` em
  `src/etl/fontes/contratos.py`.
- Criados adaptadores local e HTTP em `src/etl/fontes/local.py` e
  `src/etl/fontes/http.py`.
- O adaptador HTTP baixa ZIP, calcula identificador SHA-256, limita tamanho,
  rejeita traversal/symlink e exige exatamente um GDB.
- Criada fábrica de fontes em `src/etl/fontes/factory.py`.
- Mantida a compatibilidade de `migrar_gdb_para_sql` em
  `src/etl/migracao_db.py`.

#### Publicação do snapshot

- Criado `src/etl/importador.py`.
- O importador lê as camadas obrigatórias para schema temporário, valida
  registros e publica o conjunto por corte transacional.
- Dados antigos só são removidos durante o corte após a carga temporária
  passar pelas validações.
- Criado `src/etl/pipeline.py`, que baixa/adquire a entrega, publica o
  snapshot e grava `dados/metadata_carga_atual.json` somente depois do sucesso.
- Adicionado endpoint `GET /data/status` em `src/api.py` para expor origem,
  identificador, período, horário e contagens sem devolver os dados privados.

#### Orquestração e infraestrutura

- `run_all.py` passou a executar a ingestão configurada e deixou de iniciar o
  processo Streamlit.
- `docker-compose.yml` passou a expor API em `8000` e frontend em `3000`,
  incluindo Redis e variáveis da fonte de dados.
- Criados `.dockerignore` e `frontend/.dockerignore` para não enviar dados,
  segredos, modelos e dependências locais para imagens.
- Removida a exposição de `8501` do `Dockerfile`.
- Atualizados `README.md`, `.env.example` e `requirements.txt`.

#### Frontend

- Criado `frontend/` com React, TypeScript, Vite e `vite-plugin-pwa`.
- Implementados shell responsivo, navegação, indicadores, status da carga,
  tabela de subestações, estados de carregamento/erro/offline e media query
  para redução de movimento.
- Criado proxy de desenvolvimento e proxy `/api/` no Nginx.
- O service worker pré-cacheia somente recursos estáticos; endpoints `/api/`
  não são armazenados offline.
- Criados `frontend/package-lock.json`, `frontend/Dockerfile` e manifesto PWA.

#### Testes

- Criados testes unitários padrão da biblioteca para fonte local e extração
  segura de ZIP em `tests/test_fontes.py`.

### Validações executadas

- `npm install --ignore-scripts`: aprovado.
- `npm run typecheck`: aprovado.
- `npm run build`: aprovado; manifesto e service worker PWA gerados.
- `PYTHONPATH=. python3 -m unittest discover -s tests -v`: 3 testes aprovados.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py tests`: aprovado.
- `docker compose config`: aprovado.
- `docker compose build frontend`: aprovado.
- O build inicial do backend excedeu o timeout durante a exportação final; ele
  foi repetido com timeout maior e aprovado (ver entrada de validação abaixo).

### Pendências conhecidas

1. O endpoint, autenticação, formato e frequência da distribuidora ainda não
   foram fornecidos; por isso o adaptador HTTP é genérico e não contém URL
   fictícia.
2. A estratégia de staging precisa ser validada contra um GDB real e uma carga
   que falhe durante a geração dos derivados.
3. Relatórios, mapa interativo e assistente do frontend ainda são estados
   preparatórios, não funcionalidades completas.
4. Os módulos Streamlit antigos continuam no repositório para remoção após a
   validação do frontend novo; `run_all.py` já não os inicia.
5. Falta validar o importador contra um GDB real/anonimizado e um PostgreSQL
   PostGIS funcional.

## 2026-09-29 — validação do backend Docker

- Repetido `docker compose build gridscope` com timeout ampliado.
- Build aprovado, incluindo instalação das dependências, cópia do código e
  exportação final da imagem `gridscope-core-gridscope`.
- O `.dockerignore` reduziu o contexto do backend de aproximadamente 1,75 GB
  para 9,49 kB, excluindo dados locais, modelos, caches e dependências do
  frontend.

## 2026-09-29 — derivados no mesmo corte do snapshot

- Adicionado `DATABASE_SCHEMA` em `src/config.py` e suporte a `search_path`
  isolado em `src/database.py`.
- `SnapshotImporter` agora aceita uma etapa de preparação e publica também
  tabelas derivadas retornadas por essa etapa.
- `src/etl/pipeline.py` passou a executar os jobs de Voronoi e análise de
  mercado no schema temporário e validar `territorios_voronoi` e
  `cache_mercado` antes do corte.
- `run_all.py` deixou de executar esses jobs depois da ingestão; eles agora
  fazem parte da publicação do snapshot.
- `processar_voronoi.py` passou a usar a mesma camada de conexão, respeitando
  o schema temporário.
- Revalidados compilação, `git diff --check`, build da imagem backend e os
  três testes unitários dentro do container.

## 2026-09-29 — endurecimento da extração ZIP

- `src/etl/fontes/http.py` agora normaliza separadores POSIX/Windows, rejeita
  caminhos absolutos e `..` antes da extração e reconhece GDB com extensão em
  qualquer combinação de maiúsculas/minúsculas.
- `tests/test_fontes.py` ganhou cobertura para traversal com barra invertida.
- Validação: 4 testes unitários aprovados, compilação Python aprovada e
  `git diff --check` sem erros de conteúdo.

## 2026-09-29 — verificação de importação no container

- Refeito o build de `gridscope` após o endurecimento do ZIP.
- Confirmado que `src.api` importa no container e registra `GET /data/status`.
- Os 4 testes unitários também passaram dentro da imagem Python.

## 2026-09-29 — validação final da sessão

- `npm run typecheck` e `npm run build`: aprovados novamente.
- `PYTHONPATH=. python3 -m unittest discover -s tests -v`: 4 testes aprovados.
- Compilação Python de `src`, `run_all.py` e `tests`: aprovada.
- `docker compose config`: aprovado.
- `git diff --check`: sem erros de conteúdo; permanecem apenas avisos de
  normalização CRLF em arquivos preexistentes/modificados.

## 2026-09-29 — contrato da API, testes de corte e mapa

### Alterações

- Corrigido o contrato Pydantic de `src/api.py`: `detalhe_por_classe` agora
  representa os objetos aninhados produzidos pelo ETL (`potencia_kw` e `qtd`).
- Adicionados `id_tecnico` e `evolucao_temporal` ao contrato de subestação.
- Criado `tests/test_api_contract.py` para validar o ranking e os metadados da
  carga pela API.
- Criado `tests/test_importador.py` cobrindo preparação de derivados, bloqueio
  de publicação em falha e rejeição de camada vazia.
- O cliente TypeScript foi atualizado para o mesmo contrato e a tabela passou
  a usar o ID técnico como chave estável.
- Adicionado mapa Leaflet em `frontend/src/components/TerritoryMap.tsx`, usando
  o GeoJSON da API e falha isolada quando o endpoint geográfico não responde.
- Adicionadas dependências Leaflet e `react-leaflet`; o mapa mantém a política
  PWA de não armazenar respostas de API offline.

### Validação

- `npm run typecheck` e `npm run build`: aprovados com mapa e PWA.
- `docker compose build gridscope`: aprovado.
- `docker compose build frontend`: aprovado.
- Testes no container Python: 9 aprovados.
- Compilação Python e `git diff --check`: aprovados.

### Pendências

- O mapa usa tiles públicos do OpenStreetMap; em produção devem ser definidos
  política de atribuição, disponibilidade e provedor de tiles.
- Ainda falta validar a troca completa com GDB real e PostgreSQL/PostGIS; os
  testes atuais isolam o orquestrador e não substituem o teste integrado.

## 2026-09-29 — detalhe operacional de subestação

### Alterações

- Criado `frontend/src/components/SubstationDetail.tsx` com métricas, perfil
  de consumo, classes de GD e série temporal da subestação selecionada.
- A tabela de subestações passou a usar o ID técnico como seleção estável e
  oferece navegação acessível para abrir/fechar o detalhe.
- O estado selecionado é compartilhado entre Panorama e Subestações; clicar em
  um ativo no resumo abre a visão detalhada.
- Adicionados estados visuais responsivos para seleção, barras por classe,
  histórico e ausência de dados.
- Tipos TypeScript de perfil e evolução foram alinhados ao contrato da API.

### Validação

- `npm run typecheck`: aprovado.
- `npm run build`: aprovado com mapa e detalhe de subestação.

## 2026-09-29 — adoção de Tailwind CSS

- Adicionado Tailwind CSS v4 com `@tailwindcss/vite` ao build Vite.
- Aplicada a camada Tailwind em `frontend/src/styles.css` e utilizados
  utilitários Tailwind nos componentes de detalhe, tabela, mapa, métricas e
  foco acessível dos controles.
- Mantidos apenas estilos semânticos e específicos do domínio/Leaflet onde a
  migração direta não reduziria complexidade nesta etapa.
- `frontend/package-lock.json` atualizado.
- `npm run typecheck` e `npm run build`: aprovados após a integração.

## 2026-09-29 — Tailwind como única camada visual do frontend

- Removidas todas as regras CSS próprias de `frontend/src/tailwind.css`; o
  arquivo agora contém somente a entrada `@import "tailwindcss"`.
- Reescritos o shell, navegação, tabelas, cartões, estados, detalhe e
  responsividade usando classes utilitárias Tailwind diretamente nos
  componentes React.
- Removidos `leaflet`, `react-leaflet` e seus tipos para evitar dependência de
  CSS externo obrigatório.
- `TerritoryMap` passou a renderizar o GeoJSON em SVG, com projeção simples e
  estilos Tailwind, mantendo o mapa sem stylesheet bruto.
- `index.html` passou a declarar a base visual mínima com classes Tailwind no
  elemento `body`.
- O entrypoint visual foi renomeado para `frontend/src/tailwind.css` e não há
  regras CSS próprias nem `style` inline nos componentes.
- `npm run typecheck` e `npm run build`: aprovados; o bundle caiu para cerca
  de 168 kB antes da compressão.
- `docker compose build frontend`: aprovado após a remoção do Leaflet e do
  stylesheet bruto.

## 2026-09-29 — readiness da API e inicialização coordenada

### Alterações

- Adicionados `GET /health` (liveness) e `GET /ready` (database/Redis) em
  `src/api.py`.
- O endpoint de readiness retorna HTTP 503 e os checks individuais quando uma
  dependência ainda não está disponível.
- Adicionados healthchecks para PostgreSQL, Redis e API em
  `docker-compose.yml`.
- O frontend agora depende da API saudável, e a API depende de banco e Redis
  saudáveis antes de iniciar.
- Adicionados testes de contrato para liveness e falha de readiness.

### Validação

- `docker compose config`: aprovado com condições `service_healthy`.
- `docker compose build gridscope`: aprovado.
- Testes Python no container: 11 aprovados.
- Compilação Python e `git diff --check`: aprovados.

## 2026-09-29 — primeira exportação técnica

### Alterações

- Criado `GET /mercado/ranking.csv` em `src/api.py`.
- A exportação contém somente indicadores agregados por subestação, sem
  geometria ou dados pessoais.
- Adicionada proteção contra fórmulas de planilha para células textuais que
  começam com `=`, `+`, `-` ou `@`.
- O frontend passou a oferecer o download em Relatórios usando a mesma origem
  `/api`, sem duplicar a lógica de consulta.
- Relatórios PDF e filtros avançados permanecem explicitamente pendentes do
  contrato de exportação correspondente.

### Validação

- `npm run typecheck` e `npm run build`: aprovados.
- `docker compose build gridscope`: aprovado.
- Testes Python no container: 12 aprovados, incluindo proteção contra fórmula
  CSV.
- Compilação Python e `git diff --check`: aprovados.

### Regra para as próximas alterações

Antes de finalizar qualquer alteração, atualizar este arquivo com:

- data e objetivo;
- arquivos modificados;
- comportamento implementado;
- comandos de validação e resultado;
- pendências ou limitações introduzidas.

## 2026-09-29 — endurecimento da configuração local

### Alterações

- Removida a senha fixa do PostgreSQL em `docker-compose.yml`, `run_all.py` e
  scripts de auditoria; o Compose agora exige `POSTGRES_PASSWORD` e a URL
  interna `DATABASE_URL_DOCKER` no `.env`.
- Adicionadas variáveis explícitas para usuário, banco e portas locais em
  `.env.example`, mantendo `DATABASE_URL` para execução fora do Compose.
- As portas publicadas de PostgreSQL e Redis agora ficam limitadas a
  `127.0.0.1`; a comunicação entre os serviços permanece na rede interna.
- O healthcheck do PostgreSQL passou a usar as credenciais configuradas, e
  `run_all.py` passou a reutilizar `src.config.DATABASE_URL`, carregando o
  `.env` pelo mesmo caminho da aplicação.
- Atualizado o README com a migração de credenciais e a diferença entre URL
  local (`localhost`) e URL interna (`db`).

### Validação

- `docker compose config` com credenciais de teste: aprovado.
- Testes Python no container: 12 aprovados.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py tests`: aprovado.
- `npm run typecheck` e `npm run build`: aprovados.
- `git diff --check`: sem erros de conteúdo.

### Pendências

- Cada ambiente deve preencher `POSTGRES_PASSWORD`, `DATABASE_URL` e
  `DATABASE_URL_DOCKER` antes de executar o Compose; o arquivo `.env` local
  existente não é alterado por estar fora do controle de versão. Volumes
  PostgreSQL já inicializados com a senha anterior exigem migração explícita
  da senha ou recriação controlada do volume.

## 2026-09-29 — correção do backup PostgreSQL

### Alterações

- Atualizado `scripts/backup_db.py` para executar `docker compose exec` no
  serviço real `db`, usando `POSTGRES_USER`, `POSTGRES_DB` e
  `POSTGRES_PASSWORD` já presentes no container.
- Removido `shell=True` e o redirecionamento construído por string; o dump
  agora é escrito em arquivo temporário de permissão restrita e movido
  atomicamente após validar que não está vazio.
- Falhas do `pg_dump` removem o temporário e fazem o script terminar com código
  diferente de zero; continuam sendo mantidos no máximo cinco backups.
- Adicionado `backups/` ao `.gitignore` para impedir que dumps sejam versionados.
- Criados testes determinísticos para sucesso atômico e falha de execução.

### Validação

- `python3 -m unittest tests.test_backup_db -v`: 2 testes aprovados.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q scripts/backup_db.py tests/test_backup_db.py`: aprovado.
- `git diff --check`: aprovado.

## 2026-09-29 — simulação solar por ID técnico

### Alterações

- Adicionado `GET /simulacao/id/{id_tecnico}` em `src/api.py`, com seleção
  exata pelo identificador técnico e respostas `404` para ID ausente e `409`
  para ID duplicado, sem escolher silenciosamente um registro.
- Extraídas a validação da data, seleção do alvo e geração da simulação para
  helpers compartilhados; a rota legada por nome permanece disponível para
  compatibilidade, mas agora rejeita nomes ambíguos com `409`.
- Adicionado `getSolarSimulation` e o tipo `SolarSimulation` ao cliente
  TypeScript.
- O detalhe da subestação agora permite escolher a data, executar a projeção
  solar e visualizar geração, irradiação, temperatura, perda térmica, fonte e
  impacto retornados pelo backend.
- Adicionados testes de contrato para ID estável, ID inexistente e duplicidade.

### Validação

- Testes Python no container: 17 aprovados.
- `npm run typecheck` e `npm run build`: aprovados.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py scripts tests`: aprovado.
- `git diff --check`: aprovado.

## 2026-09-29 — contenção de dados falsos no PDF legado

### Alterações

- `src/pdf_report.py` deixou de fabricar dados aleatórios quando o cache está
  vazio ou indisponível; agora propaga `ReportDataError` e bloqueia a geração.
- ID de subestação inexistente deixou de cair silenciosamente na primeira
  linha do DataFrame.
- A data escolhida em `src/views/relatorios.py` agora é repassada ao cabeçalho
  do PDF, em vez de ser substituída pela data atual.
- Corrigido o import do módulo de relatório para funcionar como `src.pdf_report`
  nos testes e manter fallback compatível com o carregamento legado.
- Adicionados testes para cache vazio, ID inválido e preservação da data.
- Nenhuma rota PDF nova foi exposta: o contrato do relatório e a autenticação
  da nova interface continuam pendentes.

### Validação

- Testes Python no container: 22 aprovados.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py scripts tests`: aprovado.
- `git diff --check`: aprovado.

### Pendências

- A simulação ainda usa o fallback climático existente quando o provedor
  externo não responde; o resultado deve continuar identificado como
  estimativa na interface.

## 2026-09-29 — filtros locais de subestações

### Alterações

- Adicionada busca local por nome ou ID técnico na visão de Subestações.
- Adicionado filtro por situação `Todas`, `Normal` ou `Atenção`, sem alterar a
  carga recebida nem duplicar cálculos do backend.
- Adicionado contador de resultados, ação para limpar filtros e estado vazio
  acessível quando nenhum ativo corresponde à combinação selecionada.
- Mantida a seleção por `id_tecnico` e o detalhe operacional existente.

### Validação

- `npm run typecheck` e `npm run build`: aprovados.
- `git diff --check`: aprovado.

## 2026-09-29 — proveniência visível no estado da interface

### Alterações

- O cabeçalho passou a distinguir `Carga publicada`, `Metadados
  indisponíveis` e consulta em andamento por cor, texto e data.
- Adicionado aviso explícito quando a API responde sem metadados publicados,
  sem esconder os indicadores que ainda puderem ser consultados.
- O destaque do Panorama deixou de afirmar que a carga está publicada quando a
  proveniência não foi confirmada.

### Validação

- `npm run typecheck` e `npm run build`: aprovados.
- Detector Impeccable em `frontend/src/App.tsx`: nenhum achado.
- `git diff --check`: aprovado.

## 2026-09-29 — filtros na exportação CSV

### Alterações

- `GET /mercado/ranking.csv` agora aceita `busca` por nome/ID técnico e
  `situacao` (`all`, `normal` ou `attention`) no backend.
- Valores de situação inválidos retornam `400`; o arquivo continua sem
  geometria e sem dados pessoais.
- A tela Relatórios ganhou busca, filtro de situação, limpeza de filtros e
  indicação de que o recorte é aplicado no backend.
- A pendência de filtros por ativo foi removida da tela; PDF técnico continua
  aguardando contrato e serviço de geração.
- Adicionados testes de contrato para filtragem e validação do parâmetro.

### Validação

- Testes Python no container: 19 aprovados.
- `npm run typecheck` e `npm run build`: aprovados.
- Detector Impeccable em `frontend/src/App.tsx`: nenhum achado.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py scripts tests`: aprovado.
- `git diff --check`: aprovado.

## 2026-09-29 — validação da camada legada de dados PDF

### Alterações

- Substituído `eval()` por `ast.literal_eval()` com validação de mapas em
  `src/reports/data.py`.
- Cache vazio, ID inexistente e ID duplicado agora interrompem o relatório com
  `ReportDataError`, sem escolher um ativo substituto.
- Corrigido o tratamento de potência por classe quando o cache usa mapa ou
  valor numérico.
- Adicionados testes contra conteúdo malicioso, cache vazio e seleção
  ambígua.

### Validação

- Testes Python no container: 26 aprovados.
- Busca em `src/reports/*.py` e `tests/*.py`: nenhum `eval()` executável.
- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py scripts tests`: aprovado.
- `git diff --check`: aprovado.

## 2026-09-29 — parametrização de consultas e validação de identificadores

### Alterações

- Parametrizados os IDs usados nas consultas de consumo de
  `src/ai/ai_service.py` e `src/etl/etl_ai_consumo.py`; o mês da simulação é
  validado e as colunas mensais são selecionadas de uma lista fixa.
- Desativada a interpretação de regex nos filtros de nome de subestação desses
  módulos, mantendo a busca como texto literal.
- Criado um allowlist de colunas em `src/database.py`; colunas desconhecidas ou
  duplicadas agora são rejeitadas antes de formar o `SELECT`.
- Validado o schema de staging antes de iniciar os jobs derivados em
  `src/etl/pipeline.py` e mantida a citação dos identificadores dinâmicos.
- Ajustados `.env.example` e o fallback de `src/config.py` para usar
  `postgresql+psycopg2`, compatível com `psycopg2-binary` instalado no projeto.
- Criado `tests/test_sql_safety.py` com cobertura para IDs maliciosos, mês fora
  do intervalo e coluna não permitida.

### Validação

- Testes Python no container: 30 aprovados.
- `python -m compileall -q src tests` no container: aprovado.
- `git diff --check`: aprovado; permanecem apenas avisos de normalização CRLF.
- Busca por `eval()` executável em arquivos Python: nenhum resultado.

### Pendências

- O teste unitário foi executado sem o serviço `db`; a conexão da carga global
  da IA registra indisponibilidade esperada, sem reprovar os testes.
- A validação integrada ainda depende de PostgreSQL/PostGIS funcional e GDB
  real ou anonimizado.

## 2026-09-29 — estabilidade da agregação de mercado no startup

### Alterações

- `src/modelos/analise_mercado.py` agora representa o mapa de classes de
  consumidores como `Series` desde o início, evitando `AttributeError` quando
  há GD sem consumidores vinculados.
- Extraída a classificação de GD para `_classificar_geracao_por_classe`, com
  fallback explícito para `Outros`.
- `run_all.py` passou a citar os nomes fixos das tabelas na verificação de
  população do banco.
- Adicionado teste regressivo em `tests/test_analise_mercado.py`.

### Validação

- `PYTHONPYCACHEPREFIX=/tmp/opencode/gridscope-pycache python3 -m compileall -q src run_all.py tests`: aprovado.
- `git diff --check`: aprovado.

### Pendências

- O teste unitário e a suíte completa aguardam o daemon Docker; o host não
  possui `pandas`/as dependências da aplicação.

## 2026-09-30 — isolamento de testes e invalidação segura do cache Redis

### Alterações

- `src/cache_redis.py` passou a usar `SCAN` em `limpar_cache`, evitando a
  operação bloqueante `KEYS` em Redis com muitas chaves.
- `tests/test_api_contract.py` limpa o namespace de cache antes de cada caso,
  impedindo que respostas persistidas contaminem testes de contrato.
- Adicionado `tests/test_cache_redis.py` para garantir a varredura e remoção
  das chaves encontradas.

### Validação

- Testes Python no container: 32 aprovados.
- Teste integrado com PostgreSQL/PostGIS: importação temporária, publicação e
  leitura de uma tabela de staging aprovadas; a tabela de smoke test foi
  removida ao final.
- `git diff --check`: aprovado.

### Pendências

- A validação com GDB real/anonimizado continua pendente; o smoke test usa uma
  tabela temporária para não substituir dados locais existentes.

## 2026-09-30 — contrato reprodutível do modelo de consumo

### Alterações

- Criado `src/ai/model_contract.py` com a lista única de features e o nome do
  alvo compartilhados por treino e validação.
- `src/ai/train_model.py` passou a usar `numpy.random.Generator` com seed
  explícita e a selecionar as features pela ordem do contrato.
- `src/ai/ai_service.py` passou a construir a entrada da inferência com o
  mesmo contrato de colunas.
- `src/ai/validate_model.py` deixou de procurar uma pasta de modelos
  inexistente e valida `src/ai/modelo_*.pkl` usando o mesmo dataset/feature
  schema do treino.
- Adicionado `tests/test_model_contract.py` para garantir reprodutibilidade e
  ordem das features.

### Validação

- Testes Python no container: 33 aprovados.
- Validação do modelo `modelo_consumo.pkl`: R² 0,9989 e MAE 0,25.
- Compilação Python no container: aprovada.
- `docker compose build gridscope`: aprovado após fixar a dependência.

### Pendências

- `scikit-learn` foi fixado em `1.9.1` e o artefato local ignorado pelo Git foi
  regenerado com essa versão; ambientes que mantiverem artefatos antigos devem
  regenerá-los antes de produção.

## 2026-09-30 — respostas genéricas de erro na API principal

### Alterações

- `src/api.py` passou a registrar falhas no servidor e retornar mensagens
  genéricas para ranking, GeoJSON e simulações, sem expor exceções, SQL ou
  detalhes de infraestrutura ao cliente.
- Falhas de clima agora usam logging estruturado, mantendo o fallback
  explicitamente identificado como estimativa.
- Adicionados testes de contrato que verificam a ausência de detalhes internos
  nas respostas HTTP.

### Validação

- Testes Python no container: 37 aprovados.
- Compilação Python no container: aprovada.
- `git diff --check`: aprovado.

### Pendências

- Autenticação/autorização e correlação de logs continuam pendentes conforme
  `SEC-01` e `OPS-05`.

## 2026-09-30 — encerramento coordenado do supervisor

### Alterações

- `run_all.py` agora fecha os arquivos de log dos processos filhos no processo
  pai, mantém uma lista dos serviços iniciados e encerra todos de forma
  coordenada.
- A parada usa `terminate`, aguarda até cinco segundos e aplica `kill` quando
  um processo não encerra no prazo, inclusive quando outro serviço falha ou há
  `KeyboardInterrupt`.
- Adicionado `tests/test_startup.py` para cobrir encerramento normal e forçado.

### Validação

- Testes Python no container: 38 aprovados.
- Compilação Python no container: aprovada.
- `git diff --check`: aprovado.

### Pendências

- A política de quais APIs são obrigatórias/opcionais e o gerenciamento
  independente dos jobs de ingestão/treino continuam pendentes em `OPS-02`.

## 2026-09-30 — verificação operacional de backup e restore

### Validação executada

- `python3 scripts/backup_db.py`: backup PostgreSQL criado com sucesso usando
  o serviço `db` e arquivo temporário atômico.
- O dump foi restaurado em um banco descartável `gridscope_restore_test`;
  PostgreSQL/PostGIS executaram o SQL sem erro e a tabela `subestacoes` foi
  restaurada com 44 registros.
- O banco descartável foi removido ao final do teste.

### Pendências

- Definir RPO/RTO, retenção e agendamento do backup para o ambiente de
  operação; o script local continua limitado à política dos cinco arquivos.

## 2026-09-30 — inicialização lazy do armazenamento do chat

### Alterações

- `src/ai/chat_service.py` deixou de criar tabelas de feedback/histórico durante
  a importação do módulo.
- A preparação dessas tabelas passou para o `lifespan` do FastAPI, mantendo a
  inicialização no startup real do serviço e permitindo importar o módulo sem
  exigir banco disponível.
- Adicionado teste para o ciclo de vida de inicialização do armazenamento.

### Validação

- Testes Python no container: 39 aprovados.
- Compilação Python no container: aprovada.
- `git diff --check`: aprovado.

## 2026-09-30 — carregamento lazy da base da API de IA

### Alterações

- `src/ai/ai_service.py` deixou de carregar subestações e abrir conexão com o
  banco durante a importação do módulo.
- O GeoDataFrame agora é carregado sob demanda na primeira operação que exige
  localização ou busca de consumo real.
- Adicionado teste que protege a importação sem dependência de banco.

### Validação

- Testes Python no container: 40 aprovados.
- Compilação Python no container: aprovada.
- A suíte deixou de abrir conexão do banco somente para importar a API de IA.

## 2026-09-30 — contenção do monitor ANEEL

### Alterações

- `src/etl/monitor_aneel.py` passou a consultar e selecionar uma referência no
  ArcGIS Hub sem baixar ZIP/GDB, gravar `metadata_aneel.json` ou executar
  migração, Voronoi e análise de mercado.
- O workflow `.github/workflows/verificar_aneel.yml` foi renomeado para deixar
  explícito que a consulta é somente referencial e passou a instalar
  `python-dotenv` junto com `requests`.
- Removido o caminho legado que publicava automaticamente dados ANEEL durante
  a consulta.
- Adicionados testes para garantir que a consulta não abre arquivos nem indica
  publicação após erro remoto.

### Validação

- Testes Python no container: 42 aprovados.
- Compilação Python no container: aprovada.
- A consulta ANEEL foi validada sem alteração da base operacional.

### Pendências

- A ANEEL permanece somente como referência até existir contrato/autorização da
  distribuidora; o conector de produção continua bloqueado por FONTE-01.

## 2026-09-30 — invalidação do cache após publicação

### Alterações

- `src/etl/pipeline.py` agora invalida as chaves `api_cache:*` do Redis depois
  do corte bem-sucedido e da gravação dos metadados da entrega.
- Falha no Redis é registrada sem transformar uma publicação já concluída em
  falsa falha operacional; a base e os metadados continuam sendo a fonte de
  verdade.
- Adicionado teste de regressão para garantir que a invalidação ocorre após o
  corte do snapshot.

### Validação

- Testes Python no container: 43 aprovados.
- Compilação Python no container: aprovada.

## 2026-09-30 — falhas de agregação deixam de publicar resultado parcial

### Alterações

- `src/modelos/analise_mercado.py` agora interrompe a análise quando a tabela de
  consumidores está vazia ou quando falha o carregamento/processamento de
  consumidores ou GD.
- Falha ao persistir `cache_mercado` agora propaga erro para que o job derivado
  e o corte do snapshot sejam considerados malsucedidos.
- Adicionado teste de regressão para impedir publicação após falha de
  consumidores.

### Validação

- Testes Python no container: 44 aprovados.
- Compilação Python no container: aprovada.

## 2026-09-30 — simulação sem fallback geográfico silencioso

### Alterações

- `src/api.py` passou a extrair coordenadas de geometria Point/Polygon/
  MultiPolygon e validar latitude/longitude antes de consultar clima.
- Simulações com geometria ausente, inválida ou fora dos limites retornam
  indisponibilidade explícita, em vez de usar Brasília/Aracaju como alvo
  substituto.
- Adicionado teste de contrato para impedir consulta climática quando a
  localização da subestação não está disponível.

### Validação

- Testes Python no container: 45 aprovados.
- Compilação Python no container: aprovada.

## 2026-09-30 — validação geográfica na API de IA

### Alterações

- `src/ai/ai_service.py` passou a rejeitar latitude e longitude fora dos
  intervalos geográficos válidos no contrato `DuckCurveRequest`.
- Adicionados testes de contrato para coordenadas inválidas, evitando que a
  requisição chegue ao cálculo ou ao provedor climático.

### Validação

- Testes Python no container: 47 aprovados.
- Compilação Python no container: aprovada.

## 2026-09-30 — ciclo de vida da IA e startup observável

### Alterações

- O artefato ML passou a carregar a versão e a lista de features do contrato;
  artefatos antigos ou incompatíveis são rejeitados e provocam novo treino
  controlado quando o startup exigir o modelo.
- `validate_model.py` agora recusa artefatos incompatíveis antes da inferência;
  o modelo regenerado foi validado com R² 0,9989 e MAE 0,25.
- `run_all.py` substituiu a espera fixa de 12 segundos por healthchecks HTTP
  dos serviços; o chat possui readiness separado para o armazenamento.
- A API principal adiciona `X-Request-ID` às respostas e aos logs; a API de IA
  não devolve detalhes de exceções internas.
- O modelo configurado em `CHAT_MODEL` passou a ser usado pelo chat, inclusive
  no healthcheck.
- A análise de mercado agora rejeita vínculos espaciais ambíguos em vez de
  escolher silenciosamente o primeiro território.
- README corrigido para os caminhos atuais dos scripts de manutenção e para o
  comando da suíte de regressão.

### Validação

- Testes Python no container: 57 aprovados.
- Compilação Python no container: aprovada.
- Compose recriado com sucesso; startup aprovou os healthchecks da API
  principal, IA e chat.
- `/health` e `/ready` da API principal responderam com banco e Redis OK.

## 2026-09-30 — Compose padrão sem segredos ou código montado

### Alterações

- `docker-compose.yml` deixou de montar o repositório inteiro e o arquivo
  `.env` no contêiner padrão.
- Configurações necessárias passaram a ser encaminhadas explicitamente por
  variáveis de ambiente; dados e logs continuam em volumes dedicados.
- `Dockerfile` cria e executa o serviço com usuário não-root (`uid/gid 1000`),
  mantendo diretórios de dados e logs graváveis.
- Criado `docker-compose.dev.yml` como override explícito para desenvolvimento
  com código e `.env` montados.
- Adicionado teste para impedir regressão dos mounts inseguros.

### Validação

- `docker compose config` do perfil padrão e do override de desenvolvimento:
  aprovados.
- Build da imagem backend: aprovado.
- Suíte Python no container sem bind mount do código: 59 aprovados.
- Smoke real com Compose: processo executando como UID 1000; `/app/.env` e
  `/app/.git` ausentes; `/health` e `/ready` aprovados.

## 2026-09-30 — limites e tratamento seguro do chat IA

### Alterações

- `src/ai/chat_service.py` passou a limitar mensagem, histórico, conteúdo
  total, argumentos e resultados de ferramentas, além de aceitar somente os
  papéis `user` e `model` no histórico.
- Corrigido o default mutável de `historico` e adicionadas restrições para
  feedback, criação e consulta de conversas.
- O loop de function calling mantém no máximo 10 iterações e substitui
  argumentos/resultados excessivos por erro controlado.
- Erros HTTP do chat deixaram de devolver detalhes internos; conteúdo de
  respostas e argumentos não é mais gravado nos logs de debug.
- Adicionado `tests/test_chat_limits.py`.

### Validação

- Testes Python no container: 35 aprovados.
- Compilação Python no container: aprovada.

### Pendências

- Autenticação, titularidade de conversas, rate limit por identidade e política
  de retenção continuam pendentes até a definição do ambiente-alvo e da sessão
  verificável.

## 2026-09-30 — proveniência operacional dos artefatos derivados

### Alterações

- O pipeline marca os jobs derivados com `GRIDSCOPE_DERIVED_STAGING=1`; durante
  a preparação no schema temporário, Voronoi e análise de mercado não publicam
  GeoJSON, imagens ou JSONs locais.
- Falha ao persistir o Voronoi agora interrompe o job em vez de continuar com
  um artefato parcial.
- O cache de arquivos passou a ser opt-in (`ALLOW_FILE_CACHE=false`); a API e
  os relatórios usam o PostgreSQL como fonte operacional e retornam
  indisponibilidade quando não há dados, sem publicar lista vazia como sucesso.
- As chaves Redis incorporam o `delivery_id` publicado, evitando servir cache de
  um snapshot anterior depois da troca das tabelas.
- Adicionados testes para o modo staging, cache versionado, ranking vazio e
  falha de carga em relatórios.

### Validação

- Suíte Python no container: 63 aprovados.
- Compilação Python e `git diff --check`: aprovados.
- Build da imagem backend e `docker compose config` dos perfis padrão e dev:
  aprovados.
- Smoke real: `/health` e `/ready` aprovados; serviço operacional sem cache de
  arquivo e executando como UID 1000.

### Pendências

- O corte integrado ainda precisa ser validado contra GDB real/anonimizado e
  PostgreSQL/PostGIS representativo.

## 2026-09-30 — corte transacional, proveniência e correção do ranking

### Objetivo

Fechar a proveniência da carga (DATA-01/DATA-05) e restaurar a leitura do
ranking, que havia quebrado para dados vindos do banco. Nenhum fluxo que
funcionava antes foi removido: as melhorias só se somam ao comportamento
existente.

### Publicação e proveniência

- `SnapshotImporter` passou a validar colunas obrigatórias e CRS das camadas
  antes de gravá-las no staging.
- O corte registra `delivery_id`, origem, período, horário e contagens em
  `public.grid_scope_publication` dentro da mesma transação que promove tabelas
  brutas e derivadas.
- O corte descarta a tabela antiga antes de promover a nova. Com a ordem
  anterior, o índice `cache_mercado_pkey` da tabela antiga colidia com o da nova
  e a segunda publicação falhava com `relation already exists`.
- `GET /data/status` prioriza os metadados transacionais do banco e usa o JSON
  somente como espelho auxiliar quando necessário.
- Falha ao escrever o espelho JSON não desfaz nem oculta a publicação confirmada
  no banco.
- `src/cache_redis.py` deixou de depender do JSON local para nomear o cache:
  quando o Redis perde a chave de versão, ela é recuperada do registro
  transacional e reassinada. Falha transitória de Redis não vira erro HTTP.

### Correção do ranking (`Erro interno ao carregar o ranking`)

- `sanitizar_dados` chamava `pd.isna` sobre a lista inteira de subestações. Em
  listas o pandas devolve um array, o `if` estourava `ValueError` e o `except`
  devolvia a lista como `string`. O endpoint então iterava sobre caracteres e
  terminava em `AttributeError: 'str' object has no attribute 'get'`.
  Agora a checagem de nulo só é aplicada a escalares.
- `obter_dados_completos` convertia a geometria com `mapping()` mesmo já
  tendo-a como dicionário, o que também estourava. A normalização agora só
  age quando a geometria ainda é um objeto espacial.
- Ambos os defeitos eram anteriores a este trabalho e não eram cobertos: os
  testes substituíam a fusão por um mock. `tests/test_dados_cache.py` e
  `test_ranking_com_fusao_real_nao_quebra_a_geometria` exercitam o caminho real.

### Compatibilidade preservada

- `ALLOW_FILE_CACHE` voltou ao padrão `true`: os arquivos locais continuam sendo
  lidos quando existem e nenhuma entrega foi publicada pelo pipeline. Depois de
  uma publicação canônica o banco prevalece, porque os arquivos não são
  reescritos pelo staging.
- O boot volta a ingerir quando o banco está vazio, como antes;
  `DATA_INGEST_ON_STARTUP` apenas força a ingestão.
- `python -m src.etl.atualizar_banco` aceitou novamente `--only-cache` e
  `--skip-voronoi`. `--only-cache` regenera o cache de mercado a partir do banco
  publicado; `--skip-voronoi` é aceito e informado, mas o corte atômico sempre
  calcula o Voronoi.
- `processar_voronoi.py` e `analise_mercado.py` continuam executando
  isoladamente (dashboard e uso manual). A publicação direta fora do corte não é
  mais bloqueada: apenas registra aviso de que metadados e cache não serão
  atualizados. Dentro do staging, a falha de persistência do Voronoi continua
  fatal para que uma entrega não seja publicada com derivados vazios.
- As duas fontes seguem disponíveis e selecionáveis: `DATA_SOURCE=local_file`
  e `DATA_SOURCE=distributor_http` (alias `http`).

### Validação

- Suíte Python no container: 84 aprovados (82 na suíte padrão e 2 do corte
  transacional, que são ignorados sem `TEST_DATABASE_URL`).
- Build da imagem backend e `docker compose up` sem erros.
- Verificação no serviço em execução: `/health`, `/mercado/ranking` (200 com 13
  subestações e geometria), `/data/status`, `/mercado/geojson` e
  `/mercado/ranking.csv` respondem 200, que é o contrato usado pelo frontend.
- Sintaxe SQL da tabela/registro de publicação e da ordem do corte validadas em
  PostgreSQL com transação revertida.

### Validações de integridade e teste de corte real

- `SnapshotImporter` passou a bloquear identificadores nulos, duplicados,
  geometrias inválidas e referências órfãs entre camadas
  (`consumidores`/`geracao_gd` → `transformadores` → `subestacoes`,
  `rede_mt` → `subestacoes`). Mensagens incluem contagem e exemplos.
- Criado `tests/test_corte_transacional_postgis.py`, o teste "indispensável" do
  DATA-01, executado contra PostgreSQL/PostGIS real: publica A, publica B e
  exige que sobre **somente** B em brutas, derivados e registro de publicação;
  depois tenta publicar B corrompida (referência órfã e ID duplicado) e exige
  que nada mude e que o registro de publicação continue sendo o anterior.
- O teste só roda com `TEST_DATABASE_URL` explícita e nunca reaproveita
  `DATABASE_URL`, porque substitui tabelas inteiras.
- Conferido o resultado no banco: após a sequência ficam apenas `SUB-b-1` e
  `SUB-b-2`, com `grid_scope_publication` apontando para `delivery-b-*`.
- Verificado também que o teste falha contra a versão anterior do importador,
  confirmando que ele cobre o defeito e não apenas o código novo.

## 2026-09-30 — validação do pipeline derivado real

### Alterações

- A primeira execução completa do GDB real encontrou uma divergência: GeoPandas
  salvava Voronoi/cache usando o `search_path`, mas a leitura final do corte
  procurava as tabelas explicitamente no schema temporário.
- `src/database.py` passou a informar `schema=DATABASE_SCHEMA` ao salvar
  Voronoi e a qualificar todas as operações de cache e leitura derivada.
- Adicionado teste de segurança para garantir que jobs derivados respeitem o
  schema configurado.

### Validação

- O pipeline completo foi executado em `gridscope_e2e` com o GDB real, incluindo
  download do limite de Aracaju, Voronoi e análise de mercado.
- O corte publicou atomicamente 55.728 transformadores, 1.066.331
  consumidores, 15.413 registros de GD, 44 subestações, 310.744 trechos de
  rede, 12 territórios Voronoi e 12 registros de cache.
- O registro `grid_scope_publication` aponta para `gdb-real-derived` e mantém o
  `quality_report` dos descartes.
- Suíte Python no container: 90 testes executados, 87 aprovados e 3 testes
  PostGIS ignorados sem `TEST_DATABASE_URL`.
- Teste PostGIS explícito do corte: 3 aprovados.

## 2026-09-30 — descarte auditável de registros incompletos

### Objetivo

Permitir a publicação do GDB real sem transformar cinco registros incompletos
em bloqueio da entrega inteira, mantendo o bloqueio para referências textuais
que apontem para uma camada inexistente.

### Alterações

- Transformadores com `SUB` nulo ou vazio são descartados antes do staging; os
  IDs técnicos e a contagem são registrados em `quality_report`.
- Consumidores e geração distribuída ligados a transformadores descartados, ou
  sem `UNI_TR_MT`, também são descartados e auditados por motivo separado.
- Uma referência não vazia para transformador/subestação inexistente continua
  bloqueando o corte; o teste de entrega corrompida mantém essa garantia.
- `quality_report` passou a acompanhar `row_counts` em
  `public.grid_scope_publication`, no espelho JSON e em `GET /data/status`.
  Bancos com a tabela antiga continuam legíveis e recebem a coluna na próxima
  publicação.
- A leitura do GDB projeta somente as colunas consumidas pelo sistema. No
  GDB real, `UCBT_tab` caiu de 65 para 16 colunas e o pico do snapshot caiu de
  1.731 MB para 734 MB.
- Unicidade deixou de ser exigida em `UCBT_tab`/`UGBT_tab`, onde o mesmo
  transformador e `PN_CON` se repetem legitimamente; permanece apenas onde a
  entrega garante chave única.

### Validação

- Suíte Python no container: 89 testes executados, 86 aprovados e 3 testes
  PostGIS ignorados sem `TEST_DATABASE_URL`.
- Testes PostGIS explícitos: 3 aprovados, incluindo descarte auditado,
  publicação A/B e rejeição de referência textual órfã.
- GDB real publicado em `gridscope_e2e` isolado com derivados mínimos:
  55.728 transformadores, 1.066.331 consumidores, 15.413 registros de GD,
  44 subestações e 310.744 trechos de rede.
- O `quality_report` real registrou 5 transformadores sem `SUB`, 3
  consumidores ligados a eles, 24 consumidores sem transformador e 8
  registros de GD sem transformador.
- Leitura dos metadados transacionais confirmou a entrega, contagens e o
  relatório de qualidade; banco operacional não foi usado para a publicação.

## 2026-09-30 — dashboard com publicação canônica por cidade

### Alterações

- O botão de processamento do dashboard deixou de chamar Voronoi e mercado
  diretamente no schema público quando já existe uma publicação canônica.
- A nova função `ingest_city` altera a cidade, executa o pipeline completo e
  restaura a cidade anterior se a publicação falhar.
- Caches de arquivo continuam funcionando para instalações legadas que ainda
  não possuem `grid_scope_publication`; depois da primeira publicação, a cidade
  selecionada substitui atomicamente o snapshot canônico.

### Validação

- `tests/test_pipeline.py` cobre publicação da cidade selecionada e restauração
  da configuração após falha.
- Suíte Python no container: 92 testes executados, 89 aprovados e 3 testes
  PostGIS ignorados sem `TEST_DATABASE_URL`.

## 2026-09-30 — cidade canônica no frontend

### Alterações

- O tipo `DataStatus` do cliente passou a consumir `city_target`.
- A cidade canônica agora aparece no bloco de conexão e no cabeçalho da carga
  do Panorama, evitando que o usuário confunda uma publicação de outra cidade
  com a carga atual.
- Backend antigo ou cache local sem esse campo exibem `Não informada` sem
  quebrar o carregamento.

### Validação

- `npm run typecheck`: aprovado.
- `npm run build`: aprovado; bundle e service worker PWA gerados.
- Detector visual Impeccable nos arquivos alterados: nenhum alerta.

## 2026-09-30 — cidade canônica no dossiê operacional

### Alterações

- O dossiê técnico em PDF passou a exibir a cidade canônica junto da entrega,
  período, status e total de ativos.
- O campo mantém `Não informada` para cargas legadas sem `city_target`.
- O contrato de `/ready` foi mantido sem alteração: ele continua verificando
  dependências, preservando instalações antigas sem registro transacional.

### Validação

- `npm run typecheck`: aprovado.
- `npm run build`: aprovado; PWA gerada.
- Detector visual Impeccable no modal alterado: nenhum alerta.

### Política conhecida

- O banco canônico representa uma cidade por vez. Suporte a múltiplas cidades
  simultâneas exigirá particionar a publicação e a API, e não será simulado por
  caches locais fora do corte transacional.

## 2026-09-30 — cidade canônica na proveniência da carga

### Alterações

- `grid_scope_publication`, `metadata_carga_atual.json` e `GET /data/status`
  agora expõem `city_target`, deixando explícita a cidade representada pelo
  snapshot canônico.
- `ingest_current_delivery` e `migrar_gdb_para_sql` encaminham a cidade
  configurada para a publicação.
- Bancos antigos sem a coluna continuam legíveis e retornam `city_target: null`
  até a próxima publicação, sem alterar `row_counts`.

### Validação

- Testes PostGIS confirmam gravação e leitura de `city_target`.
- Compatibilidade foi verificada removendo a coluna de uma tabela scratch antiga;
  o status continuou disponível com valor nulo.
- Suíte Python no container: 92 testes executados, 89 aprovados e 3 testes
  PostGIS ignorados sem `TEST_DATABASE_URL`.
