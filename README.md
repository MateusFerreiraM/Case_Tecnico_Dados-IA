# Case Bridge - Análise de Vendas de Postos de Combustível

Este projeto consolida, analisa e gera relatórios automáticos a partir de dados de vendas e e-mails de gerentes de filiais de postos de combustível, utilizando RPA, pandas e IA (Groq API). [DADOS FICTÍCIOS]

## 🚀 Como executar

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/MateusFerreiraM/Case_Tecnico_Dados-IA.git
   cd seu-repo-case-bridge
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   python -m venv .venv
   # Ative o ambiente:
   # No Windows:
   .venv\Scripts\activate
   # No Linux/Mac:
   source .venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure a chave da API Groq:**
   - Renomeie o arquivo `.env.example` para `.env`.
   - Coloque sua chave em:
     ```
     GROQ_API_KEY=sua_chave_aqui
     ```

5. **Execute o programa:**
   ```bash
   python resolucao.py
   ```

Os resultados serão gerados na pasta `saida/` e exibidos no console.

---

## 📁 Estrutura do Projeto

```
dados_brutos/
    email_F00X_marco2025.txt
    vendas_F00X_marco2025.csv
saida/
    ranking_desempenho_marco2025.txt
    resumo_gerentes_marco2025.csv
    vendas_consolidadas_marco2025.csv
resolucao.py
requirements.txt
.env.example
```

- **dados_brutos/**: Arquivos de entrada (vendas e e-mails)
- **saida/**: Resultados gerados pelo script
- **resolucao.py**: Script principal
- **requirements.txt**: Dependências do projeto
- **.env.example**: Exemplo de configuração da chave da API

---

## 🛠️ Tecnologias
- Python 3.8+
- pandas
- requests
- beautifulsoup4
- groq
- python-dotenv

---

## 📊 Funcionalidades
- Extração automática de preços de referência (RPA)
- Consolidação e normalização dos dados de vendas
- Análise automática de e-mails de gerentes usando IA
- Geração de rankings de desempenho por filial e produto
- Exportação dos resultados em arquivos CSV e exibição formatada no console

---

## 👤 Autor

Desenvolvido por Mateus Ferreira Machado.

---

Sinta-se à vontade para usar este projeto como base para outros desafios de análise de dados! 😃
