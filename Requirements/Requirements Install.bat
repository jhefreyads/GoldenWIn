@echo off
powershell -Command "Get-Content requirements.txt | ForEach-Object { try { pip install --no-cache-dir $_ } catch { Write-Output 'Erro ao instalar $_' } }"
