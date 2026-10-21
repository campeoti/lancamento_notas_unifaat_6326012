"""Configurações do projeto Lançamento de Notas."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeyj73ps3ozKlKMRg5cUML1GRHkq-tDrdKg8smDf7klBYyOOA/viewform"

CSV_ENTRADA = DADOS_DIR / "notas.csv"

PLANILHA_URL = "https://docs.google.com/spreadsheets/d/1BL3dBXkZYlDYau5lzG1RMcLXwFNLKGPg-v7CXV_gxtI/edit?usp=sharing"
EXCEL_RESPOSTAS = DADOS_DIR / "respostas.xlsx"

COLUNAS = ["RA", "Nome", "Nota 1", "Nota 2", "TF01", "TF02"]
SEM_RA = "SEM RA"

NOTA_PROVA_MAX = 10.0
NOTA_TF_MAX = 2.0
PESO_PROVA = 8
NOTA_CORTE = 7.0

NAVEGADOR = ""
PORTA_DEPURACAO = 9333
PERFIL_NAVEGADOR = Path.home() / ".lancamento_notas_rpa" / "perfil"
IDIOMA_NAVEGADOR = "pt-BR"

TEMPO_CARREGAR_FORM = 15
TEMPO_MOVER_MOUSE = 0.5
INTERVALO_DIGITACAO = 0.05
TEMPO_ENTRE_CAMPOS = 0.3
TEMPO_APOS_ENVIAR = 15
