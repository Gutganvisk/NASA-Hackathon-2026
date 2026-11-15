BEGIN;

-- ========================================================
-- SCHEMA SQL PARA SUPABASE (POSTGRESQL + POSTGIS)
-- Crop Rotation - NASA Space Apps Challenge 2026
-- Execute este script no SQL Editor do seu projeto Supabase
-- ========================================================

-- 1. Habilitar extensões úteis (UUID e PostGIS opcional)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Tabela de Planos de Rotação e Cadastro de Produtores
CREATE TABLE IF NOT EXISTS public.produtores_planos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    nome_produtor TEXT NOT NULL,
    telefone TEXT,
    cod_car TEXT NOT NULL,
    nome_propriedade TEXT,
    talhao_id TEXT DEFAULT 'T1',
    area_ha NUMERIC(10, 2),
    cultura_atual TEXT,
    objetivo TEXT,
    horizonte_anos INTEGER DEFAULT 3,
    estrategia_selecionada JSONB DEFAULT '{}'::jsonb,
    dados_climaticos JSONB DEFAULT '{}'::jsonb,
    observacoes TEXT
);

-- Índices para buscas rápidas
CREATE INDEX IF NOT EXISTS idx_produtores_planos_car ON public.produtores_planos (cod_car);
CREATE INDEX IF NOT EXISTS idx_produtores_planos_telefone ON public.produtores_planos (telefone);
CREATE INDEX IF NOT EXISTS idx_produtores_planos_created ON public.produtores_planos (created_at DESC);

-- 3. Tabela de Propriedades Rurais e Delimitação dos Talhões
CREATE TABLE IF NOT EXISTS public.propriedades_rurais (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    cod_car TEXT UNIQUE NOT NULL,
    nome TEXT,
    municipio TEXT,
    uf TEXT DEFAULT 'RR',
    area_total_ha NUMERIC(12, 4),
    area_consolidada_ha NUMERIC(12, 4),
    talhoes JSONB DEFAULT '{}'::jsonb,
    geojson JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_propriedades_car ON public.propriedades_rurais (cod_car);

-- 4. Configuração de Políticas de Segurança (Row Level Security - RLS)
ALTER TABLE public.produtores_planos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.propriedades_rurais ENABLE ROW LEVEL SECURITY;

-- O navegador usa o backend. A Data API não concede acesso público às tabelas.
DROP POLICY IF EXISTS "Permitir leitura pública de planos" ON public.produtores_planos;
DROP POLICY IF EXISTS "Permitir gravação de planos" ON public.produtores_planos;
DROP POLICY IF EXISTS "Permitir leitura pública de propriedades" ON public.propriedades_rurais;
DROP POLICY IF EXISTS "Permitir gravação e atualização de propriedades" ON public.propriedades_rurais;

REVOKE ALL ON TABLE public.produtores_planos, public.propriedades_rurais FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.produtores_planos, public.propriedades_rurais TO service_role;

-- Notificação de sucesso
COMMENT ON TABLE public.produtores_planos IS 'Planos de rotação agroclimáticos salvos pelos produtores';
COMMENT ON TABLE public.propriedades_rurais IS 'Glebas rurais mapeadas e demarcação de talhões';

COMMIT;
