"""RPA com pyautogui: lê o CSV de notas e preenche o formulário "Lançamento de Notas" por aluno.
As respostas caem na planilha vinculada ao Forms, que depois é consultada com consulta.py.

Como funciona:
  1. Abre o formulário numa janela do Chrome/Edge no canto superior direito da tela.
  2. Calibração automática: o mouse passa sobre a página e o script mede onde ela está na tela.
  3. Para cada aluno o mouse vai até cada campo, clica e digita; depois clica em "Enviar"
     e em "Enviar outra resposta".
  4. Antes de digitar, confere se o campo certo do formulário recebeu o clique.
     Se não recebeu, o RPA para sem digitar nada fora do formulário.

Uso:
    py rpa_formulario.py                       usa dados/notas.csv
    py rpa_formulario.py --csv outro.csv
    py rpa_formulario.py --simular             preenche o 1º aluno e NÃO envia

Segurança: mova o mouse para o canto superior esquerdo da tela para abortar (FAILSAFE).
"""
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pyautogui
import pyperclip
import websocket

import config
from notas import carregar_csv, lancaveis, mostrar_relatorio, tabela_texto

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05

TECLA_CTRL = "command" if sys.platform == "darwin" else "ctrl"
CAMPOS_JS = "[...document.querySelectorAll('div[role=listitem]')].filter(q => q.querySelector('input[type=text]'))"
TITULOS_EQUIVALENTES = {"T02": "TF02"}
BOTAO_ENVIAR_JS = """(() => {
  const botoes = [...document.querySelectorAll('div[role=button]')];
  const porTexto = botoes.find(b => /^(enviar|submit)$/i.test(b.innerText.trim()));
  const perguntas = document.querySelectorAll('div[role=listitem]');
  const ultima = perguntas[perguntas.length - 1];
  return porTexto || botoes.find(b => ultima && (ultima.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING));
})()"""


class FalhaRPA(Exception):
    pass


class Navegador:
    """Conexão com a aba do formulário (DevTools) para ler a posição dos campos na página."""

    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=20, suppress_origin=True)
        self._id = 0

    def js(self, expressao):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": "Runtime.evaluate", "params": {
            "expression": expressao, "returnByValue": True, "awaitPromise": True}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                break
        resultado = msg.get("result", {})
        if "exceptionDetails" in resultado or "error" in msg:
            raise RuntimeError(resultado.get("exceptionDetails") or msg.get("error"))
        return resultado.get("result", {}).get("value")

    def esperar(self, expressao, limite, descricao):
        fim = time.time() + limite
        while time.time() < fim:
            try:
                if self.js(expressao):
                    return
            except (RuntimeError, websocket.WebSocketException):
                pass
            time.sleep(0.3)
        raise FalhaRPA(f"Tempo esgotado esperando: {descricao}")


def achar_navegador():
    if config.NAVEGADOR:
        return config.NAVEGADOR
    local = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    candidatos = {
        "win32": [
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / r"Google\Chrome\Application\chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / r"Google\Chrome\Application\chrome.exe",
            local / r"Google\Chrome\Application\chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")) / r"Microsoft\Edge\Application\msedge.exe",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / r"Microsoft\Edge\Application\msedge.exe",
        ],
        "darwin": [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        ],
    }.get(sys.platform, [])
    for exe in candidatos:
        if exe.exists():
            return str(exe)
    for nome in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge", "chrome", "msedge"):
        if shutil.which(nome):
            return shutil.which(nome)
    raise FalhaRPA("Chrome ou Edge não encontrado. Informe o caminho em NAVEGADOR no config.py.")


def area_de_trabalho():
    """Área útil da tela (sem a barra de tarefas) e escala do sistema. Fora do Windows usa a tela toda."""
    if sys.platform == "win32":
        try:
            from ctypes import wintypes
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0)
            escala = ctypes.windll.user32.GetDpiForSystem() / 96
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top, escala
        except (AttributeError, OSError):
            pass
    largura, altura = pyautogui.size()
    return 0, 0, largura, altura, 1.0


def abrir_navegador():
    """Abre o formulário numa janela no canto superior direito (metade direita da tela)."""
    x, y, largura, altura, escala = area_de_trabalho()
    janela = (int((x + largura / 2) / escala), int(y / escala), int(largura / 2 / escala), int(altura / escala))
    config.PERFIL_NAVEGADOR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([
        achar_navegador(),
        f"--remote-debugging-port={config.PORTA_DEPURACAO}",
        "--remote-allow-origins=*",
        f"--user-data-dir={config.PERFIL_NAVEGADOR}",
        f"--lang={config.IDIOMA_NAVEGADOR}",
        "--no-first-run", "--no-default-browser-check", "--new-window",
        f"--window-position={janela[0]},{janela[1]}",
        f"--window-size={janela[2]},{janela[3]}",
        config.FORM_URL,
    ])

    fim = time.time() + config.TEMPO_CARREGAR_FORM
    while time.time() < fim:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{config.PORTA_DEPURACAO}/json", timeout=2) as r:
                abas = json.load(r)
            aba = next((a for a in abas if a.get("type") == "page" and "docs.google.com/forms" in a.get("url", "")), None)
            if aba:
                return Navegador(aba["webSocketDebuggerUrl"])
        except OSError:
            pass
        time.sleep(0.5)
    raise FalhaRPA("Não consegui conectar ao navegador. Feche as janelas do RPA abertas e tente de novo.")


def esperar_formulario(nav):
    nav.esperar(f"document.readyState === 'complete' && {CAMPOS_JS}.length >= {len(config.COLUNAS)}",
                config.TEMPO_CARREGAR_FORM, "formulário carregar")
    time.sleep(0.5)


class Tela:
    """Converte posição dentro da página (CSS) em posição real na tela (pyautogui)."""

    def __init__(self, nav):
        self.nav = nav
        self.calibrar()

    def _medir(self, x, y):
        """Põe o mouse em (x, y) da tela e lê em que ponto da página ele caiu."""
        self.nav.js("window.__rpaMouse = null; true")
        pyautogui.moveTo(x, y, duration=config.TEMPO_MOVER_MOUSE)
        for passo in range(10):
            pyautogui.moveRel(2 if passo % 2 == 0 else -2, 0, duration=0.05)
            cliente = self.nav.js("window.__rpaMouse")
            if cliente:
                return pyautogui.position(), cliente
            time.sleep(0.2)
        raise FalhaRPA("A janela do formulário não recebeu o mouse. Deixe o navegador visível e tente de novo.")

    def calibrar(self):
        """Mede dois pontos com o mouse: dá a posição da página na tela e a escala (zoom do sistema)."""
        nav = self.nav
        nav.js("if (!window.__rpaOuvindo) { window.__rpaOuvindo = true; addEventListener('mousemove', "
               "e => window.__rpaMouse = [e.clientX, e.clientY], true); } true")
        info = nav.js("({sx: screenX, sy: screenY, ow: outerWidth, oh: outerHeight, "
                      "iw: innerWidth, ih: innerHeight, dpr: devicePixelRatio})")
        estimativa = info["dpr"]
        cx = (info["sx"] + info["ow"] - info["iw"] / 2) * estimativa
        cy = (info["sy"] + info["oh"] - info["ih"] / 2) * estimativa
        print("Calibração automática: movendo o mouse sobre o formulário...")
        p1, c1 = self._medir(cx - 80, cy - 80)
        p2, c2 = self._medir(cx + 80, cy + 80)
        self.escala_x = (p2.x - p1.x) / (c2[0] - c1[0]) if c2[0] != c1[0] else estimativa
        self.escala_y = (p2.y - p1.y) / (c2[1] - c1[1]) if c2[1] != c1[1] else estimativa
        self.origem = (p2.x - c2[0] * self.escala_x, p2.y - c2[1] * self.escala_y)
        print(f"Calibrado: página começa em x={self.origem[0]:.0f}, y={self.origem[1]:.0f} "
              f"(escala {self.escala_x:.2f})")

    def ponto(self, x_css, y_css):
        return self.origem[0] + x_css * self.escala_x, self.origem[1] + y_css * self.escala_y


def mover_para(nav, tela, elemento_js, descricao):
    """Rola até o elemento e move o mouse até o centro dele. Devolve a posição na tela."""
    if not nav.js(f"(() => {{ const el = {elemento_js}; if (!el) return false; "
                  "el.scrollIntoView({block: 'center'}); return true; })()"):
        raise FalhaRPA(f"Não encontrei {descricao} na página.")
    time.sleep(0.4)
    x, y = nav.js(f"(() => {{ const r = ({elemento_js}).getBoundingClientRect(); "
                  "return [r.left + r.width / 2, r.top + r.height / 2]; })()")
    destino = tela.ponto(x, y)
    pyautogui.moveTo(*destino, duration=config.TEMPO_MOVER_MOUSE, tween=pyautogui.easeInOutQuad)
    return destino


def colar(texto):
    pyperclip.copy(texto)
    pyautogui.hotkey(TECLA_CTRL, "v")


def digitar(texto):
    if texto.isascii():
        pyautogui.write(texto, interval=config.INTERVALO_DIGITACAO)
    else:
        colar(texto)


def formatar(valor) -> str:
    if isinstance(valor, float):
        return f"{valor:.2f}"
    return str(valor)


def mapear_campos(nav):
    """Associa cada coluna do CSV à pergunta do formulário pelo título."""
    titulos = nav.js(f"{CAMPOS_JS}.map(q => (q.querySelector('[role=heading]') || q).innerText.split('\\n')[0].trim())")
    normalizar = lambda t: TITULOS_EQUIVALENTES.get(t.upper().replace(" ", ""), t.upper().replace(" ", ""))
    por_titulo = {normalizar(t): i for i, t in enumerate(titulos)}
    faltando = [c for c in config.COLUNAS if normalizar(c) not in por_titulo]
    if faltando:
        raise FalhaRPA(f"Perguntas não encontradas no formulário: {faltando}. Títulos: {titulos}")
    return {c: por_titulo[normalizar(c)] for c in config.COLUNAS}


def preencher_campo(nav, tela, indice, coluna, texto):
    campo = f"{CAMPOS_JS}[{indice}].querySelector('input[type=text]')"
    for tentativa in range(2):
        nav.js("document.activeElement && document.activeElement.blur(); true")
        mover_para(nav, tela, campo, f"o campo {coluna}")
        pyautogui.click()
        time.sleep(config.TEMPO_ENTRE_CAMPOS)
        if nav.js(f"document.hasFocus() && document.activeElement === {campo}"):
            break
        if tentativa == 0:
            tela.calibrar()
    else:
        raise FalhaRPA(f"O clique não acertou o campo {coluna}. Nada foi digitado fora do formulário. "
                       "Deixe a janela do navegador visível (sem nada por cima) e rode de novo.")

    pyautogui.hotkey(TECLA_CTRL, "a")
    digitar(texto)
    time.sleep(config.TEMPO_ENTRE_CAMPOS)
    valor = nav.js(f"{campo}.value")
    if valor != texto:
        pyautogui.hotkey(TECLA_CTRL, "a")
        colar(texto)
        time.sleep(config.TEMPO_ENTRE_CAMPOS)
        valor = nav.js(f"{campo}.value")
    if valor != texto:
        raise FalhaRPA(f"Campo {coluna}: esperado '{texto}', ficou '{valor}'.")


def enviar(nav, tela):
    mover_para(nav, tela, BOTAO_ENVIAR_JS, "o botão Enviar")
    pyautogui.click()
    try:
        nav.esperar("location.href.includes('formResponse') || !document.querySelector('div[role=listitem]')",
                    config.TEMPO_APOS_ENVIAR, "confirmação do envio")
    except FalhaRPA:
        erros = nav.js("[...document.querySelectorAll('[role=alert]')].map(e => e.innerText).filter(Boolean)")
        raise FalhaRPA(f"O formulário não confirmou o envio. Mensagens na página: {erros}")


def nova_resposta(nav, tela):
    link = ("(document.querySelector('a[href*=\"usp=form_confirm\"]') || "
            "[...document.querySelectorAll('a')].find(a => /outra resposta|another response/i.test(a.innerText)))")
    if nav.js(f"!!{link}"):
        mover_para(nav, tela, link, "o link Enviar outra resposta")
        pyautogui.click()
    else:
        nav.js(f"location.href = {json.dumps(config.FORM_URL)}; true")
    time.sleep(1)
    esperar_formulario(nav)


def main():
    parser = argparse.ArgumentParser(description="Preenche o Google Forms com as notas do CSV.")
    parser.add_argument("--csv", default=config.CSV_ENTRADA, help="arquivo CSV de notas")
    parser.add_argument("--simular", action="store_true", help="preenche o 1º aluno e não envia")
    args = parser.parse_args()

    try:
        todos = carregar_csv(args.csv)
    except ValueError as erro:
        raise FalhaRPA(f"CSV com problema: {erro}") from None
    df = lancaveis(todos)
    print("Notas formatadas que serão lançadas:\n")
    print(tabela_texto(df))
    mostrar_relatorio(todos)
    if df.empty:
        raise FalhaRPA("Nenhum aluno pronto para lançar.")
    if args.simular:
        df = df.head(1)
    print(f"\n{len(df)} aluno(s) para lançar. Não mexa no mouse/teclado "
          "(canto superior esquerdo da tela = abortar).")

    nav = abrir_navegador()
    esperar_formulario(nav)
    tela = Tela(nav)
    campos = mapear_campos(nav)

    for n, (_, aluno) in enumerate(df.iterrows(), start=1):
        if n > 1:
            nova_resposta(nav, tela)
        for coluna in config.COLUNAS:
            preencher_campo(nav, tela, campos[coluna], coluna, formatar(aluno[coluna]))
        if args.simular:
            print(f"[SIMULAÇÃO] RA {aluno['RA']} - {aluno['Nome']} preenchido, NÃO enviado.")
            return
        enviar(nav, tela)
        print(f"[{n}/{len(df)}] RA {aluno['RA']} - {aluno['Nome']} enviado")

    print("Lançamento concluído.")


if __name__ == "__main__":
    try:
        main()
    except pyautogui.FailSafeException:
        sys.exit("\nRPA interrompido pelo usuário (FAILSAFE).")
    except FalhaRPA as erro:
        sys.exit(f"\nRPA parou: {erro}")
