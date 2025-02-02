import tkinter as tk
from tkinter import ttk
import subprocess
import os
import signal
import threading
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import platform



os.environ['PYTHONIOENCODING'] = 'utf-8'
# Armazenar runners globalmente
script_runners = {}

class ScriptRunner:
    def __init__(self, master, script_name, row, col):
        self.master = master
        self.script_name = script_name
        self.process = None
        self.is_running = False

        self.frame = tk.Frame(master)
        self.frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

        self.label_top = tk.Label(self.frame, text=script_name)
        self.label_top.pack()

        self.text_area = tk.Text(self.frame, width=50, height=10)
        self.text_area.pack(fill=tk.BOTH, expand=True)

        self.buttons_frame = tk.Frame(self.frame)
        self.buttons_frame.pack()

        self.start_button = tk.Button(self.buttons_frame, text="Start", command=self.start_script)
        self.start_button.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_button = tk.Button(self.buttons_frame, text="Stop", command=self.stop_script, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT)

        self.restart_button = tk.Button(self.buttons_frame, text="Restart", command=self.restart_script, state=tk.DISABLED)
        self.restart_button.pack(side=tk.LEFT)

    def start_script(self):
        if not self.is_running:
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.restart_button.config(state=tk.NORMAL)
            self.is_running = True
            self.text_area.insert(tk.END, f"Starting {self.script_name}...\n")

            # Determine the Python executable based on the OS
            python_executable = 'python' if platform.system() == 'Windows' else 'python3'

            # Subprocess with unbuffered output and forced UTF-8 encoding
            self.process = subprocess.Popen(
                [python_executable, '-u', self.script_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',  # Force UTF-8 encoding
                errors='replace',  # Replace problematic characters
            )
            self.stdout_thread = threading.Thread(target=self.read_output, args=(self.process.stdout,))
            self.stderr_thread = threading.Thread(target=self.read_output, args=(self.process.stderr,))
            self.stdout_thread.start()

    def stop_script(self):
        if self.is_running:
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.restart_button.config(state=tk.DISABLED)
            self.is_running = False
            self.text_area.insert(tk.END, f"Stopping {self.script_name}...\n")
            os.kill(self.process.pid, signal.SIGTERM)

    def restart_script(self):
        if self.is_running:
            self.stop_script()
        self.start_script()

    def read_output(self, pipe):
        while self.is_running:
            try:
                output = pipe.readline()
                if output:
                    self.text_area.insert(tk.END, output)
                    self.text_area.yview(tk.END)
                else:
                    break
            except Exception as e:
                self.text_area.insert(tk.END, f"Error: {e}\n")

    def stop_if_running(self):
        """Ensure the script is stopped if it's running."""
        if self.is_running:
            self.stop_script()

def stop_all_scripts():
    """Stop all running scripts."""
    for runner in script_runners.values():
        runner.stop_if_running()

def restart_all_scripts():
    for runner in script_runners.values():
        runner.restart_script()

    # Schedule the next restart in 20 minutes
    threading.Timer(20 * 60, restart_all_scripts).start()

def on_closing(root):
    """Handle the window closing event."""
    stop_all_scripts()  # Stop all scripts before closing
    root.destroy()  # Close the application


def restart_telegram_bot():
    runner = script_runners.get("telegrambot.py")
    if runner:
        runner.restart_script()  # Reinicia o telegrambot.py

def restart_IA():
    runner = script_runners.get("IA.py")
    if runner:
        runner.restart_script()

def restart_candles():
    runner = script_runners.get("candles.py")
    if runner:
        runner.restart_script()

def restart_prices_update():
    runner = script_runners.get("prices_update.py")
    if runner:
        runner.restart_script()


def main():
    global script_runners
    script_runners = {}  # Inicializa o dicionário de runners
    root = tk.Tk()
    root.title("Script Runner")

    # Maximizar a janela ao iniciar
    root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")

    # Tornar a grade responsiva
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)

    scripts = ["front_bot.py", "telegrambot.py", "IA.py", "support_bot.py", "candles_iq.py", "prices_update.py"]
    positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2,0), (2,1)]

    for i, script in enumerate(scripts):
        row, col = positions[i]
        runner = ScriptRunner(root, script, row, col)
        script_runners[script] = runner  # Armazena o runner usando o nome do script como chave

    # Iniciar todos os scripts automaticamente
    for runner in script_runners.values():
        runner.start_script()

    # Agendar o reinício apenas do telegrambot.py a cada 20 minutos
    scheduler = BackgroundScheduler()
    scheduler.add_job(restart_candles, IntervalTrigger(minutes=20))
    scheduler.add_job(restart_telegram_bot, IntervalTrigger(minutes=10))
    scheduler.add_job(restart_IA, IntervalTrigger(minutes=43))
    scheduler.start()

    # Vincular o evento de fechamento da janela
    root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root))

    root.mainloop()

if __name__ == "__main__":
    main()
