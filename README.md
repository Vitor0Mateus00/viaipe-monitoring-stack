# ViaIpe Monitoring System

## Visão Geral

Sistema de monitoramento containerizado da rede acadêmica brasileira ViaIpe/RNP que coleta, processa e visualiza métricas de disponibilidade, qualidade e consumo de banda de 264+ instituições conectadas. O sistema consome dados da API oficial do ViaIpe, processa indicadores de performance em tempo real e armazena em banco de dados otimizado para séries temporais, fornecendo dashboards operacionais através do Grafana.

## High Level Design

### Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VIAIPE MONITORING SYSTEM                     │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐ │
│  │    FastAPI      │    │   PostgreSQL +   │    │     Grafana     │ │
│  │ Data Collector  │◄───┤   TimescaleDB    │◄───┤   Dashboards    │ │
│  │                 │    │                  │    │                 │ │
│  │   Port: 8000    │    │   Port: 5432     │    │   Port: 3000    │ │
│  └─────────────────┘    └──────────────────┘    └─────────────────┘ │
│         │                         │                        │        │
│         ▼                         ▼                        ▼        │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐ │
│  │   Background    │    │   Hypertables    │    │  Dashboards:    │ │
│  │     Tasks       │    │   Time Series    │    │ • Main Monitor  │ │
│  │   Scheduler     │    │   Optimization   │    │ • Regional      │ │
│  └─────────────────┘    └──────────────────┘    └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │    VIAIPE API RNP      │
                    │                        │
                    │ https://viaipe.rnp.br  │
                    │      /api/norte        │
                    │                        │
                    │ • 264+ Instituições    │
                    │ • Dados em Tempo Real  │
                    │ • Métricas Completas   │
                    └─────────────────────────┘
```

### Componentes

| Componente | Tecnologia | Porta | Função |
|------------|------------|-------|---------|
| FastAPI Data Collector | Python 3.11 + FastAPI | 8000 | Coleta, processamento e orquestração |
| PostgreSQL + TimescaleDB | PostgreSQL 15 + TimescaleDB | 5432 | Armazenamento otimizado para séries temporais |
| Grafana | Grafana Latest | 3000 | Dashboards e visualização operacional |

### Fluxo de Dados

```
ViaIpe API → FastAPI Collector → PostgreSQL/TimescaleDB → Grafana Dashboards
     ↓              ↓                      ↓                    ↓
• 264 Inst.    • Parsing         • Hypertables        • Main Dashboard
• Real-time    • Calculations    • Time Optimization  • Regional Analysis  
• JSON Data    • Validation      • Views & Indexes    • Geographic Map
```

1. **FastAPI** consome API ViaIpe a cada execução manual ou automática
2. **Data Processing** calcula disponibilidade, utilização de banda e qualidade
3. **PostgreSQL + TimescaleDB** armazena dados em hypertables otimizadas
4. **Views Agregadas** fornecem estatísticas regionais e por instituição
5. **Grafana** consulta PostgreSQL para dashboards em tempo real

### Métricas Coletadas

**Por Instituição (264+ entidades)**
- **Disponibilidade**: Percentual baseado em perda de pacotes (100 - smoke.loss)
- **Latência**: Tempo de resposta em milissegundos (smoke.val)
- **Throughput**: Tráfego de entrada/saída em bytes/segundo
- **Utilização de Banda**: Percentual de uso da capacidade máxima
- **Localização**: Coordenadas geográficas (latitude/longitude)
- **Classificação Regional**: Estado e região do Brasil

**Métricas Calculadas**
- **Disponibilidade Nacional**: Média ponderada de todas instituições
- **Ranking Regional**: Comparativo por estado e região
- **Instituições Problemáticas**: Entidades com disponibilidade < 95%
- **Tendências Temporais**: Evolução histórica das métricas

### Modelo de Dados

```sql
-- Instituições da rede acadêmica
CREATE TABLE institutions (
    id VARCHAR(255) PRIMARY KEY,              -- ID único da instituição
    name VARCHAR(500) NOT NULL,               -- Nome da instituição
    latitude DECIMAL(10, 7) NOT NULL,         -- Coordenada geográfica
    longitude DECIMAL(10, 7) NOT NULL,        -- Coordenada geográfica
    region VARCHAR(50),                       -- Região do Brasil
    state VARCHAR(2)                          -- Estado (UF)
);

-- Métricas temporais (Hypertable TimescaleDB)
CREATE TABLE traffic_metrics (
    time TIMESTAMP WITH TIME ZONE NOT NULL,                    -- Timestamp da coleta
    institution_id VARCHAR(255) NOT NULL,                      -- FK para institutions
    traffic_in DECIMAL(15, 2) DEFAULT 0,                      -- Tráfego entrada (bytes/s)
    traffic_out DECIMAL(15, 2) DEFAULT 0,                     -- Tráfego saída (bytes/s)
    latency_ms DECIMAL(10, 2),                                -- Latência (ms)
    packet_loss_percent DECIMAL(5, 2) DEFAULT 0,              -- Perda de pacotes (%)
    availability_percent DECIMAL(5, 2) DEFAULT 100,           -- Disponibilidade (%)
    bandwidth_utilization_in_percent DECIMAL(5, 2) DEFAULT 0, -- Utilização entrada (%)
    bandwidth_utilization_out_percent DECIMAL(5, 2) DEFAULT 0,-- Utilização saída (%)
    PRIMARY KEY (time, institution_id)
);

-- Views para dashboards
CREATE VIEW v_institution_current_status AS ...;  -- Status atual por instituição
CREATE VIEW v_regional_statistics AS ...;         -- Estatísticas regionais
```

### Containerização

O sistema utiliza Docker Compose com 3 containers dedicados:

- **viaipe_postgres**: PostgreSQL 15 + TimescaleDB para séries temporais
- **viaipe_api**: FastAPI collector (build customizado Python 3.11)
- **viaipe_grafana**: Interface de dashboards e visualização

**Comunicação**: Rede bridge "viaipe_network" com DNS interno entre containers.
**Persistência**: Volumes Docker para dados PostgreSQL e configurações Grafana.
**Health Checks**: Monitoramento automático da saúde dos serviços.

## APIs Disponíveis

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Status da aplicação e informações básicas |
| `/health` | GET | Health check com timestamp |
| `/collect-data` | POST | Executa coleta manual do ViaIpe |
| `/institutions` | GET | Lista todas as instituições cadastradas |
| `/availability-stats` | GET | Estatísticas de disponibilidade (últimas 24h) |
| `/debug/counts` | GET | Contadores para debug (instituições, métricas) |

## Estrutura do Projeto

```
viaipe-monitoring/
├── docker-compose.yml                    # Orquestração dos containers
├── Dockerfile                           # Build da aplicação FastAPI
├── requirements.txt                     # Dependências Python
├── README.md                           # Documentação completa
├── api/
│   └── v1/
│       ├── main.py                     # Aplicação FastAPI principal
│       └── models.py                   # Modelos Pydantic
├── database/
│   └── init.sql                        # Schema + views + hypertables
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── datasources.yml         # Datasource PostgreSQL automático
    │   └── dashboards/
    │       └── dashboards.yml          # Provider de dashboards
    └── dashboards/
        ├── viaipe_main.json            # Dashboard principal
        └── viaipe_regional.json        # Dashboard análise regional
```

## Como Executar

### Pré-requisitos

- Docker e Docker Compose instalados
- Portas 3000, 5432, 8000 disponíveis
- Conexão com internet para acesso à API ViaIpe

### Execução

```bash
# Clonar o repositório
git clone <repository-url>
cd viaipe-monitoring

# Subir todos os containers
docker-compose up -d

# Verificar status dos containers
docker-compose ps

# Aguardar inicialização (30-60 segundos)
sleep 60

# Executar primeira coleta de dados
curl -X POST http://localhost:8000/collect-data

# Verificar se dados foram coletados
curl http://localhost:8000/debug/counts
```

### Acesso às Interfaces

- **Grafana**: http://localhost:3000 (admin/admin)
  - Dashboard Principal: ViaIpe - Monitoramento Geral
  - Dashboard Regional: ViaIpe - Análise Regional
- **API FastAPI**: http://localhost:8000
  - Documentação automática: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (viaipe_user/viaipe_pass)

### Verificação do Sistema

```bash
# Testar API principal
curl http://localhost:8000/health

# Verificar instituições coletadas
curl http://localhost:8000/institutions

# Verificar estatísticas de disponibilidade
curl http://localhost:8000/availability-stats

# Executar nova coleta manual
curl -X POST http://localhost:8000/collect-data

# Verificar contadores para debug
curl http://localhost:8000/debug/counts
```

### Logs e Troubleshooting

```bash
# Ver logs de todos os containers
docker-compose logs

# Ver logs de containers específicos
docker-compose logs viaipe_api
docker-compose logs viaipe_postgres
docker-compose logs viaipe_grafana

# Verificar dados no banco diretamente
docker-compose exec postgres psql -U viaipe_user -d viaipe_monitoring

# Consultas úteis para debug
docker-compose exec postgres psql -U viaipe_user -d viaipe_monitoring -c "SELECT COUNT(*) FROM institutions;"
docker-compose exec postgres psql -U viaipe_user -d viaipe_monitoring -c "SELECT COUNT(*) FROM traffic_metrics;"

# Parar todos os containers
docker-compose down

# Reset completo (remove volumes)
docker-compose down -v
docker volume prune
```

## Dashboards

O Grafana é configurado automaticamente com:

### Datasource
- **PostgreSQL** pré-configurado apontando para TimescaleDB
- **Conexão automática** via Docker network
- **TimescaleDB features** habilitadas para queries otimizadas

### Dashboards Provisionados

#### 1. ViaIpe - Monitoramento Geral
- **Status das Instituições**: Tabela ordenada por disponibilidade
- **Distribuição de Status**: Pie chart com categorização (Excelente/Bom/Regular/Ruim)
- **Evolução da Disponibilidade**: Time series das últimas 24 horas
- **KPIs Principais**: Total de instituições, disponibilidade geral, latência média
- **Instituições com Problemas**: Contador de entidades com disponibilidade < 95%
- **Consumo de Banda**: Evolução do tráfego médio de entrada/saída

#### 2. ViaIpe - Análise Regional
- **Estatísticas por Região**: Tabela comparativa com gauge de disponibilidade
- **Distribuição Geográfica**: Pie chart de instituições por região
- **Evolução Regional**: Time series de disponibilidade por região (12h)
- **Mapa Interativo**: Geomap do Brasil com status visual das instituições
- **Detalhamento por Problemas**: Tabela focada em instituições com baixa performance
- **Latência Regional**: Evolução da latência média por região

### Funcionalidades dos Dashboards
- **Auto-refresh**: Atualização automática a cada 30 segundos (main) / 1 minuto (regional)
- **Time range picker**: Seleção flexível de períodos de análise
- **Drill-down**: Navegação entre visões gerais e detalhadas
- **Responsive design**: Compatível com desktop e mobile
- **Export capabilities**: PDF, PNG, CSV dos dados

## Performance e Escalabilidade

### Otimizações Implementadas
- **TimescaleDB hypertables**: Particionamento automático por tempo
- **Índices estratégicos**: Otimização para queries temporais e por instituição
- **Views materializadas**: Cache de agregações complexas
- **Transações individuais**: Resiliência na coleta de dados
- **Background processing**: Coleta assíncrona sem bloqueio

### Monitoramento Interno
- **Health checks**: Verificação automática da saúde dos containers
- **API metrics**: Contadores de sucesso/erro na coleta
- **Database monitoring**: Métricas de performance do PostgreSQL
- **Log aggregation**: Centralização de logs para troubleshooting

Os dashboards são provisionados automaticamente na inicialização do sistema e começam a exibir dados assim que a primeira coleta é executada, geralmente dentro de 1-2 minutos após o startup completo.
