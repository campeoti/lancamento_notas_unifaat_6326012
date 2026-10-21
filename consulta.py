"""Consulta de notas por RA ou Nome no terminal, com estatísticas da turma.

Uso:
    py consulta.py                                 modo interativo
    py consulta.py 100001                          busca por RA
    py consulta.py "ana oliveira"                  busca por nome (ou parte do nome)
    py consulta.py "SEM RA"                        alunos lançados sem RA
    py consulta.py --fonte dados/respostas.xlsx    outra fonte (link do Sheets, .xlsx ou .csv)

Lê a planilha de respostas do Forms definida em config.py (PLANILHA_URL ou EXCEL_RESPOSTAS).
"""
import argparse
import unicodedata

from config import NOTA_CORTE
from notas import carregar_respostas, formatar_ra, sem_ra, tabela_texto


def sem_acento(texto) -> str:
    texto = unicodedata.normalize("NFD", str(texto))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower().split()


def exibir(aluno):
    print("-" * 40)
    print(f"RA          : {aluno['RA']}")
    print(f"Nome        : {aluno['Nome']}")
    print(f"Nota 1      : {aluno['Nota 1']:.2f}")
    print(f"Nota 2      : {aluno['Nota 2']:.2f}")
    print(f"TF01        : {aluno['TF01']:.2f}")
    print(f"TF02        : {aluno['TF02']:.2f}")
    print(f"Média Final : {aluno['Média Final']:.2f}")
    print(f"Situação    : {aluno['Situação']}")
    print("-" * 40)


def estatisticas(df):
    if df.empty:
        print("\nNenhum aluno lançado na planilha.")
        return
    aprovados = (df["Situação"] == "APROVADO").sum()
    reprovados = len(df) - aprovados
    melhor = df.loc[df["Média Final"].idxmax()]
    pior = df.loc[df["Média Final"].idxmin()]
    print("\n=== ESTATÍSTICAS DA TURMA ===")
    print(f"Alunos lançados  : {len(df)}")
    print(f"Aprovados        : {aprovados} ({aprovados / len(df):.0%})")
    print(f"Reprovados       : {reprovados} ({reprovados / len(df):.0%})")
    print(f"Nota de corte    : {NOTA_CORTE:.2f}")
    print(f"Média da turma   : {df['Média Final'].mean():.2f}")
    print(f"Maior média      : {melhor['Média Final']:.2f} - {melhor['Nome']} (RA {melhor['RA']})")
    print(f"Menor média      : {pior['Média Final']:.2f} - {pior['Nome']} (RA {pior['RA']})")
    print(f"Média Nota 1     : {df['Nota 1'].mean():.2f}")
    print(f"Média Nota 2     : {df['Nota 2'].mean():.2f}")
    print(f"Média TF01       : {df['TF01'].mean():.2f}")
    print(f"Média TF02       : {df['TF02'].mean():.2f}")


def mostrar_sem_ra(lista, completo=False):
    if lista.empty:
        print("\nNenhum aluno SEM RA.")
        return
    print(f"\nATENÇÃO: {len(lista)} aluno(s) lançados SEM RA (verificar o RA com a secretaria):\n")
    if completo:
        for _, aluno in lista.iterrows():
            exibir(aluno)
    else:
        print(tabela_texto(lista[["Nome", "Nota 1", "Nota 2", "TF01", "TF02", "Média Final", "Situação"]]))


def buscar(df, termo):
    if any(c.isdigit() for c in termo):
        resultado = df[df["RA"] == formatar_ra(termo)]
    else:
        palavras = sem_acento(termo)
        resultado = df[df["Nome"].map(lambda nome: all(p in " ".join(sem_acento(nome)) for p in palavras))]
    if resultado.empty:
        print(f"Nenhum aluno encontrado para '{termo}'.")
        return
    if len(resultado) > 1:
        print(f"{len(resultado)} aluno(s) encontrados:")
    for _, aluno in resultado.iterrows():
        exibir(aluno)


def executar(df, termo):
    comando = termo.upper().replace(" ", "")
    if comando == "SEMRA":
        mostrar_sem_ra(sem_ra(df), completo=True)
    elif comando in ("ESTATISTICAS", "ESTATÍSTICAS", "EST"):
        estatisticas(df)
    else:
        buscar(df, termo)


def main():
    parser = argparse.ArgumentParser(description="Consulta notas pelo RA ou Nome.")
    parser.add_argument("termo", nargs="?", help="RA, nome do aluno, SEM RA ou ESTATISTICAS")
    parser.add_argument("--fonte", help="link do Google Sheets, .xlsx ou .csv (padrão: config.py)")
    args = parser.parse_args()

    df = carregar_respostas(args.fonte)

    if args.termo:
        executar(df, args.termo)
        return

    print(f"=== CONSULTA DE NOTAS ===  {len(df)} aluno(s) na planilha")
    estatisticas(df)
    mostrar_sem_ra(sem_ra(df))
    print("\nDigite o RA ou o Nome do aluno. Comandos: SEM RA, ESTATISTICAS. ENTER vazio para sair.")
    while True:
        termo = input("\nBuscar (RA ou Nome): ").strip()
        if not termo:
            break
        executar(df, termo)


if __name__ == "__main__":
    main()
