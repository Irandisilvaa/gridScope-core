# Plano de qualidade e evolução — GridScope Core

> Auditoria estática do repositório em 29/09/2026. Este documento é um roteiro de implementação, não um registro de correções já aplicadas. As ocorrências citadas foram observadas no código; hipóteses sobre comportamento em produção devem ser confirmadas por testes e medições.

## 1. Objetivo, escopo e decisões iniciais

Elevar a confiabilidade do GridScope em **segurança, integridade de dados, correção técnica, disponibilidade, desempenho, experiência, manutenção e operação**. A aplicação contém três APIs FastAPI (principal, simulação e chat), dashboard Streamlit, PostgreSQL/PostGIS, Redis, ingestão da ANEEL, cálculo geoespacial, relatórios e um modelo de consumo. **Direção desejada: dados fornecidos diretamente pela distribuidora como fonte primária, com substituição integral da base publicada a cada atualização concluída; frontend web dedicado no lugar do Streamlit, com possibilidade de instalação como PWA.**

Antes da implantação, definir e registrar:

1. **Ambiente-alvo:** demonstração local, rede interna ou acesso externo. Autenticação, portas públicas e requisitos operacionais dependem dessa escolha. Até lá, tratar histórico do chat e relatórios como dados privados.
2. **Fonte de verdade e substituição:** a distribuidora é a origem primária pretendida; cada atualização publicada substitui integralmente o conjunto operacional anterior pelo novo conjunto completo para a área/período definidos. Se a origem enviar deltas, reconstruir antes um snapshot completo. Não há mescla de cargas nem retenção permanente de versões operacionais antigas; registrar origem, identificador/período recebido e conclusão da substituição.
3. **Significado de risco elétrico:** aprovar com responsável técnico fórmulas, limites e terminologia. Os índices atuais são *proxies* analíticos, não prova de sobrecarga ou de fluxo reverso.
4. **Política para estimativas:** se dados climáticos/mercado/modelo faltarem, definir se a operação deve falhar ou apresentar estimativa **identificada**. Nunca confundir valor sintético com medição.
5. **Compatibilidade:** documentar consumidores dos endpoints/exports existentes antes de mudar esquemas; versionar alterações incompatíveis.
6. **Integração pendente de confirmação:** obter da distribuidora o canal real de entrega, autorização, documentação do esquema, exemplo anonimizado, frequência e política para correções/exclusões. Não pressupor API pública nem prometer atualização em tempo real sem contrato que a suporte.

### Convenção de prioridade

- **P0:** risco de acesso indevido, perda/corrupção de dados, execução comprometida ou resultado fictício apresentado como real. Corrigir antes de expor ou atualizar a aplicação.
- **P1:** funcionalidade incorreta, cálculo inconsistente ou ausência de controle de regressão. Corrigir na estabilização.
- **P2:** manutenibilidade, desempenho e UX. Implementar após estabelecer testes e medições.
- **P3:** evoluções condicionadas a demanda e métricas, não pré-requisitos para estabilização.

## 2. Registro de achados e ações

Cada identificador abaixo pode virar um issue. **Aceite** é verificável; **referência** aponta para o código atual, não para uma linha imutável após refatorações.

### A. Segurança, privacidade e fronteiras de confiança

**SEC-01 — P0 — Conversas sem autenticação/autorização.** `src/ai/chat_service.py:284-295,505-530` aceita `usuario_id` e `conversa_id` do cliente e consulta mensagens por ID; `src/database.py:629-639` não verifica o proprietário; `src/views/tab_chat.py:59-60` usa o hostname como identidade. **Ação:** definir identidade de sessão verificável pelo servidor, associar cada conversa ao principal autenticado e checar titularidade na criação, listagem, leitura e escrita; restringir feedback conforme política. **Aceite:** usuário A recebe 403/404 ao ler ou acrescentar mensagens à conversa de B, mesmo conhecendo o ID; hostname não funciona como identidade; testes de acesso cruzado em todas as rotas.

**SEC-02 — P0 — `eval()` e SQL montado dinamicamente.** `src/reports/data.py:38-59,114-139` interpreta campos com `eval()`; `src/ai/ai_service.py:85-93` e `src/etl/etl_ai_consumo.py:35-49` interpolam IDs no SQL; `src/database.py:48-57,114-123,180-184` interpola colunas. **Ação:** remover `eval` em favor de JSON e validação de esquema; usar parâmetros vinculados para valores e allowlist explícita para identificadores/colunas, que não podem ser parametrizados como valores. **Aceite:** strings maliciosas são rejeitadas sem execução; seleção de colunas fora da allowlist falha com erro controlado; testes de consultas com IDs contendo aspas.

**SEC-03 — P0 — Segredos e serviços expostos por padrão.** `docker-compose.yml:5-38` publica banco/Redis e usa senha fixa; monta o repositório inteiro e `.env` no contêiner. `.env.example:13` contém URL com senha e porta diferentes das do Compose. **Ação:** mover credenciais para variáveis/segredos configuráveis; expor somente portas necessárias ao cenário definido; usar rede interna para banco/Redis; restringir mounts e permissões; retirar fallback de senha operacional. **Aceite:** execução com credenciais fornecidas externamente, sem senha fixa em configuração operacional; banco/Redis não acessíveis externamente no perfil de operação; documentação de desenvolvimento separada.

**SEC-04 — P1 — Extração e download externos sem limites explícitos.** `src/etl/monitor_aneel.py:13-75` baixa arquivo sem limite total e executa `ZipFile.extractall` diretamente no destino. **Ação:** aplicar ao conector acordado validação de origem, limites de tamanho e expansão, integridade, quantidade de entradas e espaço disponível; em entregas ZIP, bloquear caminhos absolutos, `..` e symlinks, extrair em área temporária e validar antes de publicar. **Aceite:** entregas grandes, inválidas ou fora do escopo são recusadas sem modificar o conjunto publicado.

**SEC-05 — P1 — Limites e dados sensíveis no chat/IA.** `src/ai/chat_service.py:266-270,284-490` aceita histórico fornecido pelo cliente e faz até dez iterações de ferramentas, sem limites de tamanho ou orçamento por requisição; exceções podem ir ao corpo HTTP (`:489-490`). **Ação:** limitar mensagem, histórico, gráficos, parâmetros e tempo/custo; validar roles e argumentos das ferramentas; obter histórico confiável no servidor quando houver conversa persistida; aplicar rate limit por identidade; registrar política de retenção e envio ao provedor externo. **Aceite:** entradas excessivas são recusadas com erro definido; requisições concorrentes não excedem orçamento configurado; respostas HTTP não contêm traceback, SQL nem detalhes de infraestrutura.

**SEC-06 — P2 — Exportações e logs.** `src/pdf_report.py:424-445` exporta campos textuais para CSV; `run_all.py:16-28` grava logs locais; `src/ai/chat_service.py:358` registra argumentos de ferramenta. **Ação:** neutralizar fórmulas CSV ao abrir em planilhas, redigir dados sensíveis nos logs, definir retenção/rotação e acesso a backups, logs e relatórios. **Aceite:** exportação com células iniciadas por `=`, `+`, `-` ou `@` não executa fórmulas em planilha; logs não incluem mensagens ou tokens desnecessários.

### B. Integridade do ETL, dados e geoprocessamento

**DATA-01 — P0 — Substituição integral pode reportar sucesso parcial.** `src/etl/migracao_db.py:33-49,67-115,117-140` limpa tabelas e as repopula — **a substituição integral é desejada** —, mas captura erro por camada com `pass`; falhas de conexão/arquivo também retornam normalmente. **Ação:** carregar em *staging* um snapshot completo recebido da distribuidora (ou convertido do formato acordado), validar contagem, esquema, CRS, vínculos e unicidade; concluir a troca de todas as tabelas publicadas em uma operação coordenada/transacional, descartando o conjunto anterior no corte; propagar erro e código de saída. Staging é transitório e não implica manter histórico de bases. Planejar espaço em disco durante a carga e recuperação caso a troca falhe. **Aceite:** após êxito, tabelas contêm **apenas** dados da nova entrega validada, sem registros antigos; falha antes do corte não deixa dados parcialmente substituídos nem sinaliza sucesso.

**DATA-02 — P0 — Fluxo ANEEL atual não corresponde à fonte-alvo.** `src/etl/monitor_aneel.py:77-200` pesquisa/baixa dados da ANEEL e chama `migrar_gdb_para_sql(limpar_antes=True)` (`:172`), mas `src/etl/migracao_db.py:117` não aceita esse argumento; `run_all.py:106-108` executa o monitor a cada inicialização. O monitor grava `metadata_aneel.json` antes da carga (`monitor_aneel.py:153-163`). **Ação:** trocar o gatilho principal por integração contratada com a distribuidora (FONTE-01/02); corrigir assinatura/propagação de erro do importador e torná-lo independente da origem do arquivo; deixar a ANEEL apenas como referência de validação ou fonte de contingência **se expressamente aprovada**, nunca como substituição silenciosa. **Aceite:** uma entrega da distribuidora percorre aquisição, importação, Voronoi e cache; a ANEEL não altera a base operacional por iniciativa própria; falha não marca a entrega nova como publicada.

**DATA-03 — P1 — Mercado pode falhar ou persistir parcialmente.** `src/modelos/analise_mercado.py:116,142,181` inicia `mapa_pn_classe` como `{}` e depois acessa `.empty`; exceções de consumidores/GD são ignoradas (`:161-196`) e ainda se tenta salvar resultados (`:385-397`). **Ação:** inicializar tipos consistentes, exigir insumos obrigatórios e regras explícitas para campos opcionais; só persistir agregados depois de checar qualidade. **Aceite:** casos sem consumidores, sem GD, com PN_CON ausente ou inválido não causam AttributeError nem publicam agregação incompleta como válida.

**DATA-04 — P1 — Correspondências e geometria precisam de invariantes.** `src/modelos/analise_mercado.py:89-110` usa `intersects` e escolhe um vínculo após `drop_duplicates`, inclusive em bordas; `src/utils.py:128-174` associa geometria por nome e ID e devolve `[]` ao falhar; `src/modelos/processar_voronoi.py:89-101` repete `dissolve` e `explode`. **Ação:** preferir ID estável, definir desempate espacial determinístico, validar CRS, geometrias válidas, cobertura do município, sobreposição, ausência de buracos e taxa de vínculos; testar pontos em fronteiras. **Aceite:** cada transformador elegível é atribuído a exatamente uma subestação ou aparece em relatório de exceções; cobertura e tolerâncias são medidas e aprovadas.

**DATA-05 — P1 — Cache derivado deve acompanhar a substituição total.** `src/database.py:270-309` apaga `cache_mercado` e reinserta registros na mesma transação, mas `criar_tabela_cache()` usa outra engine/conexão; `src/cache_redis.py:40-89` possui TTL sem invalidar após nova carga. **Ação:** definir esquema via migrações, recomputar Voronoi/mercado para o **novo conjunto completo** antes de publicar e invalidar Redis/cache Streamlit quando ele substituir o anterior. Identificador da carga serve para consistência e rastreabilidade, não para guardar dados antigos. **Aceite:** após a troca, tabelas brutas, territórios, agregados e respostas em cache correspondem à mesma entrega da distribuidora; nenhuma consulta combina cargas.

**Regra operacional de substituição (DATA-01/02/05 e FONTE-03):**

1. Receber e identificar a entrega da distribuidora no formato contratado; se chegar por alterações parciais, materializar e conferir o snapshot completo antes de publicar. Não alterar o conjunto visível aos usuários durante a preparação.
2. Carregar **todos** os registros novos em área temporária, processar territórios e agregados correspondentes e validar contagens/chaves/geometrias; uma camada vazia só é aceita se sua ausência for explicitamente permitida.
3. Se qualquer etapa falhar, encerrar com erro, descartar a carga temporária e **não afirmar que a atualização ocorreu**. Isso não cria uma política de guardar bases históricas: apenas evita publicar meia carga.
4. Se todas passarem, substituir o conjunto publicado **por inteiro**, incluindo tabelas derivadas e identificador da carga, em corte coordenado. Excluir dados antigos nesse corte; não anexar registros novos aos antigos e não manter cópia histórica nas tabelas de operação.
5. Atualizar os caches externos e os metadados auxiliares após o corte de forma recuperável; caso a escrita do arquivo auxiliar falhe, o registro transacional da carga atual no banco continua sendo a fonte de verdade. Backups operacionais, se habilitados, têm política de retenção própria e não são versões disponíveis para consulta na aplicação.

**Teste indispensável:** publicar entrega A com IDs exclusivos, depois B com IDs exclusivos; após sucesso, encontrar **somente B** em tabelas brutas, Voronoi, cache e API. Repetir com entrega B incompleta/corrompida ou falha durante importação: não encontrar mistura A+B nem status de sucesso.

**DATA-06 — P2 — Escalabilidade do processamento.** `src/database.py:20-36` recria/testa engine repetidamente; `src/modelos/analise_mercado.py:85-195` carrega tabelas completas; `src/modelos/processar_voronoi.py:75-103` processa todos os pontos em memória. **Ação:** reutilizar engine com pool, selecionar colunas, processar em lotes ou agregar no PostGIS quando medição justificar, revisar índices com `EXPLAIN (ANALYZE, BUFFERS)` e medir memória/tempo por etapa. **Aceite:** metas de tempo/memória definidas contra dataset representativo e atingidas sem alterar contagens ou geometria além de tolerância documentada.

### C. Correção funcional, modelo e domínio elétrico

**DOM-01 — P1 — Criticidade contraditória entre superfícies.** ETL usa relação potência GD/demanda média com limites 0,4 e 1,0 (`src/modelos/analise_mercado.py:314-323`); dashboard da subestação usa energia solar estimada/consumo e limites 15%/25% (`src/views/analise_subestacao.py:141-156`); prompt do chat descreve proporção de clientes com GD (`src/ai/chat_service.py:43-49`); `src/reports/data.py:70-85` calcula outro indicador. **Ação:** criar catálogo de indicadores e função única por indicador; diferenciar *penetração de unidades*, *potência/demanda* e *energia estimada/consumo*. Revisar nomes, premissas e faixas com especialista antes de alterar valores. **Aceite:** fixture conhecida recebe mesma classificação em ETL, APIs, dashboard, chat e PDF; cada indicador mostra fórmula, unidade e limitações.

**DOM-02 — P1 — Unidades e curvas físicas ambíguas.** `src/views/tab_ia.py:119-135` multiplica consumo abaixo de 500 por 1.000, mas o campo enviado chama `consumo_mes_alvo_mwh`; `src/ai/ai_service.py:195-210` volta a inferir kWh/W pela magnitude. O mesmo serviço reduz ou aumenta a curva com `fator_escala` após normalizar energia mensal (`:258-265`) e altera `curve_consumo` após calcular `curve_liquida` (`:281-308`). **Ação:** tipar unidades de entrada/saída sem heurística, definir se séries horárias são potência média (kW) ou energia por intervalo (kWh), conservar energia da entrada quando essa for a regra e calcular curva líquida **após** eventuais ajustes. **Aceite:** testes de conservação e consistência por hora/mês; `carga_liquida = consumo - geração` em cada posição; valores positivos/zero e unidades documentadas.

**DOM-03 — P1 — Local e clima podem não representar o alvo.** `src/views/analise_subestacao.py:104-114,128-131` calcula centróide da área, mas não o inclui em `subestacao_obj`; `src/views/tab_ia.py:124-135` usa coordenadas padrão de Brasília. `src/api.py:204-216` tenta extrair coordenadas a partir de vértices do polígono ou usa Aracaju como fallback. **Ação:** transmitir coordenada/ID do alvo de forma explícita, usar ponto da subestação ou ponto representativo, validar latitude/longitude e retornar origem da localização e clima; tratar datas fora da cobertura da API meteorológica. **Aceite:** requisições de subestações diferentes usam coordenadas coerentes; falha de geolocalização não produz silenciosamente simulação de outra cidade.

**DOM-04 — P1 — Modelo treinado/validado de modo inconsistente.** `src/ai/train_model.py:38-114` cria dados sintéticos sem semente para a geração; `src/ai/validate_model.py:9,72-83,125-135` procura outro diretório e usa conjunto de *features* diferente do treino. `run_all.py:131-132` treina a cada subida. **Ação:** fixar sementes, versionar dataset, artefato e esquema de *features*; treinar em job separado; validar contra base independente e métricas por segmento; permitir apenas artefatos locais confiáveis (carregamento `joblib` executa código ao desserializar conteúdo malicioso). **Aceite:** treino reproduzível, validação usa mesmo contrato de entrada, inicialização funciona sem retreino e disponibiliza versão do modelo.

**DOM-05 — P1 — Fallbacks confundem ausência e dado real.** `src/pdf_report.py:217-220,306-345` devolve valores aleatórios em erro; `src/ai/ai_service.py:120-148,150-179` usa clima/perfil sintético; `src/utils.py:94-125` devolve dados vazios em exceção; `src/api.py:113-115` retorna clima padrão. **Ação:** modelar estado da fonte (`real`, `previsto`, `estimado`, `indisponível`), registrar motivo e data, proibir mocks em operação e decidir explicitamente quando estimativas são aceitáveis. **Aceite:** banco indisponível retorna erro/estado indisponível, não CSV/PDF de valores inventados; estimativas permitidas são rotuladas em toda saída.

**DOM-06 — P1 — Relatórios podem usar alvo/dados incorretos.** `src/pdf_report.py:465-470` escolhe primeira subestação se ID não for encontrado; `src/reports/data.py:29-36,77-85` faz o mesmo e rotula consumo como capacidade; `src/views/relatorios.py:212-218,253-270` coleta data que não é repassada ao gerador (`src/pdf_report.py:591-598`). **Ação:** retornar erro de ID inválido, remover métrica fictícia ou calcular capacidade com fonte adequada, repassar data escolhida e conferir totais/rótulos. **Aceite:** ID inexistente não gera relatório de outra subestação; cabeçalho usa a data solicitada; CSV/PDF concordam com dataset de referência.

**DOM-07 — P2 — API pública e consultas devem ter contrato claro.** `src/api.py:38-59,121-145` declara `detalhe_por_classe: Dict[str, float]`, enquanto `src/modelos/analise_mercado.py:366-380` preenche dict com `potencia_kw` e `qtd`; `src/api.py:181-197` permite match parcial ambíguo por nome. **Ação:** definir modelos de resposta aderentes aos dados reais, validação na fronteira, versão da API para mudanças incompatíveis, busca por ID estável e comportamento definido para nomes duplicados. **Aceite:** respostas validadas por testes de contrato; requisição ambígua não escolhe silenciosamente a primeira subestação.

### D. Infraestrutura, disponibilidade e operação

**OPS-01 — P0 — Configuração inconsistente e startup frágil.** `src/cache_redis.py:10-16` tenta importar `REDIS_HOST/PORT/DB` não definidos em `src/config.py`; `run_all.py:79-104` lê `DATABASE_URL` do ambiente antes de importar `config.py`, portanto não carrega `.env` via esse caminho. `.env.example:13` usa porta 5433, Compose publica 5435 e `src/config.py:25` usa 5435 como padrão. **Ação:** criar configurações tipadas por serviço, carregar `.env` somente no perfil local, validar parâmetros obrigatórios no início e manter um único mapa documentado de portas/hosts. **Aceite:** `docker compose config` e processo local usam valores coerentes; Redis local e em Compose conectam mediante configuração explícita; erros de configuração apontam a variável ausente.

**OPS-02 — P1 — Inicialização mistura ETL, treino e servidores.** `run_all.py:106-188` consulta ANEEL, migra, recalcula e treina antes de subir APIs, não exige sucesso de Voronoi/mercado/treino e verifica disponibilidade do dashboard com `sleep(12)`; `docker-compose.yml:14-15` espera apenas início do banco. **Ação:** jobs de ETL/treino independentes, políticas de retry e timeouts, readiness para banco/Redis/APIs, encerramento ordenado dos filhos e política por serviço obrigatório/opcional. **Aceite:** falha em etapa obrigatória impede prontidão; SIGTERM encerra filhos sem órfãos; novo deploy não reexecuta ETL desnecessariamente.

**OPS-03 — P1 — Backup não acompanha Compose.** `scripts/backup_db.py:17` chama `docker-compose exec -T gridscope_db pg_dump -U gridscope_user gridscope_db`, mas o serviço é `db`, usuário `postgres` e banco `gridscope_local` em `docker-compose.yml:19-30`; o script engole falhas (`backup_db.py:30-31`). **Ação:** parametrizar origem, executar comando sem shell, salvar em arquivo temporário com verificação, mover atomicamente, proteger diretório e exercitar restauração periódica; definir RPO/RTO conforme ambiente. **Aceite:** backup e restore em banco descartável preservam amostras e esquemas; falha produz código de saída diferente de zero.

**OPS-04 — P1 — Dependências e automação não são reproduzíveis.** `requirements.txt` duplica `pandas` (`:34,69`), mistura versões fixas e mínimas e não declara `tqdm` usado por `src/etl/migracao_db.py:7` nem `weasyprint` usado por `src/reports/generator.py:2` (verificar se esse gerador será mantido). `.github/workflows/verificar_aneel.yml:19-24` instala só `requests`, mas o monitor importa `src/config.py`, que requer `python-dotenv`; esse workflow não dispõe do banco/dataset usado na atualização. **Ação:** dependências diretas + lock/constraints por Python suportado, separar extras/jobs e substituir o workflow de atualização operacional ANEEL por orquestração da entrega da distribuidora no ambiente autorizado; manter verificação ANEEL isolada apenas se tiver finalidade definida. **Aceite:** instalação limpa e CI executam testes com fixtures sem credenciais reais; publicação de dados só roda no ambiente que recebe a entrega autorizada.

**OPS-05 — P2 — Observabilidade e documentação.** `src/database.py:16`, `src/utils.py:14` e outros configuram logging global; APIs devolvem detalhes de erros internos (`src/api.py:143-155`, `src/ai/ai_service.py:321-323`). `README.md:64-69` indica comandos de scripts fora de `scripts/`. **Ação:** logs estruturados, ID de correlação, métricas de ingestão/frescor/latência/erros, healthcheck separado de readiness, alertas e runbooks para distribuidora, banco, Redis, clima e IA; atualizar README com instalação, portas, comandos e contratos. **Aceite:** operador localiza identificador e horário da última carga, origem e causa da falha sem ler traceback no cliente.

**OPS-06 — P2 — Imagem e perfis de execução.** `Dockerfile:1-28` instala toolchain no runtime, copia todo o contexto e executa múltiplos serviços por um processo; Compose também monta `.:/app` (`docker-compose.yml:8-12`). **Ação:** adicionar `.dockerignore`, imagens/estágios mínimos compatíveis com dependências geoespaciais, usuário não-root, volumes apenas para dados necessários; separar processos ou manter supervisor explícito com verificações e parada confiável. **Aceite:** build reprodutível sem `.env`, logs, cache ou GDB no contexto; serviços reiniciam e reportam falha isoladamente.

### E. Arquitetura, testes, desempenho e experiência

**ENG-01 — P1 — Cobertura automatizada inexistente no repositório.** Não há suíte de testes rastreada em `git ls-files`; scripts `__main__` não substituem testes de regressão. **Ação:** estabelecer `pytest` com fixtures pequenas de BDGD/GeoDataFrame e teste integrado PostgreSQL/PostGIS+Redis; adicionar testes de contrato de API, relatórios e segurança. Priorizar cenários dos itens P0/P1, sem depender de ANEEL/Gemini/Open-Meteo reais no CI. **Aceite:** pipeline executa testes determinísticos e falha ao reintroduzir qualquer bug P0 documentado.

**ENG-02 — P2 — Organização e duplicação.** `src/database.py` mistura acesso, DDL e histórico de chat (`:245-652`); `src/pdf_report.py` concentra carga, filtro, IA e renderização (`:1-730`); há manipulação de `sys.path` em módulos de API, views e ETL; `src/api.py:26` e `src/utils.py:76` implementam versões diferentes de `limpar_float`. **Ação:** empacotar projeto, manter imports explícitos, extrair módulos por domínio/repositório/serviço/adapter, eliminar duplicação gradualmente com testes; definir esquema tipado compartilhado para cache e exports. **Aceite:** imports funcionam do pacote instalado e do Compose; sem fallbacks que ocultem ImportError; resultados numéricos preservados por fixtures.

**ENG-03 — P2 — Falhas silenciosas e estado global.** `src/database.py:459-652` cria tabelas em runtime e suprime falhas em funções de conversa; `src/ai/chat_service.py:25-30` chama DDL na importação; `src/ai/ai_service.py:30-46` carrega modelo/banco na importação; `src/views/analise_subestacao.py:67-78` usa cache Streamlit sem TTL/invalidação associada à versão do ETL. **Ação:** migrações versionadas, inicialização controlada, dependências injetáveis, exceções tipadas e política de cache com versão dos dados. **Aceite:** importar módulo não cria tabelas nem exige banco; falha de gravação não produz confirmação falsa; publicação de ETL torna dados novos visíveis.

**ENG-04 — P2 — Performance medida, não presumida.** `src/cache_redis.py:84-89` usa `KEYS`; `src/api.py:121-155` serializa ranking e GeoJSON completos; `src/views/relatorios.py:112-151` recarrega dados para preview e CSV. **Ação:** medir volume/p95/memória primeiro; substituir `KEYS` por invalidação por versão ou `SCAN`, revisar limites/paginação e payload geoespacial, evitar consultas duplicadas na mesma interação e testar cache sob concorrência. **Aceite:** metas de p95 e memória definidas para dataset realista, comparadas antes/depois; sem regressão de dados.

**UX-01 — P2 — Estados e consistência de interface.** `src/dashboard.py:193-195` exibe assistente “Online” sem consultar disponibilidade; `src/views/tab_chat.py:261-264` limpa tela/histórico local, mas não remove conversa persistida; `src/views/relatorios.py:253-270` exibe botão de download apenas no ciclo de geração do PDF; partes da UI mostram exceções diretamente. **Ação:** distinguir serviço indisponível de sem dados; definir semântica de “Nova conversa”, “Limpar tela” e “Excluir histórico”; manter PDF gerado em sessão até download; feedback acessível, rótulos claros, contraste e responsividade. **Aceite:** estado exibido reflete serviço/dados; ações sobre conversas têm resultado previsível; PDF continua disponível após rerender esperado.

**UX-02 — P2 — Acessibilidade e usabilidade na nova interface.** `src/dashboard.py:66-146` contém estilos inline; mapas e gráficos concentram informação por cor. **Ação:** construir a interface substituta com navegação por teclado, texto alternativo, contraste, unidades nas legendas, layout responsivo e linguagem para indicadores estimados desde o início. **Aceite:** checklist de acessibilidade definido e testado com cenários reais de dashboard, gráficos e exportações.

### F. Substituição integral do Streamlit

**WEB-01 — P1 — Backend depende da interface Python.** `src/views/visao_geral.py:180-445` e `src/views/analise_subestacao.py:25-409` consultam diretamente o banco via `carregar_dados_cache()` e calculam indicadores durante o render; `src/views/relatorios.py:14-304` chama funções Python para gerar arquivos. Um frontend no navegador não pode executar essas funções. **Ação:** extrair regras de negócio das views para serviços reutilizáveis e expor contratos HTTP autenticados de leitura, simulação e exportação. **Aceite:** nova interface não consulta PostgreSQL/Redis diretamente nem duplica as fórmulas elétricas em TypeScript; respostas batem com fixtures aprovadas.

**WEB-02 — P1 — Interface Streamlit é o único fluxo completo.** `src/dashboard.py:155-242` roteia Visão Geral, Análise, Relatórios e Chat; `src/views/tab_ia.py:20-69` e `src/views/tab_chat.py:8-46` usam URLs locais fixas. **Ação:** criar app web próprio, migrar cada fluxo com controles e estados equivalentes e API base configurável pelo ambiente, antes de remover o dashboard antigo. **Aceite:** navegação direta/atualização de página, telas vazias, indisponibilidade de serviço, download e interação em dispositivos menores funcionam sem Streamlit.

**WEB-03 — P1 — Publicação conjunta requer fronteira de segurança.** No Compose somente `8000`/`8501` são publicados, mas APIs de IA/chat usam `8001`/`8002` (`docker-compose.yml:5-7`, `run_all.py:142-156`); o chat atual confia em identidade fornecida pelo cliente (SEC-01). **Ação:** publicar frontend e um ponto de entrada HTTP seguro; manter serviços internos e integrar autenticação/autorização antes de expor chat/exports ao navegador. **Aceite:** o navegador acessa apenas origens/rotas aprovadas, não conhece credenciais do banco/Gemini e não consegue consultar conversas de outro usuário.

**WEB-04 — P2 — Tornar o frontend instalável como PWA.** React/Vite permite distribuir a interface como Progressive Web App, mas a instalação não torna APIs, PostGIS, simulações ou chat disponíveis offline. **Ação:** após estabilizar navegação e autenticação, adicionar manifesto e service worker (por exemplo, via `vite-plugin-pwa`), ícones dedicados, nome, tema e tela de indisponibilidade; definir política de cache e atualização descrita abaixo. **Aceite:** app instalável em navegador compatível sob HTTPS (ou localhost em desenvolvimento), abre a interface instalada com ou sem rede, sinaliza indisponibilidade de dados sem apresentar uma carga anterior como atual e atualiza arquivos estáticos sem exigir que o usuário limpe manualmente o cache.

#### Arquitetura proposta para validação na Fase 0

- **Frontend:** `frontend/` com React + TypeScript + Vite. É uma aplicação de dashboard autenticado; renderização no servidor não é requisito identificado. Estabelecer componentes, tokens visuais, formatos `pt-BR`, rotas, estados de carregamento/erro e testes de interface. Escolher bibliotecas de estado/formulário apenas quando a necessidade concreta aparecer; evitar manter um segundo modelo de domínio independente.
- **Visualizações:** iniciar com React-Leaflet/Leaflet para GeoJSON dos territórios e Plotly.js para gráficos, por compatibilidade com Folium/Plotly já usados. Receber dados estruturados da API; validar custo de bundle e volume de GeoJSON com dataset representativo antes de fixar a solução de mapas/gráficos. Revisar política de uso/atribuição das tiles em operação.
- **Backend:** manter Python para ETL, cálculos, modelo, Gemini, acesso a PostGIS, CSV e PDF. FastAPI fornece modelos tipados, autenticação e contratos OpenAPI; gerar/verificar tipos do cliente a partir do contrato ou usar testes de contrato para impedir divergência. Escolher entre compor as três aplicações sob uma origem ou usar gateway/reverse proxy; manter serviços internos indisponíveis diretamente pela internet.
- **Transporte:** navegador → frontend estático e `/api` na mesma origem → FastAPI → serviços/banco internos. Sessão ou token com gestão no servidor conforme ambiente-alvo; para cookie de sessão, CSRF e atributos Secure/HttpOnly/SameSite apropriados. Segredos e chamadas ao Gemini permanecem no backend. Não habilitar CORS amplo para contornar configuração de proxy.
- **Estado dos dados:** API informa identificador da carga atual, período, fonte e qualidade; frontend invalida consultas quando o conjunto completo é substituído, sem replicar regras de cache Streamlit. O identificador não implica armazenar múltiplas versões. Simulação e exportação são ações explícitas, com feedback de execução e limites de tamanho/tempo.
- **Proveniência visível:** disponibilizar, por exemplo, `GET /api/v1/data-status` com origem (`distribuidora` ou contingência identificada), identificador da carga, data de referência, horário da publicação e situação de atraso/indisponibilidade; é uma proposta de contrato a validar com FONTE-04. Exibir no overview, relatórios e PWA sem rotular snapshot cadastral como informação em tempo real.
- **PWA instalável (WEB-04):** adicionar `manifest.webmanifest`, ícones adequados (incluindo variante *maskable*), `display: standalone`, `start_url`, `scope`, `theme_color` e service worker do build Vite. Pré-armazenar **somente shell e assets estáticos versionados** (HTML/CSS/JS/ícones e tela offline); atualizar HTML prioritariamente pela rede quando ela estiver disponível e tratar atualização do service worker sem interromper formulários ou operações em curso. Servir sob HTTPS no ambiente publicado.
- **Política offline/cache:** não interceptar nem persistir em Cache Storage/IndexedDB respostas autenticadas de `/api`, GeoJSON, indicadores, conversas, gráficos do chat, PDF/CSV ou simulações. Para essas requisições, usar rede e mostrar estado offline/erro; não criar fila de escrita automática para chat/feedback. O cache de consulta em memória deve ser invalidado ao mudar o identificador da carga ou encerrar a sessão. Evitar que o fallback da SPA transforme erro de API em HTML com status 200.
- **Possível expansão posterior — P3:** se houver necessidade comprovada de consultar indicadores offline, definir consentimento, escopo por usuário, proteção de dados, TTL e chave composta por usuário + identificador da carga; apagar dados locais no logout e quando a nova carga substituir a antiga. Esse recurso exige teste específico e **não** faz parte do primeiro PWA.

#### Inventário de equivalência funcional e contratos a implementar

| Fluxo Streamlit atual | Entrega da nova interface | Contrato HTTP proposto (nomes sujeitos à definição OpenAPI) |
| --- | --- | --- |
| `src/views/visao_geral.py` | cinco indicadores, mapa de criticidade com legenda/tooltip, tabela de subestações, CSV, distribuição de risco e top 5 GD | `GET /api/v1/overview`, `GET /api/v1/substations?…`, `GET /api/v1/territories`, `GET /api/v1/exports/overview.csv`; paginação/filtros se volume exigir |
| `src/views/analise_subestacao.py` | seleção por ID, dados e mapa do território, GD/perfil por classe, histórico mensal, tabela consolidada e indicadores com a mesma fórmula aprovada | `GET /api/v1/substations/{id}` e `GET /api/v1/substations/{id}/history`; não retornar primeira subestação em ID ausente |
| `src/views/tab_ia.py` | seleção de data, curva de consumo/geração/carga líquida, filtros por classe, estados de clima/modelo e origem | `POST /api/v1/substations/{id}/simulations/duck-curve` e consulta solar conforme contrato; mapear endpoints legados `/simulacao/{nome_subestacao}` e `/predict/duck-curve` sem depender de nome parcial |
| `src/views/relatorios.py` | filtros separados CSV/PDF, prévia, data de referência, seções, geração e download persistente até concluir | `GET/POST /api/v1/exports/csv` e `POST /api/v1/reports/pdf` com filtros validados; streaming ou job assíncrono conforme duração medida |
| `src/views/tab_chat.py` | lista/abertura de conversas, nova conversa, mensagens, gráficos, sugestões e feedback; autorização por usuário | rotas autenticadas `/api/v1/chat/…` cobrindo mensagem, lista, detalhe e feedback; modelo de erro para cota/serviço indisponível |

Os caminhos acima são **propostas de contrato**, não endpoints já disponíveis. Inventariar parâmetros, tipos, respostas e casos de erro reais na Fase 0. Exports e simulações devem reutilizar serviços Python após correções SEC/DOM/DATA, sem copiar a lógica presente nas views. Conteúdo do chat deve ser renderizado de forma segura (Markdown controlado, sem HTML executável); gráficos retornados por ferramenta exigem validação/limite de tamanho.

#### Sequência de migração, convivência e retirada

1. **Preparar backend (Fases 1–3):** SEC-01/02/03, DOM-01/02/05 e DATA-01 têm precedência. Extrair serviços das views, criar respostas tipadas para overview/detalhe/export e testes de contrato; manter rotas legadas apenas durante migração quando houver consumidores identificados.
2. **Criar casca da aplicação:** iniciar `frontend/`, pipeline de build/lint/testes, rota inicial, design responsivo e proxy local para `/api`; publicar prévia interna isolada com os serviços necessários e fonte de dados explicitada.
3. **Migrar por fatias verticais:** primeiro Visão Geral e detalhe de subestação; depois simulação; relatórios; por último chat após autorização. Em cada fatia, comparar fixtures, indicadores, mapa/gráficos, exportação e falhas com a regra corrigida; ativar a rota nova apenas depois do aceite.
4. **Corte controlado:** testar navegação, autenticação, permissão, acessibilidade, exportações, celular, carga e observabilidade com dataset representativo; tornar o frontend novo o endereço principal. Manter rollback por configuração de roteamento durante uma janela definida e monitorar falhas/uso.
5. **Retirada:** somente após aceite de todos os fluxos e fim da janela de rollback, remover `src/dashboard.py`, `src/views/`, dependências exclusivas de Streamlit/Folium de UI em `requirements.txt`, porta 8501, processo Streamlit em `run_all.py`, caches e documentação legada. Verificar quais bibliotecas geoespaciais/Plotly ainda são usadas pelo backend antes de removê-las.
6. **PWA após estabilidade:** implementar WEB-04 depois que rotas, sessões e atualização da carga estiverem confiáveis. Testar instalação, rede desligada, atualização de build, publicação de nova entrega da distribuidora e logout em navegador e aparelho móvel compatíveis antes de promover o service worker.

**Critério de desativação do Streamlit:** nenhuma função exclusiva da interface antiga é necessária; paridade funcional corrigida e testes de contrato/E2E verdes; segurança e origem dos dados visíveis; usuários acessam o novo endereço; rollback de roteamento e backup operacional documentados. A remoção não depende de redesenhar toda a estética, mas não deve perpetuar bugs de cálculo por apego à paridade visual.

### G. Alimentação direta pela distribuidora

**Situação comprovada:** o caminho atual pesquisa a ANEEL (`src/etl/monitor_aneel.py:77-132`), baixa um ZIP e extrai um GDB (`:13-75`); `src/etl/migracao_db.py:14-27,67-109` lê camadas de um caminho local definido por `FILE_GDB`; `run_all.py:106-123` inicia esse fluxo ao subir os serviços. **Não há no repositório um contrato, credenciais nem adaptador de integração direta com a distribuidora.** O canal e a cadência de entrega ainda são desconhecidos. Toda decisão abaixo sobre transporte é condicional à confirmação com a fonte.

**FONTE-01 — P0 — Formalizar acesso e contrato de dados.** Obter documentação e amostra de uma entrega real anonimizada, autorização de uso/armazenamento e contato técnico da distribuidora. Definir se será API (consulta com paginação ou envio), SFTP/arquivo entregue, bucket privado ou outro canal; autenticação, ambientes de teste/operação, limites, frequência, fuso, identificador de entrega, integridade e sinal de “entrega completa”. Inventariar campos necessários a subestações, transformadores, consumidores, GD e rede MT; registrar IDs estáveis, relações, tipo, unidade, data de referência e CRS da geometria. **Aceite:** contrato assinado/aprovado e fixture representativa que permita mapear todas as tabelas obrigatórias; nenhuma suposição de disponibilidade de API de distribuidora é tratada como fato.

**FONTE-02 — P1 — Implementar conector desacoplado do importador.** Criar adaptador isolado para o canal acordado, sem lógica de cálculo; autenticar com segredos fora do repositório; receber em área temporária, validar integridade/tamanho/formato e produzir um manifesto normalizado (origem, ID/hash da entrega, período, tipo `snapshot`/`delta`, esquema, contagens esperadas e horário). Para API paginada, exigir paginação completa/sinal de término; para arquivos, validar arquivo e manifesto; para push/webhook, autenticar emissor, confirmar recebimento sem assumir publicação e processar em job. Implementar retry limitado, backoff, idempotência por ID/hash e política para entrega duplicada/atrasada. **Aceite:** entrega repetida não duplica dados; entrega incompleta ou não autenticada é recusada; conector não altera tabelas visíveis antes da validação.

**FONTE-03 — P0 — Snapshot completo como única unidade de publicação.** Se a distribuidora enviar base completa, mapear formato acordado (GDB, GeoPackage, CSV/Parquet + geometrias ou API) para o esquema canônico em *staging*. Se enviar apenas deltas, definir com a fonte eventos de inclusão/alteração/**exclusão**, ordenação e cursor; reconstruir **snapshot completo** em staging e só então substituir integralmente tabelas operacionais, territórios e agregados. Delta incompleto, cursor com lacuna ou entrega fora de ordem **não** deve apagar a base atual nem ser publicado parcialmente. A necessidade de materialização transitória não muda a regra de que a aplicação consulta somente a carga completa vigente. **Aceite:** carga A seguida de snapshot B ou deltas que produzam B deixa só B acessível; exclusões propagam; lacuna de páginas/eventos bloqueia o corte.

**FONTE-04 — P1 — Governar qualidade, rastreabilidade e atualização.** Validar esquemas/colunas obrigatórias, tipos, IDs únicos, relações consumidor→transformador→subestação, somatórios, limites de valor, consistência temporal, cobertura e CRS; produzir relatório com totais e rejeições antes do corte. Manter **metadados da carga publicada atual** no banco (origem, identificador/hash, período, timestamp e contagens) separados do status da tentativa em andamento/rejeitada; não manter cópias históricas operacionais. Definir limiares de qualidade com a distribuidora e alertas para carga ausente, atrasada, incompleta, rejeitada ou sem mudança; medir atraso entre referência da fonte e publicação. Mostrar fonte/período/horário da última atualização na API, frontend e PWA. **Aceite:** falha deixa estado `atrasado` ou `indisponível` visível sem fingir atualização; somente entrega íntegra altera o identificador de carga publicado; registro atual corresponde a API/cache/exportações.

**FONTE-05 — P1 — Segregação de dados e execução.** Restringir acesso aos arquivos recebidos e campos sensíveis de consumidores ao mínimo necessário para agregação; definir retenção/remoção dos temporários, segredos rotacionáveis e trilha de execução sem armazenar payload pessoal nos logs. Executar o job de ingestão no ambiente autorizado, por agenda da distribuidora ou disparo autenticado, **separado do boot e do GitHub Actions público**. Quando indisponível, tratar ANEEL como fonte de comparação ou contingência apenas se houver autorização e identificação explícita da troca de origem; não misturar campos/recortes de bases diferentes. **Aceite:** reinício da API não dispara download nem altera dados; apenas job autorizado publica; logs e artefatos temporários respeitam a política acordada.

#### Perguntas para fechar com a distribuidora antes de implementar o conector

| Tema | Informação necessária | Consequência no desenho |
| --- | --- | --- |
| Canal e acesso | API de leitura, push/webhook, transferência de arquivo ou outro? Há homologação, autenticação e limite de requisições? | escolhe adaptador, agenda, rede e gestão de credenciais |
| Formato e cobertura | GDB/GeoPackage/CSV/Parquet/JSON? Entrega completa ou delta? Quais áreas, ativos e IDs? | define schema canônico, geoprocessamento e estratégia de snapshot |
| Fechamento da entrega | Como saber que páginas/arquivos/lotes terminaram? Há manifesto, contagens, hash e cursor? | impede substituir a base por entrega parcial |
| Temporalidade | Qual data de referência e frequência real? Há correções retroativas, exclusões e tolerância a atraso? | define ordenação, reconciliação, métricas de frescor e aviso na UI |
| Direito de uso e privacidade | Quais campos podem ser guardados, agregados, expostos, enviados à IA e por quanto tempo? | controla importação, logs, exports, cache e retenção |
| Disponibilidade | SLA, janela de manutenção, contato e política de contingência autorizada? | define retries, alertas e comportamento ao faltar nova entrega |

**Critério de passagem:** FONTE-01 é pré-requisito da escolha do adaptador. Enquanto não houver acesso/contrato da distribuidora, desenvolver o pipeline com **fixtures anonimizadas e adaptador de arquivo de teste**, sem inventar endpoint real. Não classificar snapshots cadastrais como telemetria “em tempo real”; leituras de operação em tempo real, se existirem, precisam de contrato/fluxo próprio e semântica de atualização distinta.

## 3. Ordem de implementação e entregas

As fases seguintes são **incrementais**: não transformar todo o sistema de uma vez. Cada entrega contém mudanças pequenas, testes pertinentes e nota de migração/rollback. IDs referem-se aos achados acima.

### Fase 0 — Base verificável (antes de alterar contratos)

1. Registrar arquitetura atual, fluxos de dados, dependências e portas; decidir ambiente-alvo, política de identidade e responsável pela validação técnica. Abrir FONTE-01 com a distribuidora para fechar canal, esquema, amostra, frequência e autorização.
2. Preparar dados de teste pequenos e anonimizados: 2 usuários, 3 subestações, consumidores, GD, geometrias válidas e de borda, entradas vazias/inválidas, clima simulado.
3. Capturar respostas e totais esperados das APIs, CSV/PDF e funções de cálculo; separar expectativa correta de comportamento legado incorreto.
4. Criar CI mínimo com instalação limpa, lint e testes iniciais que **reproduzam** acesso cruzado, importação com falha, `limpar_antes`, seleção de ID inexistente e unidade ambígua.

**Entrega:** suíte de regressão inicial, inventário de contratos e baseline de desempenho; contrato ou lista de pendências formais da fonte direta; nenhuma mudança matemática antes de aprovar a fórmula.

### Fase 1 — Contenção de acesso e dados inventados (P0)

1. SEC-01: identidade e autorização transversais para chat; migrar conversas legadas com política explícita de titularidade e retenção.
2. SEC-02/03: retirar `eval`, parametrizar SQL, validar configuração/secrets e reduzir superfície exposta.
3. DOM-05: desabilitar mocks automáticos em operação; propagar indisponibilidade e origem do dado até API/UI/relatório.
4. DATA-01: corrigir propagação de falhas e realizar a substituição integral somente depois da validação; a carga antiga é descartada no corte bem-sucedido.

**Portão de aceite:** teste de autorização cruzada, entrada hostil, falha de banco e falha de carga passa; não há confirmação de sucesso com dados simulados não identificados.

### Fase 2 — Atualização e operação reproduzíveis (P0/P1)

1. OPS-01/04 e FONTE-01: consolidar configurações/dependências, fechar contrato da fonte e retirar ANEEL do gatilho principal; workflow ANEEL isolado somente se for mantido para consulta.
2. FONTE-02/03 e DATA-01/02/03/05: implementar conector contratado, staging do snapshot completo, checagens de integridade, substituição integral coordenada e caches atualizados para a nova entrega.
3. FONTE-04/05 e OPS-02/03: qualidade e metadados da carga atual, job de ingestão isolado do boot, prontidão, alertas, backup e restauração verificada.
4. SEC-04: aplicar limites e validações a qualquer arquivo recebido (inclusive se vier diretamente da distribuidora); testar reconciliação de deltas se esse for o contrato.

**Portão de aceite:** fixture e, quando disponível, entrega de homologação da distribuidora passam pelo mesmo pipeline; falha antes da troca não mistura datasets; após sucesso, só existem registros da nova carga; origem/período/frescor ficam visíveis; backup restaurado em ambiente descartável confirma tabelas e amostras.

### Fase 3 — Contratos e exatidão técnica (P1)

1. DOM-01/02/03: aprovar catálogo de métricas/unidades, corrigir simulações e coordenadas, comparar curvas e somatórios contra referências técnicas.
2. DATA-04: validar topologia, IDs e CRS com tolerâncias explícitas e relatório de exceções.
3. DOM-04: separar ciclo de vida do modelo e alinhar treino, validação e inferência.
4. DOM-06/07: consolidar fluxo de relatório, corrigir schema de resposta e planejar versão de API se necessário.

**Portão de aceite:** fixtures produzem mesmos indicadores em ETL, APIs, chat, dashboard e PDF; erro de ID/dado/tempo gera estado explícito, nunca um alvo substituto.

### Fase 3B — Nova interface e corte do Streamlit (P1)

1. WEB-01/03: expor APIs tipadas e seguras para os fluxos atualmente implementados em Python; tratar autorizações antes de disponibilizá-las no navegador.
2. WEB-02: construir `frontend/` com React/TypeScript/Vite, mapa/gráficos, tabelas, exports, simulação e chat conforme o inventário; verificar acessibilidade (UX-02) em cada fatia.
3. Rodar Streamlit e nova interface em paralelo apenas durante a migração; comparar os resultados **corrigidos** e testar cada fluxo ponta a ponta.
4. Mudar o roteamento principal, observar falhas e concluir a janela de rollback; retirar processo, porta e dependências exclusivas do Streamlit após o aceite integral.

**Portão de aceite:** overview, detalhe, simulação, relatórios e chat operam no frontend novo com segurança e dados de uma única carga; Streamlit deixa de ser necessário e pode ser removido sem perda funcional.

### Fase 3C — Instalação PWA e comportamento offline (P2)

1. WEB-04: configurar manifesto, ícones e service worker para assets estáticos; definir estratégia de atualização sem interromper o uso.
2. Criar estado offline legível para as telas que precisam de API; testar que nenhuma resposta de dados autenticados ou de carga anterior está disponível como se fosse atual.
3. Verificar HTTPS, instalação, abertura pelo ícone, nova versão do frontend, publicação de nova entrega da distribuidora, recuperação da rede e logout em navegadores compatíveis.

**Portão de aceite:** interface instalável e carregável offline, APIs claramente indisponíveis sem rede, dados atualizados quando a conexão volta e nenhuma conversa/relatório persistido pelo service worker. Consulta de dados offline fica condicionada a decisão posterior (P3).

### Fase 4 — Manutenção, escala e experiência (P2/P3)

1. ENG-02/03: pacote e módulos por responsabilidade, migrações, tipagem progressiva e exceções consistentes.
2. DATA-06/ENG-04: medir gargalos e otimizar banco, memória, mapas, cache e exportações com benchmarks repetíveis.
3. SEC-05/06, OPS-05/06: limites/custos, observabilidade, documentação e endurecimento da imagem.
4. UX-01: aperfeiçoar estados e semântica das ações após migração; manter os requisitos de acessibilidade e responsividade da Fase 3B.

**Portão de aceite:** CI e smoke tests verdes, metas de latência/memória documentadas, dashboards operacionais com versão e idade do dataset, UX validada com tarefas representativas.

### Mapa de alterações por componente

| Componente atual | Intervenções previstas | Dependências para iniciar |
| --- | --- | --- |
| `src/ai/chat_service.py`, `src/ai/chat_queries.py`, `src/views/tab_chat.py` | identidade, autorização, limites, schemas e estados de erro do chat; consultas por ID e proteção do histórico | decisão sobre usuários/sessões; testes SEC-01 |
| `src/database.py`, `src/cache_redis.py`, `src/config.py` | repositórios, transações, migrações de schema, conexão/pool, configuração e cache por versão | modelos do domínio e contrato de publicação |
| `src/etl/migracao_db.py`, `src/etl/monitor_aneel.py`, `src/etl/atualizar_banco.py` | importar snapshot independentemente da origem, retirar atualização ANEEL automática, validar e substituir por completo | contrato da distribuidora e métricas mínimas de qualidade aprovados |
| Novo adaptador em `src/etl/fontes/` (caminho proposto) | aquisição autenticada conforme canal acordado, normalização, manifesto, idempotência e materialização de snapshot se vierem deltas | FONTE-01 e ambiente autorizado de homologação |
| `src/modelos/analise_mercado.py`, `src/modelos/processar_voronoi.py`, `src/utils.py` | regras únicas de agregação/vínculo, CRS, tolerâncias espaciais e validação antes de persistir | fixtures de referência e decisão de fórmula |
| `src/api.py`, `src/ai/ai_service.py`, `src/views/tab_ia.py` | contratos HTTP, datas/coordenadas, unidades e cálculo da curva | catálogo técnico e testes de conservação |
| `src/pdf_report.py`, `src/reports/`, `src/views/relatorios.py` | unificação de gerador, remoção de mocks, data do relatório e exports seguros | schema de dados validado; decisão de gerador suportado |
| `src/ai/train_model.py`, `src/ai/validate_model.py` | treino reproduzível, métricas, compatibilidade do artefato e inferência versionada | contrato de *features* aprovado |
| `run_all.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `.github/workflows/`, `scripts/`, `README.md` | separação de jobs/serviços, build/CI, backup e runbooks | definição do ambiente-alvo e serviços obrigatórios |
| `frontend/` (novo), `src/dashboard.py`, `src/views/` (a retirar) | frontend dedicado, integração HTTP, testes E2E e desativação de Streamlit | WEB-01/03, SEC-01 e contratos aprovados |
| `frontend/` (manifesto, ícones, service worker e configuração Vite) | instalação PWA, cache restrito a assets e atualização após novo build | WEB-02/03, sessões seguras e corte da nova interface |

### Procedimento para executar uma entrega

1. Abrir issue com **ID deste plano**, problema reproduzido, cenário afetado, comportamento desejado e responsável por aceitar o resultado.
2. Criar fixture e teste de regressão antes da correção; para ETL, testar falha no meio da execução e substituição integral bem-sucedida, sem coexistência de dados antigos e novos.
3. Implementar o menor corte vertical: entrada → regra → persistência → resposta/UI, quando aplicável. Evitar refatorar módulos não relacionados no mesmo PR.
4. Documentar migração de schema, configuração ou contrato HTTP; se houver consumidores antigos, prever janela de compatibilidade e remoção.
5. Rodar testes locais e no CI; anexar exemplos de saída, contagens ou medições relevantes. Validar cancelamento antes do corte e recuperação de falha em mudanças de banco/ETL.
6. Publicar primeiro em ambiente de ensaio com dados representativos; promover apenas após conferir critérios de aceite e identificador da carga/modelo atual.

**Dependências críticas:** SEC-01 antecede exposição do chat; FONTE-01 antecede integração real; DATA-01/FONTE-03 antecedem publicação automática de qualquer fonte; SEC-04 antecede ingestão de arquivos; DOM-01/02 antecedem mudança dos alertas operacionais; OPS-03 antecede substituição de dados em operação; WEB-01/03 antecedem ativação do frontend novo; WEB-04 sucede estabilização de sessões/rotas e troca de carga. ENG-01 deve começar na Fase 0 e evoluir junto com cada entrega.

## 4. Matriz mínima de testes e verificações

| Camada | Casos obrigatórios | Evidência de aceite |
| --- | --- | --- |
| Autorização | dois usuários, IDs conhecidos, leitura/escrita/listagem/feedback | resposta de negação e ausência de vazamento |
| Contrato HTTP | datas inválidas, nomes duplicados, payload sem campos, unidades fora do intervalo | status e schema previsíveis; sem erro interno exposto |
| Banco/ETL | entrega ausente, camada/tabela vazia, falha na 3ª camada, repetição da mesma carga, cache com registros inválidos, IDs exclusivos de cada carga | falha não publica conjunto incompleto; sucesso remove todos os registros anteriores e preserva apenas os novos |
| Fonte direta | entrega completa/incompleta, duplicada, fora de ordem, sem autenticação, páginas ausentes, hash inválido, delta com exclusão e fonte indisponível | só snapshot completo válido é publicado; idempotência, proveniência e alerta de atraso verificados |
| Geoespacial | CRS divergente, polígono inválido, pontos dentro/fora/na borda, ID ausente | relatório de cobertura/vínculo e regra determinística |
| Domínio | limites exatos das faixas, zero, classe desconhecida, conversão kWh↔MWh e kW↔MW | cálculos coincidentes entre canais e aprovados pelo responsável técnico |
| Simulação | clima real/estimado/indisponível, subestação sem ponto, 24 horas, energia mensal | origem explícita e identidades matemáticas preservadas |
| IA | modelo ausente, versão incompatível, ferramenta inválida, provedor lento/429, custo máximo | fallback/erro correto sem perder integridade nem expor detalhes |
| Relatórios | ID inexistente, data selecionada, classe sem GD, CSV hostil, cache vazio | nenhuma substituição silenciosa ou valor inventado |
| Operação | instalação limpa, Compose, SIGTERM, health/readiness, backup+restore | ambiente sobe/para corretamente e recuperação demonstrada |
| Performance | dataset de referência, p50/p95, consumo de memória, tamanho de resposta, custo de ETL | comparação baseline vs. resultado com tolerância definida |
| Nova interface | rotas diretas, mapa/gráficos, downloads, simulação, chat, teclado, celular e autenticação | fluxos E2E aprovados e nenhum processo Streamlit necessário após corte |
| PWA | instalar/abrir, ficar offline, voltar online, atualizar frontend, substituir entrega da distribuidora A por B e sair da sessão | shell disponível offline, APIs sem cache persistente, dados B mostrados após reconexão e nenhum dado privado local |

**Ferramentas sugeridas, a confirmar com a equipe:** `pytest` e fixtures; `ruff` para estilo/lint; verificador de tipos progressivo (mypy ou pyright); testes integrados com PostgreSQL/PostGIS e Redis isolados; checagem de dependências e de segredos em CI. Não fixar meta arbitrária de cobertura: acompanhar **riscos cobertos**, flakiness e regressões críticas. Lint, tipagem e testes precisam rodar em PR; integração pesada pode ter estágio próprio, desde que mudanças no ETL sejam bloqueadas por ele.

## 5. Padrões de implementação e definição de pronto

Para **cada** item entregue:

1. Descrever mudança, impacto no contrato, migração de dados/configuração e plano de reversão no PR.
2. Adicionar teste que exercite comportamento externo ou regra de domínio; evitar testes que apenas reproduzam linhas de implementação.
3. Validar dados de entrada na fronteira; valores inesperados geram falha tipada. Evitar `except:`/`except Exception` sem contexto, propagação ou política explícita de fallback.
4. Manter configurações em fonte única e segredos fora do código/logs; falhar cedo quando requisito obrigatório faltar.
5. Alteração de cálculo exige fórmula, unidade, fonte e revisão técnica; alteração de schema exige teste de contrato e estratégia de compatibilidade.
6. Mudança em ETL exige substituição integral sem mescla, contagens/qualidade, publicação verificável e tratamento de falha testado; mudança em cache exige invalidação documentada.
7. Executar lint, testes afetados, integração pertinente e smoke test de fluxo principal. Registrar limitações conhecidas e métricas antes/depois se houver otimização.

**Sequência sugerida de primeiras entregas pequenas:**

1. Testes de acesso cruzado + correção da autorização do chat (`SEC-01`).
2. Remoção de `eval()` e parametrização das consultas (`SEC-02`).
3. Desativação de mocks automáticos e estados de origem (`DOM-05`).
4. Migração que falha de forma segura; depois staging temporário e substituição integral verificada (`DATA-01`).
5. Contrato com a distribuidora, adaptador para o canal confirmado e metadados da carga substituta (`FONTE-01/02/03`, `DATA-02`).
6. Configuração/dependências reproduzíveis e backup restaurável (`OPS-01/03/04`).
7. Catálogo de fórmulas/unidades aprovado e harmonização das saídas (`DOM-01/02`).
8. Primeiras rotas do frontend dedicado, começando por Visão Geral e detalhe (`WEB-01/02/03`).

## 6. Limitações desta auditoria

A análise cobriu arquivos rastreados e fluxos relevantes por leitura estática. **Não** houve execução de Docker, acesso ao banco/serviços externos ou à distribuidora, revisão de dados reais, auditoria de dependências por CVE, benchmark, teste em navegador/dispositivo nem validação científica das fórmulas. Canal, formato, autorização e frequência de entrega da distribuidora **ainda não foram confirmados**; por isso não se pode garantir atualização em tempo real nem implementar o conector definitivo sem o contrato FONTE-01. Metas numéricas de desempenho, classificação elétrica definitiva, estimativas de esforço e decisão de autenticação devem ser fechadas com o ambiente e o responsável apropriados. Itens não citados nominalmente ainda podem surgir nos testes integrados; registrar novos achados com o mesmo formato (evidência, impacto, aceite e prioridade).
