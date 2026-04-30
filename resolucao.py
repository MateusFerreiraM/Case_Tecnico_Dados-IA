import os
import glob
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from groq import Groq
# Carrega variáveis de ambiente do .env automaticamente ao importar
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# CONFIGURAÇÕES E VARIÁVEIS GLOBAIS
# Centralizamos os mapeamentos para facilitar manutenção
# ==========================================
MAPA_FILIAIS = {
    'F001': 'Posto Bandeirantes',
    'F002': 'Auto Posto Central', 
    'F003': 'Posto São João',
    'F004': 'Posto Ipiranga Express',
    'F005': 'Posto Litoral Norte'
}

MAPA_PRODUTOS = {
    'gc': 'Gasolina Comum',
    'gas. comum': 'Gasolina Comum',
    'gasolina comum': 'Gasolina Comum',
    'gasolina': 'Gasolina Comum',
    'gasolina c': 'Gasolina Comum',
    'gasolina comun': 'Gasolina Comum',
    'etanol': 'Etanol',
    'alc': 'Etanol',
    'alcool': 'Etanol',
    'álcool': 'Etanol',
    'etanol comum': 'Etanol',
    'etanol hid.': 'Etanol',
    'etanol hidratado': 'Etanol',
    'diesel s10': 'Diesel S10',
    'dsl s10': 'Diesel S10',
    'diesel': 'Diesel S10',
    's10': 'Diesel S10',
    'diesel s-10': 'Diesel S10',
    'diesel s10 aditivado': 'Diesel S10'
}

# ==========================================
# FASE 1: RPA
# ==========================================
def extrair_precos_referencia() -> pd.DataFrame:
    print("\n[1/4] Iniciando extração de preços (RPA)...")
    url = "https://bridgenoc.github.io/case-postos/precos_marco2025.html"
    
    resposta = requests.get(url)
    resposta.raise_for_status()
    
    soup = BeautifulSoup(resposta.text, 'html.parser')
    tabela = soup.find('table')
    linhas = tabela.find_all('tr')
    
    cabecalhos = [th.text.strip() for th in linhas[0].find_all('th')]
    dados = [[col.text.strip() for col in linha.find_all('td')] for linha in linhas[1:]]
        
    df_precos = pd.DataFrame(dados, columns=cabecalhos)
    df_precos['preco_medio_litro_brl'] = df_precos['preco_medio_litro_brl'].astype(float)
    
    print("      ✅ Preços extraídos com sucesso.")
    return df_precos

# ==========================================
# FASE 2: DADOS
# ==========================================
def normalizar_e_consolidar_vendas(df_precos: pd.DataFrame) -> pd.DataFrame:
    print("\n[2/4] Iniciando normalização dos arquivos de vendas...")
    arquivos_csv = glob.glob('dados_brutos/vendas_*.csv')
    lista_dfs = []
    
    for arquivo in arquivos_csv:
        filial_id = os.path.basename(arquivo).split('_')[1] 
        df_temp = pd.read_csv(arquivo)
        
        df_temp['filial_id'] = filial_id
        df_temp['filial_nome'] = MAPA_FILIAIS.get(filial_id, 'Desconhecida')
        
        df_temp['produto_canonico'] = (
            df_temp['produto']
            .str.strip()
            .str.lower()
            .map(MAPA_PRODUTOS)
            .fillna(df_temp['produto'])
        )
        lista_dfs.append(df_temp)
        
    df_consolidado = pd.concat(lista_dfs, ignore_index=True)
    
    df_final = pd.merge(df_consolidado, df_precos, left_on='produto_canonico', right_on='produto', how='left')
    df_final['volume_estimado_litros'] = (df_final['valor_total_brl'] / df_final['preco_medio_litro_brl']).round(2)
    
    colunas_finais = ['data', 'filial_id', 'filial_nome', 'produto_canonico', 'valor_total_brl', 'volume_estimado_litros']
    df_final = df_final[colunas_finais]
    
    os.makedirs('saida', exist_ok=True)
    caminho_saida = 'saida/vendas_consolidadas_marco2025.csv'
    df_final.to_csv(caminho_saida, index=False)
    
    print(f"      ✅ Vendas consolidadas salvas em '{caminho_saida}'.")
    return df_final

# ==========================================
# FASE 3: IA
# ==========================================
def resumir_emails_com_ia() -> pd.DataFrame:
    print("\n[3/4] Iniciando análise de e-mails com Groq API...")
    
    chave_api = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=chave_api)
    
    arquivos_txt = glob.glob('dados_brutos/email_*.txt')
    resultados = []

    prompt_base = """
    Leia o relato e retorne APENAS um JSON válido.
    Estrutura: {"resumo": "...", "destaques": ["..."], "alertas": "...", "sentimento_geral": "..."}
    Relato:
    """

    for arquivo in arquivos_txt:
        filial_id = os.path.basename(arquivo).split('_')[1]
        filial_nome = MAPA_FILIAIS.get(filial_id, 'Desconhecida')
        
        with open(arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            prompt_final = prompt_base + f.read()
            
        try:
            resposta = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt_final}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
            )
            
            dados = json.loads(resposta.choices[0].message.content)
            
            resultados.append({
                'filial_id': filial_id,
                'filial_nome': filial_nome,
                'resumo': dados.get('resumo', ''),
                'alertas': dados.get('alertas', ''),
                'sentimento_geral': dados.get('sentimento_geral', ''),
                'destaques': " | ".join(dados.get('destaques', []))
            })
        except Exception as e:
            print(f"      ❌ Erro ao processar a filial {filial_id}: {e}")
            resultados.append({'filial_id': filial_id, 'filial_nome': filial_nome})
        
    df_resumos = pd.DataFrame(resultados)
    
    colunas_finais = ['filial_id', 'filial_nome', 'resumo', 'alertas', 'sentimento_geral', 'destaques']
    df_resumos = df_resumos.reindex(columns=colunas_finais).fillna('')
    
    caminho_saida = 'saida/resumo_gerentes_marco2025.csv'
    df_resumos.to_csv(caminho_saida, index=False, encoding='utf-8')
    print(f"      ✅ Resumos salvos em '{caminho_saida}'.")
    
    return df_resumos

# ==========================================
# FASE 4: RANKING (Console)
# ==========================================
def gerar_ranking_desempenho(df_vendas: pd.DataFrame):
    print("\n[4/4] Gerando Rankings no Console...")

    ranking_filial = df_vendas.groupby('filial_nome')['valor_total_brl'].sum().sort_values(ascending=False)
    ranking_produto = df_vendas.groupby('produto_canonico')['volume_estimado_litros'].sum().sort_values(ascending=False)

    max_filial_len = max([len(str(nome)) for nome in ranking_filial.index] + [25])
    max_produto_len = max([len(str(nome)) for nome in ranking_produto.index] + [25])

    total_width_filial = 8 + max_filial_len + 18
    total_width_produto = 8 + max_produto_len + 18

    print("\n" + "="*total_width_filial)
    print(" 🏆 RANKING DE FILIAIS (FATURAMENTO) ".center(total_width_filial-1, "="))
    print("="*total_width_filial)
    for i, (posto, valor) in enumerate(ranking_filial.items(), 1):
        valor_brl = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f" {i}º | {posto:<{max_filial_len}} | {valor_brl:>{15}} ")

    print("\n" + "="*total_width_produto)
    print(" ⛽ RANKING DE VOLUME POR PRODUTO ".center(total_width_produto-1, "="))
    print("="*total_width_produto)
    for i, (produto, volume) in enumerate(ranking_produto.items(), 1):
        volume_str = f"{volume:,.2f} L".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f" {i}º | {produto:<{max_produto_len}} | {volume_str:>{15}} ")
    print("="*total_width_produto)

if __name__ == "__main__":
    df_precos = extrair_precos_referencia() # 1.RPA
    df_vendas = normalizar_e_consolidar_vendas(df_precos) # 2.DADOS
    df_resumos = resumir_emails_com_ia() # 3.IA
    gerar_ranking_desempenho(df_vendas) # 4.RANKING
    
    print("\n✅ PROCESSO CONCLUÍDO COM SUCESSO!")