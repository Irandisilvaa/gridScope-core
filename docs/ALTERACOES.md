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
