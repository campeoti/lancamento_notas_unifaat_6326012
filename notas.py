"""Leitura e formatação do CSV de notas, leitura da planilha de respostas do Forms e cálculo da média."""
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from config import (COLUNAS, CSV_ENTRADA, DADOS_DIR, EXCEL_RESPOSTAS, NOTA_CORTE, NOTA_PROVA_MAX,
                    NOTA_TF_MAX, PESO_PROVA, PLANILHA_URL, SEM_RA)

CABECALHOS = {
    "RA": "RA", "NOME": "Nome",
    "NOTA1": "Nota 1", "NOTA01": "Nota 1", "N1": "Nota 1", "PROVA1": "Nota 1",
    "NOTA2": "Nota 2", "NOTA02": "Nota 2", "N2": "Nota 2", "PROVA2": "Nota 2",
    "TF01": "TF01", "TF1": "TF01",
    "TF02": "TF02", "TF2": "TF02", "T02": "TF02",
}
FAIXAS = {"Nota 1": NOTA_PROVA_MAX, "Nota 2": NOTA_PROVA_MAX, "TF01": NOTA_TF_MAX, "TF02": NOTA_TF_MAX}
SEM_NOTA = {"", "FALTOU", "FALTA", "N/A", "NA", "-", "--", "NAN"}
PALAVRAS_MINUSCULAS = {"da", "de", "do", "das", "dos", "e"}


def _chave_cabecalho(nome) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(nome).upper())


def formatar_nota(valor) -> float:
    """Nota bagunçada -> número com 2 casas. ' 9,5 ' -> 9.50, '8.333' -> 8.33, FALTOU/N/A/-/vazio -> 0."""
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        return 0.0
    texto = re.sub(r"[\s\"']", "", str(valor))
    if texto.upper() in SEM_NOTA:
        return 0.0
    if "," in texto and "." in texto:
        decimal = max(texto.rfind(","), texto.rfind("."))
        texto = re.sub(r"[.,]", "", texto[:decimal]) + "." + texto[decimal + 1:]
    texto = texto.replace(",", ".").rstrip(".")
    try:
        numero = Decimal(texto)
    except InvalidOperation:
        raise ValueError(f"nota inválida {valor!r}") from None
    return float(numero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def formatar_nome(nome) -> str:
    palavras = str(nome).strip().split()
    return " ".join(p.lower() if i > 0 and p.lower() in PALAVRAS_MINUSCULAS else p.capitalize()
                    for i, p in enumerate(palavras))


def formatar_ra(ra) -> str:
    """Só os números, juntos e sem zero à esquerda: 'RA100004' -> '100004', '0100001' -> '100001', '100019-0' -> '1000190'."""
    if ra is None or (not isinstance(ra, str) and pd.isna(ra)):
        return ""
    texto = re.sub(r"\.0$", "", str(ra).strip())
    return re.sub(r"\D", "", texto).lstrip("0")


def renomear_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=lambda c: CABECALHOS.get(_chave_cabecalho(c), str(c).strip()))
    faltando = [c for c in COLUNAS if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas ausentes: {faltando}. Encontradas: {list(df.columns)}")
    return df[COLUNAS]


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    df = renomear_colunas(df).dropna(how="all").copy()
    df["RA"] = df["RA"].map(formatar_ra)
    df["Nome"] = df["Nome"].map(formatar_nome)
    for col in FAIXAS:
        df[col] = df[col].map(formatar_nota)
    return df.reset_index(drop=True)


def analisar(df_bruto: pd.DataFrame) -> pd.DataFrame:
    """Formata cada aluno do CSV na ordem RA, Nome, Nota 1, Nota 2, TF01, TF02.

    Nota acima do limite vira o limite (prova 10, TF 2) e RA vazio vira 'SEM RA'; ambos ficam em 'Ajuste'.
    Nota ilegível ou RA repetido ficam em 'Problema' e não são lançados.
    """
    alunos = []
    for linha, bruto in enumerate(renomear_colunas(df_bruto).to_dict("records"), start=2):
        if all(str(v).strip() == "" for v in bruto.values()):
            continue
        aluno = {"Linha": linha, "RA": formatar_ra(bruto["RA"]) or SEM_RA, "Nome": formatar_nome(bruto["Nome"])}
        problemas = []
        ajustes = [f"RA vazio -> {SEM_RA}"] if aluno["RA"] == SEM_RA else []
        for col, maximo in FAIXAS.items():
            try:
                nota = formatar_nota(bruto[col])
            except ValueError as erro:
                problemas.append(f"{col} {erro}")
                nota = 0.0
            if nota > maximo:
                ajustes.append(f"{col} {nota:.2f} -> {maximo:.2f}")
                nota = maximo
            elif nota < 0:
                ajustes.append(f"{col} {nota:.2f} -> 0.00")
                nota = 0.0
            aluno[col] = nota
        aluno["Ajuste"] = "; ".join(ajustes)
        aluno["Problema"] = "; ".join(problemas)
        alunos.append(aluno)

    df = pd.DataFrame(alunos, columns=["Linha"] + COLUNAS + ["Ajuste", "Problema"])
    repetido = (df["RA"] != SEM_RA) & df["RA"].duplicated(keep=False)
    df.loc[repetido, "Problema"] = df.loc[repetido, "Problema"].map(
        lambda p: "; ".join(filter(None, [p, "RA repetido no CSV"])))
    return df.reset_index(drop=True)


def lancaveis(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Problema"] == ""][COLUNAS].reset_index(drop=True)


def pendentes(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["Problema"] != ""].reset_index(drop=True)


def sem_ra(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["RA"] == SEM_RA].reset_index(drop=True)


def calcular_media(n1, n2, tf01, tf02) -> float:
    """Média final de 0 a 10: provas (0-10) valem até 8 e TF (0-2) vale até 2."""
    d = lambda v: Decimal(str(v))
    parte_prova = (d(n1) + d(n2)) / 2 / d(NOTA_PROVA_MAX) * d(PESO_PROVA)
    parte_tf = (d(tf01) + d(tf02)) / 2
    return float((parte_prova + parte_tf).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def situacao(media: float) -> str:
    """Aprovado com média final maior ou igual à nota de corte."""
    return "APROVADO" if media >= NOTA_CORTE else "REPROVADO"


def adicionar_media(df: pd.DataFrame) -> pd.DataFrame:
    df["Média Final"] = [
        calcular_media(r["Nota 1"], r["Nota 2"], r["TF01"], r["TF02"]) for _, r in df.iterrows()
    ]
    df["Situação"] = df["Média Final"].map(situacao)
    return df


def ler_csv(caminho) -> pd.DataFrame:
    """Lê CSV separado por , ou ; salvo em UTF-8 ou pelo Excel (Windows-1252)."""
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(caminho, sep=None, engine="python", dtype=str,
                               encoding=codificacao, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Não consegui ler o arquivo {caminho}")


def carregar_csv(csv_path=CSV_ENTRADA) -> pd.DataFrame:
    """CSV recebido -> todos os alunos formatados, com as colunas Ajuste e Problema."""
    return analisar(ler_csv(csv_path))


def salvar_formatado(df: pd.DataFrame, destino) -> None:
    saida = df[COLUNAS].copy()
    for col in FAIXAS:
        saida[col] = saida[col].map(lambda v: f"{v:.2f}")
    saida.to_csv(destino, index=False, encoding="utf-8")


def _url_export_csv(url: str) -> str:
    """Converte o link da planilha do Google em link de exportação CSV."""
    m = re.search(r"/spreadsheets/d/([\w-]+)", url)
    if not m:
        raise ValueError(f"Link de planilha inválido: {url}")
    gid = re.search(r"[#&?]gid=(\d+)", url)
    return (f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
            + (f"&gid={gid.group(1)}" if gid else ""))


def carregar_respostas(fonte=None) -> pd.DataFrame:
    """Planilha de respostas do Forms (Google Sheets pelo link, ou .xlsx/.csv baixado).

    Se o mesmo aluno foi enviado mais de uma vez, vale o último envio (alunos SEM RA são comparados pelo nome).
    """
    fonte = str(fonte or PLANILHA_URL or EXCEL_RESPOSTAS)
    if fonte.startswith("http"):
        df = pd.read_csv(_url_export_csv(fonte), dtype=str)
    elif fonte.lower().endswith(".csv"):
        df = ler_csv(fonte)
    else:
        df = pd.read_excel(fonte, dtype=str)
    df = normalizar(df)
    df["RA"] = df["RA"].replace("", SEM_RA)
    chave = df["RA"].where(df["RA"] != SEM_RA, SEM_RA + ":" + df["Nome"])
    df = df[~chave.duplicated(keep="last")]
    return adicionar_media(df.reset_index(drop=True))


def tabela_texto(df: pd.DataFrame) -> str:
    return df.to_string(index=False, float_format=lambda v: f"{v:.2f}")


def mostrar_relatorio(df: pd.DataFrame) -> None:
    ajustados = df[df["Ajuste"] != ""]
    if not ajustados.empty:
        print(f"\n{len(ajustados)} aluno(s) com ajuste automático (nota acima do limite ou sem RA):\n")
        print(tabela_texto(ajustados[["Linha", "RA", "Nome", "Ajuste"]]))
    problemas = pendentes(df)
    if not problemas.empty:
        print(f"\n{len(problemas)} aluno(s) NÃO serão lançados (corrija no CSV):\n")
        print(tabela_texto(problemas[["Linha", "RA", "Nome", "Problema"]]))


if __name__ == "__main__":
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else CSV_ENTRADA
    todos = carregar_csv(origem)
    prontos = lancaveis(todos)
    destino = DADOS_DIR / f"{origem.stem}_formatado.csv"
    salvar_formatado(prontos, destino)
    print(f"{len(prontos)} aluno(s) formatados e salvos em {destino}:\n")
    print(tabela_texto(adicionar_media(prontos.copy())))
    mostrar_relatorio(todos)
