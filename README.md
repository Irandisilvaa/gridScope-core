# GridScope Core

**GridScope Core** é uma plataforma avançada de monitoramento de redes elétricas e simulação de geração distribuída.
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

## � Ferramentas de Manutenção

O projeto inclui scripts utilitários para gerenciamento do banco de dados:

- `python scripts/backup_db.py`: Gera backup completo do banco PostgreSQL
  (salva em `backups/`).
- `python scripts/criar_indices.py`: Recria índices de performance nas tabelas
  do banco.
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
