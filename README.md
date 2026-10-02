# GridScope Core

**GridScope Core** é uma plataforma avançada de monitoramento de redes elétricas e simulação de geração distribuída.

### Aquisição pelo catálogo ANEEL

O monitor consulta qualquer distribuidora sem alterar a publicação por padrão:

```bash
python -m src.etl.monitor_aneel --distribuidora "Light"
```

Para baixar e preservar o GDB em `dados/`:

```bash
python -m src.etl.monitor_aneel --distribuidora "Light" --baixar
```

Para baixar, validar os derivados e substituir atomicamente a publicação vigente:

```bash
python -m src.etl.monitor_aneel --distribuidora "Light" --publicar
```

Use `--publicar` conscientemente: o GridScope mantém uma publicação operacional por banco.

#### Compatibilidade BDGD

O importador normaliza as entregas para um contrato interno único e valida antes
do corte transacional:

- camadas `SUB`, `UNTRMT`, `UCBT_tab` (ou `UCBT`), `UGBT_tab` (ou `UGBT`) e `SSDMT`;
- chaves, colunas mensais, geometrias, CRS e referências entre as camadas;
- código IBGE `MUN` nos transformadores;
- SIRGAS 2000 / UTM selecionada automaticamente para concessões compactas;
- SIRGAS 2000 / Brazil Polyconic para concessões que atravessam zonas UTM.

Uma incompatibilidade cancela o staging e preserva integralmente a publicação
anterior. O banco mantém uma publicação ativa; publicar outra distribuidora
substitui atomicamente a vigente.

Quando a cobertura municipal bloquear uma entrega, o diagnóstico persistido
fica em `dados/diagnosticos/<delivery_id>/<tentativa>/`. Para investigá-la sem
carregar consumidores nem publicar dados:

```bash
python -m src.etl.diagnosticar_geografia --gdb "dados/Light-<id>.gdb" --saida "dados/diagnosticos/light"
```

O comando grava `resumo.json`, `transformadores_fora.csv` e, quando aplicável,
`transformadores_fora.geojson`. O código de saída `2` indica pontos além da
tolerância de qualidade de 250 m; a tolerância nunca expande a malha publicada.

Para comparar as ocorrências preservadas com uma malha oficial candidata local,
sem mudar a publicação ou o cache operacional:

```powershell
python -m src.etl.comparar_cobertura `
  --ocorrencias "<tentativa>/preflight/transformadores_fora.csv" `
  --manifesto-atual "<tentativa>/malhas.json" `
  --malha-candidata "<malha-oficial-candidata>.gpkg" `
  --coluna-codigo "<campo-IBGE>" `
  --saida "dados/diagnosticos/light/comparacao"
```

Opcionalmente, `--referencia-ampla` e `--coluna-codigo-referencia` classificam
os pontos por município espacial, inclusive municípios não selecionados. As
opções `--malha-candidata-ibge-uf` e `--referencia-ibge-uf` baixam a malha
municipal máxima estadual do IBGE direto na comparação. A comparação é somente
diagnóstica: não altera a malha operacional nem amplia o território publicado.

### Escopo da malha de validação

Duas malhas distintas participam da publicação, e elas não podem ser confundidas:

| Uso | Escopo | Configuração |
| --- | --- | --- |
| Malha de **validação** (bloqueia a publicação) | Todos os municípios da(s) UF(s) presentes em `MUN` | Fixo |
| Malha de **publicação** (recorte do Voronoi e tabela `limites_municipais`) | Somente os municípios declarados em `MUN` | fixo por desenho |

O motivo: `MUN` é um atributo declarado pelo distribuidor e não é fonte confiável
de território. Na entrega Light auditada (`f5a569a8…`), **1.307 das 99.490
sementes (1,31%)** com `MUN` válido caem espacialmente em outro município do
próprio estado — por exemplo, 486 ativos da subestação `18520902` declarados em
Queimados (`3302858`) estão dentro de Nilópolis (`3303203`). Se a malha de
validação fosse montada apenas a partir de `MUN`, esse erro de atribuição
apareceria como erro de coordenada e bloquearia a entrega sem evidência real.

A validação julga a coordenada contra a
divisão municipal oficial do estado — uma referência que não depende do atributo
auditado. O resultado é que erro de atribuição deixa de bloquear, e a detecção
de coordenadas fora da área de operação continua válida: dos 1.161 bloqueios da
entrega Light, 1.054 (90,8%) eram falso positivo de atribuição e 107 são pontos
fisicamente fora do RJ (96 em MG, 10 em SP), de 251 m a 5.023 m da fronteira.

### Quarentena auditada de outliers

Alguns pontos não são corrigíveis por malha: o `MUN` declara um município do
estado, mas a coordenada cai fisicamente em município de outra UF. Não existe
malha oficial que conserte a coordenada, e a malha publicada nunca é ampliada
para acomodá-los. A quarentena exclui esses registros da carga **de forma
explícita e auditável**, em vez de bloquear a entrega inteira.

É delimitada por quatro regras:

1. Só se aplica a sementes cuja única pendência é posição geográfica
   (`outside_above_tolerance`). Geometria inválida, coordenada não finita,
   identificador ou município ausentes continuam bloqueando.
2. Nunca remove uma fração relevante da base: acima de
   `GRIDSCOPE_QUARENTENA_FRACAO_MAXIMA` (0,5% por padrão) a publicação é
   bloqueada, porque esse volume indica falha sistêmica da entrega, não
   outliers isolados.
3. Exige `transformador_id` identificável em todas as linhas excluídas.
4. Grava `quarentena.csv` no diretório de diagnóstico com cada registro
   excluído e seu motivo, e registra cada identificador removido em
   `quality_report.discarded_records` da publicação, que é o registro
   auditável do que ficou de fora. Registros de `UCBT_tab`/`UGBT_tab` ligados
   aos transformadores excluídos são descartados na mesma cascata usada pelas
   demais exclusões.

O console mostra apenas um resumo: a proveniência completa das malhas e a lista
de identificadores ficam no arquivo de metadados e no diagnóstico, não no log.

Na entrega Light auditada isso afetou 107 sementes de 99.490 (0,108%), em 8
subestações de fronteira, das quais 96 caem em MG e 10 em SP. A publicação
ficou com 99.383 transformadores e os 30 municípios declarados na malha.

O sistema utiliza uma arquitetura moderna orientada a serviços para processar dados geoespaciais e fornecer insights em tempo real.

---

## 🚀 Funcionalidades

- **API RESTful (FastAPI)**  
  Endpoints otimizados para consulta do status da rede com **Cache L1 (Redis)**.

- **Frontend responsivo (React + Vite + PWA)**
  Visualização operacional da rede, análise de mercado e acesso aos serviços da API.

- **Processamento Geoespacial (PostGIS)**  
  Cálculo de territórios Voronoi e junções espaciais realizadas diretamente no banco de dados.

- **Simulação Solar com IA**  
  Estimativa de geração fotovoltaica baseada em dados climáticos reais (Open-Meteo) e perfis de consumo reais.

---

## 🛠️ Arquitetura Técnica

O sistema foi migrado para uma arquitetura robusta baseada em banco de dados:

- **Database:** PostgreSQL 15 + PostGIS (Armazenamento Centralizado)
- **Cache:** Redis 7 (Aceleração de API - Respostas em <50ms)
- **Backend:** Python 3.10+, FastAPI
- **Frontend:** React, TypeScript, Vite e PWA
- **Infraestrutura:** Docker Compose

---

## ⚙️ Instalação (Docker - Recomendado)

A forma padrão de execução é via Docker, que sobe automaticamente o Banco, Redis, API e frontend.

### 1. Configuração

Clone o repositório e configure o `.env`:

```bash
git clone <url-do-repositorio>
cd gridScope-core
# Crie o arquivo .env baseado no .env.example
# Defina POSTGRES_PASSWORD e repita a mesma credencial nas URLs DATABASE_URL
# e DATABASE_URL_DOCKER; faça percent-encoding dos caracteres reservados da URL.
# DATABASE_URL usa localhost; DATABASE_URL_DOCKER usa o serviço interno "db".
```

### 2. Execução

```bash
docker compose up --build
```

O Compose padrão não monta o repositório nem o `.env` dentro do contêiner e
executa a API com usuário não-root. Para desenvolvimento com hot reload/código
montado, use o override explícito:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### 3. Acessos

- **Frontend:** [http://localhost:3000](http://localhost:3000)
- **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

As portas do PostgreSQL e do Redis ficam vinculadas somente a `127.0.0.1`.
Para alterar as portas locais, use `POSTGRES_HOST_PORT` e
`REDIS_HOST_PORT` no `.env`; a comunicação entre os serviços usa a rede
interna do Compose.

---

## 🔐 Autenticação e usuários

O acesso à plataforma é autenticado por sessão de servidor. Não existe cadastro
público: usuários são criados somente por um administrador autenticado, e o
primeiro administrador é provisionado explicitamente:

```bash
docker compose run --rm gridscope \
  python -m src.auth.bootstrap_admin \
  --email admin@gridscope.local \
  --name "Administrador GridScope"
```

As senhas são armazenadas com `scrypt`, usuários e sessões usam UUID, operações
de escrita exigem CSRF e login, chat e administração possuem limites Redis
configuráveis no `.env.example`. O comando de bootstrap não cria outro
administrador quando já existe um administrador ativo.

---

## � Ferramentas de Manutenção

O projeto inclui scripts utilitários para gerenciamento do banco de dados:

- `python scripts/backup_db.py`: Gera backup completo do banco PostgreSQL
  (salva em `backups/`).
- `python scripts/restore_db.py backups/arquivo.sql --database gridscope_restore_e2e --confirm`:
  Restaura um dump em um banco-alvo explícito; use somente em banco descartável
  ou de homologação e confirme explicitamente a sobrescrita.
- `python scripts/criar_indices.py`: Recria índices de performance nas tabelas
  do banco.
- `python -m src.etl.pipeline`: Publica um snapshot completo (bruto, Voronoi,
  mercado e metadados transacionais) a partir da fonte configurada em
  `DATA_SOURCE`, que aceita `local_file` ou `distributor_http`.
- `python -m src.etl.atualizar_banco --only-cache`: Regenera apenas o cache de
  mercado a partir do banco já publicado.
- `python -m unittest discover -s tests -v`: Executa a suíte de regressão.

---

## 📂 Estrutura do Projeto

```text
gridScope-core/
├── frontend/              # Aplicação React/Vite/PWA
├── src/
│   ├── api.py            # API com Cache Redis
│   ├── database.py       # Camada de Acesso a Dados (PostgreSQL)
│   ├── cache_redis.py    # Módulo de Cache L1
│   ├── etl/              # Scripts de Carga e Migração
│   └── modelos/          # Regras de Negócio (Voronoi, Mercado)
│
├── dados/                # (Obsoleto - Dados migrados para o Banco)
├── docker-compose.yml    # Orquestração (API, frontend, DB, Redis)
├── requirements.txt
└── README.md
```

---

**Responsável Técnico:** Guilherme Araújo
**Atualizado em:** Janeiro/2026
