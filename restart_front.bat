@echo off
REM Fecha todos os processos python.exe
taskkill /IM python.exe /F

REM Aguarda um momento para garantir que o processo foi fechado
timeout /t 2 /nobreak

REM Inicia o novo script Python
start python "front_bot.py"

REM Fecha a janela do arquivo batch após a execução
exit
