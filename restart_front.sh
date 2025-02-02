#!/bin/bash

# Fechar todos os processos Python
pkill -f "python"
pkill -f "python3"
pkill -f "py"

# Aguarde um momento para garantir que todos os processos sejam encerrados
sleep 3

# Executar o script front_bot.py com Python 3
python3 front_interface.py &
