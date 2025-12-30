# GridScope Core

**GridScope Core** é uma API avançada e um Dashboard interativo para monitoramento de redes elétricas e simulação de geração distribuída.  
O sistema integra dados geográficos, métricas de rede e dados climáticos para fornecer insights em tempo real sobre a infraestrutura elétrica.

---

## 🚀 Funcionalidades

- **API RESTful (FastAPI)**  
  Endpoints para consulta do status da rede, ranking de subestações e simulação de geração solar.

- **Dashboard Interativo (Streamlit)**  
  Visualização de dados em mapas (Folium), gráficos de consumo e métricas de Geração Distribuída (GD).

- **Processamento Geoespacial**  
  Geração automática de territórios de atuação de subestações utilizando Diagramas de Voronoi.

- **Simulação Solar**  
  Estimativa de geração fotovoltaica baseada em dados climáticos reais e previstos (via Open-Meteo API).

---

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python, FastAPI, Uvicorn  
- **Frontend/Dashboard:** Streamlit, Plotly, Folium  
- **Geoprocessamento:** GeoPandas, Shapely, OSMnx, SciPy (Voronoi)  
- **Infraestrutura:** Docker, Docker Compose  
- **Dados Externos:** Open-Meteo (Clima)

---

## ⚙️ Configuração Inicial (Obrigatória)

Antes de rodar o projeto (via Docker ou manualmente), é necessário configurar as variáveis de ambiente.

### 1️⃣ Clone o repositório

```bash
git clone <url-do-repositorio>
cd gridScope-core
````

### 2️⃣ Crie o arquivo `.env`

Na raiz do projeto, crie um arquivo `.env` baseado no `.env.example`:

```env
# Arquivos de dados (caminhos relativos ou absolutos)
FILE_GDB="Energisa_SE_6587_2023-12-31_V11_20250701-0833.gdb"
FILE_GEOJSON="subestacoes_logicas_aracaju.geojson"
FILE_MERCADO="perfil_mercado_aracaju.json"

# Configuração da cidade alvo para o Voronoi
CIDADE_ALVO="Aracaju, Sergipe, Brazil"
```

### 3️⃣ Dados de entrada

Certifique-se de que o arquivo `.gdb` esteja dentro da pasta `dados/` na raiz do projeto.

---

## ▶️ Como Executar

Escolha uma das opções abaixo para rodar o sistema.

---

## 🐳 Opção 1: Executar com Docker (Recomendado)

A forma mais simples de executar o projeto, sem necessidade de configurar Python ou bibliotecas geoespaciais localmente.

### Pré-requisitos

* Docker
* Docker Compose

### Executar

```bash
docker-compose up --build
```

> Para rodar em segundo plano:

```bash
docker-compose up -d --build
```

### Acessos

* **Dashboard:** [http://localhost:8501](http://localhost:8501)
* **API (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

### Parar os serviços

```bash
docker-compose down
```

---

## 🐍 Opção 2: Execução Manual (Python Local)

Indicada para desenvolvimento, testes e depuração.

### 1️⃣ Criar e ativar ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

### 2️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

### 3️⃣ Executar o sistema

```bash
python run_all.py
```

O script irá automaticamente:

* Gerar os territórios de Voronoi
* Processar a análise de mercado
* Iniciar a API
* Abrir o Dashboard no navegador

---

## 📂 Estrutura do Projeto

```text
gridScope-core/
├── src/
│   ├── api.py            # Aplicação FastAPI
│   ├── dashboard.py      # Dashboard Streamlit
│   ├── config.py         # Configurações e variáveis de ambiente
│   ├── utils.py          # Funções utilitárias
│   └── modelos/          # Lógica de Voronoi e Análise de Mercado
│
├── dados/                # Arquivos GDB e dados de entrada
├── logs/                 # Logs de execução
├── run_all.py            # Orquestrador do sistema
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

Desenvolvido como parte do projeto **GridScope** ⚡
