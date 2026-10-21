@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Instalando o RPA Lançamento de Notas ===

where py >nul 2>nul && (set PY=py) || (
  where python >nul 2>nul && (set PY=python) || (
    echo Python não encontrado. Instale em https://www.python.org/downloads/
    echo e marque "Add python.exe to PATH" na instalação.
    pause
    exit /b 1
  )
)

%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt || (echo Falha ao instalar as bibliotecas. & pause & exit /b 1)

%PY% -c "import rpa_formulario; print('Navegador encontrado:', rpa_formulario.achar_navegador())" || (
  echo Instale o Google Chrome ou o Microsoft Edge.
)
echo.
echo Pronto! Para rodar:  %PY% rpa_formulario.py --csv dados\notas_teste_2alunos.csv --simular
pause
