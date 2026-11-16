# Plataforma de Prescrição Agroclimática e Demarcação Geoespacial
## Agricultura Familiar de Roraima (Bioma Amazônia & Lavrado)
### NASA Space Apps Challenge 2026

Plataforma unificada para planejamento sincronizado de rotação de culturas, sensoriamento remoto de cobertura do solo e regularização de imóveis rurais da agricultura familiar em Roraima, integrando dados orbitais da **NASA** e da **ESA** com a **Matriz de Passaporte Biológico da Embrapa Roraima**.

---

## Dados e interpretação

- **NASA POWER (AG)** fornece chuva acumulada, temperatura, radiação e saturação relativa do solo. O diagnóstico solicita os últimos 14 dias UTC completos e informa quantos dias tinham dados em cada variável.
- **Copernicus Sentinel-2 L2A** fornece NDVI médio sobre o perímetro CAR, para o dia mais recente com pixels terrestres válidos nos últimos 30 dias. O NDVI indica vigor da vegetação verde. A declividade e a análise de solo exigem fontes adicionais.
- **CAR** usa o perímetro do Supabase, uma cópia local quando disponível ou a consulta WFS. Área consolidada e reserva legal exigem camadas próprias. O mapa exibe a geometria cadastrada sobre uma imagem Sentinel-2 solicitada pelo backend. A imagem regional cobre Boa Vista até que o usuário consulte um CAR.
- **Desenho dos talhões** permite marcar e mover pontos de T1, T2 e T3. O backend calcula a área, valida o contorno e avisa sobre sobreposições. O desenho fica na sessão da aba, separado por CAR. Se recarregar, consulte o mesmo CAR para recuperar os talhões vinculados a ele.
- **Agenda** aponta para o [ZARC vigente de Roraima](https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/programa-nacional-de-zoneamento-agricola-de-risco-climatico/portarias/safra-vigente/roraima/roraima-rr) e para as orientações da Embrapa. Confira município, solo, grupo de cultivar e nível de risco para definir a janela de plantio. A simulação compara estratégias qualitativas de manejo.

## Supabase e Cloud Run

Execute [supabase_schema.sql](supabase_schema.sql) no SQL Editor do projeto antes de publicar. O script revoga o acesso direto de clientes às tabelas e preserva o acesso pelo backend. Registros anteriores permanecem no banco. O fluxo atual grava apenas cultura, objetivo, horizonte e identificador da estratégia, sem vínculo com o CAR.

Use `SUPABASE_URL` como configuração do serviço. Vincule `SUPABASE_KEY` (chave de servidor compatível com o papel `service_role`), `CDSE_CLIENT_ID` e `CDSE_CLIENT_SECRET` ao Secret Manager. A identidade do serviço precisa de `roles/secretmanager.secretAccessor` nos segredos vinculados. Prefira versões numéricas no vínculo de cada variável. Veja [Configurar segredos do Cloud Run](https://docs.cloud.google.com/run/docs/configuring/services/secrets).

O servidor usa o `PORT` injetado pelo Cloud Run. A rota `/healthz` verifica o processo HTTP sem depender dos provedores externos.

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
│   ├── nasa_power.py                  # NASA POWER v2.0 com janela móvel
│   └── copernicus_sentinel2.py        # Copernicus CDSE Sentinel-2 Statistical API (NDVI no perímetro)
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
2. Insira suas credenciais do [Copernicus Data Space Ecosystem](https://dataspace.copernicus.eu/) caso deseje consultar a Statistical API diretamente.
   Sem credenciais do CDSE, o NDVI aparece como indisponível.

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
