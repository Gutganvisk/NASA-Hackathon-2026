import pdfplumber
import os
import pandas as pd
import re

# ==========================================
# 1. CONFIGURAÇÕES INICIAIS
# ==========================================
# Lista de caminhos dos PDFs locais
pdfs = [
    "/content/cit032005milho.pdf",
    "/content/cit052005-mandioca-dalton.pdf",
    "/content/CIT170N09.pdf",
    "/content/DOC452010ID80.pdf",
    "/content/Cot122001milhoesorgodaniel.pdf",
    "/content/BP052005conbeamilhoroberto.pdf",
    "/content/PDF012002tratsemilhosmiderle.pdf",
    "/content/Cot0092002amapssjoscar.pdf",
    "/content/0052002milhodaniel.pdf",
    "/content/O-Cultivo-da-Mandioca-em-Roraima.pdf",
    "/content/cot182008-mandiocaprod-dalton.pdf",
    "/content/0082002mandiocadalton.pdf"
]

# Termos refinados de busca
termos_busca = [
    "milho", "mandioca", "caupi", "feijão", "vigna", 
    "nitrogênio", "potássio", "fósforo", "adubação",
    "rotação", "ciclo", "espaçamento", "cobertura"
]

# Dicionário de categorização para as 7 Engrenagens do Passaporte Biológico
atributos_termos = {
    "1. Balanço de N": ["nitrogênio", "fixação", "nodulação", "balanço", "uréia"],
    "2. Extração de K/P": ["potássio", "fósforo", "extração", "exportação", "k2o", "p2o5"],
    "3. Sistema Radicular": ["raiz", "radicular", "fasciculad", "pivotante", "compactação", "profundidade"],
    "4. Grupo Fitossanitário": ["praga", "doença", "fungo", "nematóide", "rotação", "família", "patógeno"],
    "5. Relação C/N": ["c/n", "carbono", "palhada", "decomposição", "imobilização", "cobertura morta"],
    "6. Tolerância à Acidez/Al": ["acidez", "alumínio", "al3+", "calagem", "ph", "saturação", "calcário", "tóxico"],
    "7. Coeficiente Kc/Água": ["kc", "coeficiente", "evapotranspiração", "fenolog", "hídric", "seca", "chuva", "estresse", "água"]
}

# ==========================================
# 2. FUNÇÕES DO MOTOR
# ==========================================
def extrair_contexto_robusto(arquivos, termos):
    dados = []
    for caminho in arquivos:
        if not os.path.exists(caminho):
            continue
        nome_arquivo = os.path.basename(caminho)
        try:
            with pdfplumber.open(caminho) as pdf:
                for num_pag, pagina in enumerate(pdf.pages, 1):
                    texto = pagina.extract_text()
                    if not texto: continue
                    
                    texto_limpo = re.sub(r'-\n\s*', '', texto)
                    linhas = texto_limpo.split('\n')
                    tamanho_janela = 2
                    
                    for i, linha in enumerate(linhas):
                        linha_lower = linha.lower()
                        termos_encontrados = [t for t in termos if t in linha_lower]
                        
                        if termos_encontrados:
                            inicio = max(0, i - tamanho_janela)
                            fim = min(len(linhas), i + tamanho_janela + 1)
                            contexto_completo = " ".join(linhas[inicio:fim]).strip()
                            contexto_completo = re.sub(r'\s+', ' ', contexto_completo)
                            
                            dados.append({
                                "Arquivo": nome_arquivo,
                                "Página": num_pag,
                                "Termos Encontrados": ", ".join(termos_encontrados),
                                "Contexto Expandido": contexto_completo
                            })
        except Exception as e:
            print(f"Erro ao processar {nome_arquivo}: {e}")
            
    df = pd.DataFrame(dados)
    if not df.empty:
        df = df.drop_duplicates(subset=['Arquivo', 'Página', 'Contexto Expandido'])
    return df

def mapear_atributos_passaporte(texto):
    texto_lower = texto.lower()
    categorias = []
    for atributo, palavras in atributos_termos.items():
        if any(p in texto_lower for p in palavras):
            categorias.append(atributo)
    return ", ".join(categorias) if categorias else "Sem Categoria"

# ==========================================
# 3. PIPELINE DE EXECUÇÃO
# ==========================================
if __name__ == "__main__":
    print("\n[1/3] Extraindo contextos relevantes dos PDFs...")
    df_mapeamento = extrair_contexto_robusto(pdfs, termos_busca)
    
    print("[2/3] Classificando trechos nas 7 Engrenagens do Passaporte...")
    df_mapeamento['Atributos do Passaporte'] = df_mapeamento['Contexto Expandido'].apply(mapear_atributos_passaporte)
    df_passaporte = df_mapeamento[df_mapeamento['Atributos do Passaporte'] != "Sem Categoria"].copy()
    
    # Exportando o dump bruto
    df_mapeamento.to_csv('extracao_agronomica_bruta.csv', index=False, encoding='utf-8-sig')
    
    print("[3/3] Consolidando a Matriz Final do Passaporte Biológico...")
    culturas_alvo = {
        "Milho": "milho",
        "Mandioca": "mandioca",
        "Feijão-Caupi": "caupi|feijão|vigna"
    }
    
    matriz_passaporte = []
    atributos_lista = list(atributos_termos.keys())
    
    for nome_cultura, regex_cultura in culturas_alvo.items():
        df_cultura = df_passaporte[df_passaporte['Contexto Expandido'].str.contains(regex_cultura, case=False, na=False)]
        linha_cultura = {"Cultura": nome_cultura}
        
        for atributo in atributos_lista:
            df_attr = df_cultura[df_cultura['Atributos do Passaporte'].str.contains(atributo, regex=False, na=False)]
            trechos = df_attr['Contexto Expandido'].head(3).tolist()
            resumo = " | ".join([t.replace("\n", " ") for t in trechos]) if trechos else "Sem dados específicos extraídos."
            linha_cultura[atributo] = resumo
            
        matriz_passaporte.append(linha_cultura)
        
    df_passaporte_sintetizado = pd.DataFrame(matriz_passaporte)
    df_passaporte_sintetizado.to_csv('matriz_passaporte_biologico.csv', index=False, encoding='utf-8-sig')
    
    print("\nWorkflow concluído com sucesso! Arquivos gerados:")
    print("- extracao_agronomica_bruta.csv")
    print("- matriz_passaporte_biologico.csv")
