# Plataforma de Prescrição Agroclimática e Demarcação Geoespacial
## Agricultura Familiar de Roraima (Bioma Amazônia & Lavrado)
### NASA Space Apps Challenge 2026

Plataforma unificada para planejamento sincronizado de rotação de culturas, sensoriamento remoto de cobertura do solo e regularização de imóveis rurais da agricultura familiar em Roraima, integrando dados orbitais da **NASA** e da **ESA** com a **Matriz de Passaporte Biológico da Embrapa Roraima**.

---

## 🛰️ 1. Satélites e Sensores Integrados

| Sensor / Missão | Agência | Resolução | Parâmetros Monitorados | Aplicação no Motor Agronômico |
| :--- | :---: | :---: | :--- | :--- |
| **NASA POWER v2.0 (AG)** | NASA | Grade 0.5° | `PRECTOTCORR`, `T2M`, `ALLSKY_SFC_SW_DWN`, `RH2M` | Histórico climatológico de 30 anos e monitoramento diário para corte de chuvas. |
| **NASA SMAP** | NASA | 9 km / L4 | `GWETROOT` (0-100 cm), `GWETTOP` (0-5 cm) | Umidade do solo na zona radicular e emergência de sementes / manivas. |
| **ESA Sentinel-2 (MSI)** | ESA / CDSE | 10 metros | Bandas B04 (Vermelho) e B08 (NIR) | Cálculo de NDVI, % de biomassa ativa, palhada residual e risco de solo exposto. |
| **NASA SRTM** | NASA | 30 metros | Modelo Digital de Elevação (DEM) | Risco de erosão por declividade (veto para mandioca se > 8% no Lavrado). |

---

## 🌾 2. Engrenagens Agronômicas da Embrapa Roraima

A plataforma sincroniza as culturas anuais com o regime pluviométrico unimodal de Roraima (chuvas de abril a setembro; seca severa de outubro a março):

1. **1ª Fase - Safra Chuvosa Principal (Maio a Agosto):**
   * **Milho (*Zea mays* - BRS 1030 / BRS 1055):** Semeadura após o início real das chuvas confirmado por GPM. Ciclo de ~110 dias para maturação antes do corte das chuvas. Produz palhada massiva de alta relação C/N (> 60) para plantio direto.
2. **2ª Fase - Safrinha / Sucessão Imediata (Agosto a Outubro):**
   * **Feijão-Caupi (*Vigna unguiculata* - BRS Novaera / BRS Tumucumaque):** Plantio direto na palhada do milho. Ciclo de 65–70 dias. Aproveita a umidade residual do solo (SMAP GWETROOT) e fixa nitrogênio atmosférico (FBN).
3. **3ª Fase - Safra Rústica / Ciclo Longo (Maio a Outubro do Ano 2):**
   * **Mandioca (*Manihot esculenta* - Aciolina / Platinão):** Alta tolerância a secas prolongadas (até 6 meses). O arranquio das raízes revolve o solo, exigindo retorno imediato com milho/gramínea para recompor a estrutura física.

---

## 🔄 3. Pipeline Integrado: Da Pesquisa Científica à Decisão

1. **Extração Científica via NLP (`gerador_passaporte_agronomico.py`):**
   * Processa os Comunicados Técnicos e Boletins de Pesquisa da Embrapa Roraima (`*.pdf`).
   * Gera a matriz descritiva de conhecimento agroecológico (`matriz_passaporte_biologico.csv`).
2. **Parametrização & Motor de Decisão (`rotation_planner.py` & `passaporte_biologico.py`):**
   * Transforma as recomendações em regras operacionais (`matriz_passaporte_parametrizada.csv`).
   * Cruza as exigências hídricas, térmicas e de relevo com as leituras orbitais da NASA e ESA.
3. **Módulo Geoespacial & PostGIS (`land_demarcation.py` & `supabase_schema.sql`):**
   * Recupera perímetros do CAR, calcula centroides, calcula áreas em $m^2$ e hectares, e isola Reserva Legal e Área Consolidada.
4. **Dashboard de Prescrição (`index.html` & `server.py`):**
   * Interface Leaflet interativa com Google Satellite Hybrid, ESA Sentinel-2 Cloudless e diagnóstico agronômico detalhado.

---

## 🏛️ 4. Estrutura do Repositório

```
├── .env.example                       # Modelo para credenciais do Copernicus CDSE
├── .gitignore                         # Bloqueio de credenciais, caches e dados binários pesados
├── README.md                          # Documentação técnica e guia da solução
│
├── 🌾 Pesquisa & Inteligência Agronômica
│   ├── *.pdf                          # Literatura e Boletins Técnicos da Embrapa Roraima
│   ├── gerador_passaporte_agronomico.py # Extrator NLP de regras da literatura científica
│   ├── matriz_passaporte_biologico.csv  # Matriz textual extraída da pesquisa
│   ├── matriz_passaporte_parametrizada.csv # Matriz quantitativa calibrada para o motor
│   ├── passaporte_biologico.py        # Dicionário agronômico tipado (Dataclasses)
│   ├── crops_profile.py               # Perfis botânicos complementares
│   └── rotation_planner.py            # Motor de Decisão e gatilhos de satélite
│
├── 🛰️ Sensoriamento Remoto & Microsserviços
│   ├── nasa_power.py                  # NASA POWER v2.0 com Snapping de Grade (0.5°)
│   └── copernicus_sentinel2.py        # Copernicus CDSE Sentinel-2 Process API (NDVI 10m)
│
├── 🗺️ Demarcação Territorial & Banco Espacial
│   ├── land_demarcation.py            # Consulta WFS SICAR e demarcação local de alta precisão
│   ├── import_shapefile_to_supabase.py # Leitor Python puro de Shapefiles (.shp / .dbf)
│   └── supabase_schema.sql            # DDL PostgreSQL + PostGIS (GiST indexes, RPCs)
│
└── 💻 Aplicação & Servidor
    ├── index.html                     # Frontend Web interativo (Leaflet + Camadas de Satélite)
    ├── server.py                      # Servidor HTTP REST (porta 8080)
    └── main.py                        # Ponto de entrada CLI para testes rápidos
```

---

## 🚀 5. Como Executar

### Pré-requisitos
* Python 3.9+ instalado (o projeto foi concebido para rodar **sem necessidade de compilar bibliotecas C externas como GDAL ou GeoPandas**, utilizando bibliotecas padrão e chamadas REST puras).

### Configuração de Credenciais (Opcional para Sentinel-2 ao vivo)
1. Copie o arquivo `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```
2. Insira suas credenciais do [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) caso deseje consultar a Process API diretamente.  
   *(Se não fornecido, o sistema ativa automaticamente o fallback com dados de Roraima em cache).*

### Iniciar o Servidor Web e Dashboard
```bash
python server.py
```
Acesse no navegador: **`http://localhost:8080`**

### Testar Análise via Terminal (CLI)
```bash
python main.py
```

---

## 🛡️ 6. Segurança e Conformidade

* **Proteção de Segredos:** Tokens, arquivos `.env` e credenciais locais são estritamente ignorados pelo `.gitignore`.
* **NASA POWER Grid Snapping:** Respeita as políticas da NASA POWER v2.0 com snapping em 0.5° x 0.5°, prevenindo penalidades de HTTP 429 por requisições redundantes.
* **Privacidade Fundiária:** Nenhuma informação privada (como CPFs de produtores) é armazenada ou versionada; utiliza-se apenas as geometrias públicas vetoriais do SICAR.
