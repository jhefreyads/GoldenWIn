import tkinter as tk
from tkinter import ttk
import pandas as pd
import sqlite3
from datetime import datetime
import subprocess
import os
import signal
import threading
import time
import json

CONFIG_FILE = "config.json"

class ScriptRunner:
    def __init__(self, master, script_name, display_name, row, col):
        self.master = master
        self.script_name = script_name
        self.display_name = display_name
        self.process = None
        self.is_running = False
        self.restart_interval = tk.IntVar(value=30)  # Intervalo de reinício em minutos
        self.auto_restart = tk.BooleanVar(value=True)  # Se deve reiniciar automaticamente

        self.frame = tk.Frame(master)
        self.frame.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')

        self.label_top = tk.Label(self.frame, text=display_name)
        self.label_top.pack()

        self.text_area = tk.Text(self.frame, width=50, height=10)
        self.text_area.pack(expand=True, fill='both')

        self.buttons_frame = tk.Frame(self.frame)
        self.buttons_frame.pack()

        self.start_button = tk.Button(self.buttons_frame, text="Start", command=self.start_script)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = tk.Button(self.buttons_frame, text="Stop", command=self.stop_script, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        # Iniciar script ao iniciar o programa
        self.start_script()

    def create_table(self, parent):
        self.tree = ttk.Treeview(parent, columns=("ID", "Symbol", "Direction", "Timeframe", "Time", "Result", "Message ID", "Sent", "Edited"), show='headings')
        self.tree.heading("ID", text="ID")
        self.tree.column("ID", anchor=tk.CENTER, width=50)
        self.tree.heading("Symbol", text="Symbol")
        self.tree.column("Symbol", anchor=tk.CENTER, width=100)
        self.tree.heading("Direction", text="Direction")
        self.tree.column("Direction", anchor=tk.CENTER, width=100)
        self.tree.heading("Timeframe", text="Timeframe")
        self.tree.column("Timeframe", anchor=tk.CENTER, width=100)
        self.tree.heading("Time", text="Time")
        self.tree.column("Time", anchor=tk.CENTER, width=100)
        self.tree.heading("Result", text="Result")
        self.tree.column("Result", anchor=tk.CENTER, width=100)
        self.tree.heading("Message ID", text="Message ID")
        self.tree.column("Message ID", anchor=tk.CENTER, width=100)
        self.tree.heading("Sent", text="Sent")
        self.tree.column("Sent", anchor=tk.CENTER, width=200)
        self.tree.heading("Edited", text="Edited")
        self.tree.column("Edited", anchor=tk.CENTER, width=200)
        self.tree.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky='nsew')

        self.update_table()

    def update_table(self):
        conn = sqlite3.connect("signals.db")
        df = pd.read_sql_query("SELECT * FROM trading_signals ORDER BY id DESC LIMIT 100", conn)
        conn.close()

        # Identify float columns and object columns separately
        float_columns = df.select_dtypes(include=['float64']).columns
        object_columns = df.select_dtypes(exclude=['float64']).columns

        # Fill NaN in float columns with 0 or another appropriate value
        df[float_columns] = df[float_columns].fillna(0)

        # Convert object columns to object type (if not already) and fill NaN with an empty string
        df[object_columns] = df[object_columns].astype(object).fillna("")

        self.tree.delete(*self.tree.get_children())

        for i, row in df.iterrows():
            # Supondo que "formatted_time" é uma string no formato americano (ex: "2024-06-09 15:30:00")
            formatted_time = row["time"]
            
            # Converter a string para um objeto datetime
            datetime_obj = datetime.strptime(formatted_time, "%Y-%m-%d %H:%M:%S")
            
            # Formatar a data para HH:MM
            formatted_time = datetime_obj.strftime("%H:%M")
            
            self.tree.insert("", "end", values=(row["id"], row["symbol"], row["direction"], row["timeframe"], formatted_time, row["result"], row["message_id"], row["sent"], row["edited"]))

        self.master.after(1000, self.update_table)

    def start_script(self):
        if not self.is_running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.is_running = True
            self.text_area.insert(tk.END, f"Starting {self.display_name}...\n")
            self.process = subprocess.Popen(['python', self.script_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, universal_newlines=True, encoding='utf-8', errors='replace')
            self.thread = threading.Thread(target=self.read_output)
            self.thread.start()
            if self.auto_restart.get():
                self.master.after(self.restart_interval.get() * 60 * 1000, self.restart_script)

    def restart_script(self):
        if self.is_running and self.auto_restart.get():
            self.stop_script()
            time.sleep(1)
            self.start_script()

    def stop_script(self):
        if self.is_running:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.is_running = False
            self.text_area.insert(tk.END, f"Stopping {self.display_name}...\n")
            if self.process:
                os.kill(self.process.pid, signal.SIGTERM)
                self.process = None
            self.text_area.delete("1.0", tk.END)  # Limpa o console ao parar o script

    def read_output(self):
        while self.is_running:
            if self.process:
                output = self.process.stdout.readline()
                if output:
                    self.text_area.insert(tk.END, output)
                    self.text_area.yview(tk.END)
                if self.process and self.process.poll() is not None:
                    break
            else:
                break
            time.sleep(0.1)  # Evita uso excessivo da CPU

def save_config(script_runners):
    config = {}
    for runner in script_runners:
        config[runner.script_name] = {
            "auto_restart": runner.auto_restart.get(),
            "restart_interval": runner.restart_interval.get()
        }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def load_config(script_runners):
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        for runner in script_runners:
            if runner.script_name in config:
                runner.auto_restart.set(config[runner.script_name]["auto_restart"])
                runner.restart_interval.set(config[runner.script_name]["restart_interval"])

def main():
    root = tk.Tk()
    root.title("Script Runner")
    root.state('zoomed')  # Inicia maximizado

    notebook = ttk.Notebook(root)
    notebook.pack(expand=True, fill='both')

    # Frame para execução de scripts
    frame_scripts = tk.Frame(notebook)
    frame_scripts.grid_rowconfigure(0, weight=1)
    frame_scripts.grid_columnconfigure(0, weight=1)
    frame_scripts.grid_rowconfigure(1, weight=1)
    frame_scripts.grid_columnconfigure(1, weight=1)

    # Mapeamento dos nomes dos arquivos para nomes amigáveis
    scripts_info = [
        ("ia.py", "IA"),
        ("telegrambot.py", "Telegram"),
        ("candles.py", "Candles MT5"),
        ("candles_iq.py", "Candles OTC"),
        ("bothtml.py", "HTML")
    ]
    positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)]

    script_runners = []
    for i, (script, display_name) in enumerate(scripts_info):
        row, col = positions[i]
        runner = ScriptRunner(frame_scripts, script, display_name, row, col)
        script_runners.append(runner)

    load_config(script_runners)  # Carregar configurações ao iniciar

    # Frame para configurações
    frame_config = tk.Frame(notebook)
    frame_config.grid_rowconfigure(0, weight=1)
    frame_config.grid_columnconfigure(0, weight=1)

    for i, runner in enumerate(script_runners):
        config_frame = tk.LabelFrame(frame_config, text=runner.display_name)
        config_frame.grid(row=i, column=0, padx=5, pady=5, sticky='nsew')

        auto_restart_check = tk.Checkbutton(config_frame, text="Auto Restart", variable=runner.auto_restart)
        auto_restart_check.pack(side=tk.LEFT, padx=5, pady=5)

        restart_interval_label = tk.Label(config_frame, text="Restart Interval (min):")
        restart_interval_label.pack(side=tk.LEFT, padx=5, pady=5)

        restart_interval_entry = tk.Entry(config_frame, textvariable=runner.restart_interval)
        restart_interval_entry.pack(side=tk.LEFT, padx=5, pady=5)

    save_button = tk.Button(frame_config, text="Save Configurations", command=lambda: save_config(script_runners))
    save_button.grid(row=len(script_runners), column=0, pady=10)

    notebook.add(frame_scripts, text="Scripts")
    notebook.add(frame_config, text="Configurações")

    # Criar tabela na aba de scripts
    if script_runners:
        script_runners[0].create_table(frame_scripts)

    root.mainloop()

if __name__ == "__main__":
    main()
