# ===============================
# IMPORTAÇÕES E CONFIGURAÇÃO
# ===============================
# Importa bibliotecas essenciais para manipulação de arquivos, requisições, dados e IA
import os
import glob
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env (ex: chave da API)
load_dotenv()

# ==========================================
"""
CONFIGURAÇÕES E VARIÁVEIS GLOBAIS
Mapeamentos de filiais e produtos para padronização dos dados.
"""
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
# FASE 1: RPA - Extração automática de preços de referência
# ==========================================
def extrair_precos_referencia() -> pd.DataFrame:
    print("\n[1/4] Iniciando extração de preços (RPA)...")
    url = "https://bridgenoc.github.io/case-postos/precos_marco2025.html"
    
    # Faz requisição HTTP para obter a tabela de preços
    resposta = requests.get(url)
    resposta.raise_for_status()
    
    # Utiliza BeautifulSoup para parsear o HTML e extrair a tabela
    soup = BeautifulSoup(resposta.text, 'html.parser')
    tabela = soup.find('table')
    linhas = tabela.find_all('tr')
    
    # Extrai cabeçalhos e dados da tabela
    cabecalhos = [th.text.strip() for th in linhas[0].find_all('th')]
    dados = [[col.text.strip() for col in linha.find_all('td')] for linha in linhas[1:]]
    
    # Cria DataFrame com os preços de referência
    df_precos = pd.DataFrame(dados, columns=cabecalhos)
    df_precos['preco_medio_litro_brl'] = df_precos['preco_medio_litro_brl'].astype(float)
    
    print("      ✅ Preços extraídos com sucesso.")
    return df_precos

# ==========================================
# FASE 2: DADOS - Normalização e consolidação das vendas
# ==========================================
def normalizar_e_consolidar_vendas(df_precos: pd.DataFrame) -> pd.DataFrame:
    print("\n[2/4] Iniciando normalização dos arquivos de vendas...")
    arquivos_csv = glob.glob('dados_brutos/vendas_*.csv')
    lista_dfs = []
    
    # Para cada arquivo de vendas, padroniza e adiciona ao DataFrame
    for arquivo in arquivos_csv:
        filial_id = os.path.basename(arquivo).split('_')[1] 
        df_temp = pd.read_csv(arquivo)
        
        # Adiciona informações de filial e padroniza nome do produto
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
    
    # Consolida todos os arquivos em um único DataFrame
    df_consolidado = pd.concat(lista_dfs, ignore_index=True)
    
    # Faz merge com preços de referência e calcula volume estimado
    df_final = pd.merge(df_consolidado, df_precos, left_on='produto_canonico', right_on='produto', how='left')
    df_final['volume_estimado_litros'] = (df_final['valor_total_brl'] / df_final['preco_medio_litro_brl']).round(2)
    
    # Seleciona apenas as colunas finais para exportação
    colunas_finais = ['data', 'filial_id', 'filial_nome', 'produto_canonico', 'valor_total_brl', 'volume_estimado_litros']
    df_final = df_final[colunas_finais]
    
    # Salva arquivo consolidado
    os.makedirs('saida', exist_ok=True)
    caminho_saida = 'saida/vendas_consolidadas_marco2025.csv'
    df_final.to_csv(caminho_saida, index=False)
    
    print(f"      ✅ Vendas consolidadas salvas em '{caminho_saida}'.")
    return df_final

# ==========================================
# FASE 3: IA - Resumo dos e-mails usando LLM (Groq API)
# ==========================================
def resumir_emails_com_ia() -> pd.DataFrame:
    print("\n[3/4] Iniciando análise de e-mails com Groq API...")
    
    # Inicializa cliente da API Groq usando chave do .env
    chave_api = os.getenv("GROQ_API_KEY")
    client = Groq(api_key=chave_api)
    
    arquivos_txt = glob.glob('dados_brutos/email_*.txt')
    resultados = []

    # Prompt base para orientar a IA a responder em JSON estruturado
    prompt_base = """
    Leia o relato e retorne APENAS um JSON válido.
    Estrutura: {"resumo": "...", "destaques": ["..."], "alertas": "...", "sentimento_geral": "..."}
    Relato:
    """

    for arquivo in arquivos_txt:
        filial_id = os.path.basename(arquivo).split('_')[1]
        filial_nome = MAPA_FILIAIS.get(filial_id, 'Desconhecida')
        
        # Lê o conteúdo do e-mail e monta o prompt final
        with open(arquivo, 'r', encoding='utf-8', errors='ignore') as f:
            prompt_final = prompt_base + f.read()
        
        try:
            # Chama a API Groq para resumir o e-mail
            resposta = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt_final}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
            )
            # Converte resposta JSON em dicionário Python
            dados = json.loads(resposta.choices[0].message.content)
            # Adiciona resultado estruturado à lista
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
    
    # Monta DataFrame final e salva CSV
    df_resumos = pd.DataFrame(resultados)
    colunas_finais = ['filial_id', 'filial_nome', 'resumo', 'alertas', 'sentimento_geral', 'destaques']
    df_resumos = df_resumos.reindex(columns=colunas_finais).fillna('')
    caminho_saida = 'saida/resumo_gerentes_marco2025.csv'
    df_resumos.to_csv(caminho_saida, index=False, encoding='utf-8')
    print(f"      ✅ Resumos salvos em '{caminho_saida}'.")
    
    return df_resumos

# ==========================================
# FASE 4: RANKING - Geração de rankings no console
# ==========================================
def gerar_ranking_desempenho(df_vendas: pd.DataFrame):
    print("\n[4/4] Gerando Rankings no Console...")

    # Agrupa e ordena faturamento por filial
    ranking_filial = df_vendas.groupby('filial_nome')['valor_total_brl'].sum().sort_values(ascending=False)
    # Agrupa e ordena volume por produto
    ranking_produto = df_vendas.groupby('produto_canonico')['volume_estimado_litros'].sum().sort_values(ascending=False)

    # Calcula larguras para formatação visual
    max_filial_len = max([len(str(nome)) for nome in ranking_filial.index] + [25])
    max_produto_len = max([len(str(nome)) for nome in ranking_produto.index] + [25])
    total_width_filial = 8 + max_filial_len + 18
    total_width_produto = 8 + max_produto_len + 18

    # Exibe ranking de faturamento por filial
    print("\n" + "="*total_width_filial)
    print(" 🏆 RANKING DE FILIAIS (FATURAMENTO) ".center(total_width_filial-1, "="))
    print("="*total_width_filial)
    for i, (posto, valor) in enumerate(ranking_filial.items(), 1):
        valor_brl = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f" {i}º | {posto:<{max_filial_len}} | {valor_brl:>{15}} ")

    # Exibe ranking de volume por produto
    print("\n" + "="*total_width_produto)
    print(" ⛽ RANKING DE VOLUME POR PRODUTO ".center(total_width_produto-1, "="))
    print("="*total_width_produto)
    for i, (produto, volume) in enumerate(ranking_produto.items(), 1):
        volume_str = f"{volume:,.2f} L".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f" {i}º | {produto:<{max_produto_len}} | {volume_str:>{15}} ")
    print("="*total_width_produto)

if __name__ == "__main__":
    # Executa as etapas principais do processo
    df_precos = extrair_precos_referencia() # 1. Extração automática de preços
    df_vendas = normalizar_e_consolidar_vendas(df_precos) # 2. Consolidação das vendas
    df_resumos = resumir_emails_com_ia() # 3. Resumo dos e-mails com IA
    gerar_ranking_desempenho(df_vendas) # 4. Exibição dos rankings
    print("\n✅ PROCESSO CONCLUÍDO COM SUCESSO!")