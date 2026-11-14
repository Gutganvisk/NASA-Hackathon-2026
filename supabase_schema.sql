-- =====================================================================
-- ESQUEMA COMPLETO PARA O SUPABASE (PostgreSQL + PostGIS)
-- Sistema de Cadastro de Agricultor Familiar com Demarcação de Terras
-- =====================================================================

-- 1. Ativa a extensão espacial PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Tabela de Imóveis Rurais (Perímetros, Áreas Consolidadas e Reserva Legal)
CREATE TABLE IF NOT EXISTS sicar_imoveis (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cod_imovel TEXT UNIQUE NOT NULL,
    municipio TEXT NOT NULL,
    uf VARCHAR(2) NOT NULL DEFAULT 'RR',
    status_imovel VARCHAR(50) DEFAULT 'AT',
    tipo_imovel VARCHAR(50) DEFAULT 'IRU', -- Imóvel Rural
    modulos_fiscais NUMERIC(10, 4),
    
    -- Áreas em Hectares
    area_total_ha NUMERIC(12, 4) NOT NULL,
    area_consolidada_ha NUMERIC(12, 4) DEFAULT 0,
    area_reserva_legal_ha NUMERIC(12, 4) DEFAULT 0,
    area_app_ha NUMERIC(12, 4) DEFAULT 0,

    -- Áreas convertidas automaticamente para Metros Quadrados (ha * 10.000)
    area_total_m2 NUMERIC(16, 2) GENERATED ALWAYS AS (area_total_ha * 10000) STORED,
    area_consolidada_m2 NUMERIC(16, 2) GENERATED ALWAYS AS (area_consolidada_ha * 10000) STORED,
    area_reserva_legal_m2 NUMERIC(16, 2) GENERATED ALWAYS AS (area_reserva_legal_ha * 10000) STORED,

    -- Geometrias Espaciais em EPSG:4326 (WGS84 / GPS)
    geom GEOMETRY(MultiPolygon, 4326) NOT NULL,
    geom_consolidada GEOMETRY(MultiPolygon, 4326),
    geom_reserva_legal GEOMETRY(MultiPolygon, 4326),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices espaciais GiST (garantem busca geográfica em < 50ms)
CREATE INDEX IF NOT EXISTS idx_sicar_imoveis_geom ON sicar_imoveis USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_sicar_imoveis_cod ON sicar_imoveis (cod_imovel);

-- 3. Tabela de Produtores / Agricultores Familiares Cadastrados
CREATE TABLE IF NOT EXISTS agricultores_familiares (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    nome_completo TEXT NOT NULL,
    telefone VARCHAR(30) NOT NULL,
    email VARCHAR(255),
    endereco TEXT NOT NULL,
    cod_car TEXT NOT NULL REFERENCES sicar_imoveis(cod_imovel) ON DELETE RESTRICT,
    cod_ccir TEXT,
    observacoes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agricultores_cod_car ON agricultores_familiares (cod_car);

-- =====================================================================
-- 4. FUNÇÃO RPC: Consulta Completa por Código do CAR
-- Retorna os dados, métricas em m² e GeoJSON pronto para Leaflet/Mapbox
-- =====================================================================
CREATE OR REPLACE FUNCTION buscar_demarcacao_imovel(p_cod_imovel TEXT)
RETURNS JSON AS $$
DECLARE
    resultado JSON;
BEGIN
    SELECT json_build_object(
        'encontrado', true,
        'cod_imovel', cod_imovel,
        'municipio', municipio,
        'uf', uf,
        'status', status_imovel,
        'modulos_fiscais', modulos_fiscais,
        'areas', json_build_object(
            'total_ha', area_total_ha,
            'total_m2', area_total_m2,
            'consolidada_ha', area_consolidada_ha,
            'consolidada_m2', area_consolidada_m2,
            'reserva_legal_ha', area_reserva_legal_ha,
            'reserva_legal_m2', area_reserva_legal_m2,
            'app_ha', area_app_ha,
            'app_m2', ROUND(area_app_ha * 10000, 2)
        ),
        'centroid', json_build_object(
            'latitude', ST_Y(ST_Centroid(geom)),
            'longitude', ST_X(ST_Centroid(geom))
        ),
        'geojson_perimetro', json_build_object(
            'type', 'Feature',
            'geometry', ST_AsGeoJSON(geom)::json,
            'properties', json_build_object(
                'camada', 'Perímetro do Imóvel',
                'area_m2', area_total_m2
            )
        ),
        'geojson_consolidada', CASE 
            WHEN geom_consolidada IS NOT NULL THEN json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(geom_consolidada)::json,
                'properties', json_build_object(
                    'camada', 'Área Consolidada (Plantio)',
                    'area_m2', area_consolidada_m2
                )
            )
            ELSE NULL 
        END,
        'geojson_reserva_legal', CASE 
            WHEN geom_reserva_legal IS NOT NULL THEN json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(geom_reserva_legal)::json,
                'properties', json_build_object(
                    'camada', 'Reserva Legal (Protegida)',
                    'area_m2', area_reserva_legal_m2
                )
            )
            ELSE NULL 
        END
    )
    INTO resultado
    FROM sicar_imoveis
    WHERE cod_imovel = p_cod_imovel
    LIMIT 1;

    IF resultado IS NULL THEN
        RETURN json_build_object('encontrado', false, 'mensagem', 'Imóvel não encontrado na base de dados.');
    END IF;

    RETURN resultado;
END;
$$ LANGUAGE plpgsql STABLE;

-- =====================================================================
-- 5. FUNÇÃO RPC: Consulta por Ponto Clicado no Mapa (Intersecção)
-- =====================================================================
CREATE OR REPLACE FUNCTION buscar_demarcacao_por_ponto(p_lat DOUBLE PRECISION, p_lon DOUBLE PRECISION)
RETURNS JSON AS $$
DECLARE
    v_cod TEXT;
BEGIN
    SELECT cod_imovel INTO v_cod
    FROM sicar_imoveis
    WHERE ST_Intersects(geom, ST_SetSRID(ST_Point(p_lon, p_lat), 4326))
    LIMIT 1;

    IF v_cod IS NULL THEN
        RETURN json_build_object('encontrado', false, 'mensagem', 'Nenhum imóvel demarcado intercepta este ponto.');
    END IF;

    RETURN buscar_demarcacao_imovel(v_cod);
END;
$$ LANGUAGE plpgsql STABLE;
