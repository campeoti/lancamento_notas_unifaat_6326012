# Lançamento de Notas - RPA com PyAutoGUI

Fluxo: **CSV → RPA (pyautogui) preenche o Google Forms → respostas caem na planilha (Excel/Sheets) → consulta por RA no terminal.**

## Instalação (qualquer computador)
Requisitos: **Python 3.9+** e **Google Chrome ou Microsoft Edge**.

1. Copie/clone esta pasta para o computador.
2. No Windows, dê dois cliques em **`instalar.bat`** (instala as bibliotecas e verifica o navegador).
   Ou, em qualquer sistema:
   ```bash
   py -m pip install -r requirements.txt
   ```
3. Teste sem enviar nada:
   ```bash
   py rpa_formulario.py --csv dados/notas_teste_2alunos.csv --simular
   ```
> No Windows, se `python` abrir a Microsoft Store, use `py` no lugar. No Mac/Linux use `python3`.

O RPA se adapta sozinho a cada máquina: resolução, zoom do Windows (100%/125%/150%), posição da janela,
idioma do navegador e layout do teclado (se a digitação sair diferente, ele corrige colando o valor).
Não precisa ajustar coordenadas. No **Mac**, dê permissão de *Acessibilidade* ao Terminal/VS Code
(Ajustes do Sistema > Privacidade e Segurança) para o pyautogui controlar o mouse.

Em `config.py`:
- `FORM_URL`: link público do formulário (já configurado).
- `PLANILHA_URL`: link da planilha de respostas vinculada ao Forms (compartilhada como
  "Qualquer pessoa com o link: Leitor"). **Ou** deixe vazio e baixe a planilha em
  *Arquivo > Fazer download > .xlsx* para `dados/respostas.xlsx`.

## 1. RPA - lançar as notas do CSV no formulário
Coloque o CSV recebido em `dados/notas.csv` (colunas RA, Nome, Nota 1, Nota 2, TF01, TF02).
O CSV pode vir bagunçado: separador `,` ou `;`, notas com vírgula ou ponto, várias casas decimais, espaços,
aspas, nomes em maiúsculas/minúsculas, cabeçalho escrito diferente (`nota1`, `tf 01`) e arquivo salvo pelo Excel.
O código formata tudo para o padrão `9.25` antes de lançar. Para ver a formatação sem lançar:
```bash
py notas.py
```
Mostra o CSV original, o formatado com média e situação, e salva `dados/notas_formatado.csv`.
O `dados/notas.csv` já vem com 10 alunos fictícios em formato bagunçado para teste.
```bash
py rpa_formulario.py
```
Sem nenhuma interação:
1. Abre o formulário numa janela do Chrome/Edge na metade direita da tela (perfil separado, só do RPA).
2. **Calibração automática**: o mouse passa sobre a página e o script mede a posição dela na tela.
3. Para cada aluno, o mouse vai até cada campo, clica e digita; clica em **Enviar** e em **Enviar outra resposta**.
4. Antes de digitar, confere se o clique caiu no campo certo; se não, para sem digitar fora do formulário.

Cada envio cai na planilha de respostas do Forms. Para testar sem enviar:
```bash
py rpa_formulario.py --csv dados/notas_teste_2alunos.csv --simular
```
**Para abortar, jogue o mouse no canto superior esquerdo da tela.**

## 2. Consulta por RA ou Nome (lê a planilha de respostas pelo link)
```bash
py consulta.py                    # interativo: estatísticas + alunos SEM RA + busca
py consulta.py 100001             # por RA (aceita RA0100001, 100019-0...)
py consulta.py "ana oliveira"     # por nome ou parte do nome, sem diferenciar acento/maiúscula
py consulta.py "SEM RA"           # alunos lançados sem RA
py consulta.py ESTATISTICAS       # estatísticas da turma
```
Mostra RA, Nome, Nota 1, Nota 2, TF01, TF02, Média Final e Situação (APROVADO/REPROVADO).
Estatísticas: total, aprovados/reprovados (%), média da turma, maior e menor média, média de cada nota.
Se o mesmo aluno foi enviado mais de uma vez, vale o último envio.

## Média final
Formato das notas: ponto decimal, 2 casas (ex.: `9.25`).
Nota 1 e Nota 2 vão de 0 a 10; TF01 e TF02 vão de 0 a 2. O RPA recusa o CSV se alguma nota estiver fora da faixa.

`Média Final = média(Nota 1, Nota 2) × 0.8 + média(TF01, TF02)` → provas valem até 8, TF até 2, total 10.

Exemplo: provas 9.25 e 8.50, TF 1.75 e 2.00 → 8.875 × 0.8 + 1.875 = **8.98**.

**Nota de corte: 7.** Média final maior ou igual a 7 → **APROVADO**; abaixo de 7 → **REPROVADO**
(mostrado na consulta; ajuste em `NOTA_CORTE` no `config.py`).

## Regras de formatação do CSV
- Colunas reconhecidas pelo nome, em qualquer ordem (`Nome;RA;Nota01;TF01;Nota02;TF02` funciona).
- Notas com ponto e 2 casas; `FALTOU`, `falta`, `N/A`, `-` e em branco viram `0.00`.
- Nota acima do limite vira o limite (prova 12 → 10, TF 4 → 2).
- RA só com números, juntos e sem zero à esquerda (`RA0100001` → `100001`, `100019-0` → `1000190`).
- Aluno sem RA é lançado com **`SEM RA`** no campo RA (o RA é obrigatório no formulário).
  Na consulta eles aparecem em destaque ao abrir; digite `SEM RA` para ver a ficha completa.
