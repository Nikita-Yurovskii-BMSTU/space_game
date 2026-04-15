"""Основной класс игрового клиента"""

import threading
import sys
import select
import time
from rich.live import Live
from rich.console import Console

from client.network import NetworkClient
from client.state import ClientState
from client.ui import GameUI
from common.protocols import *

console = Console()


class GameClient:
    def __init__(self, host='localhost', port=5555):
        self.network = NetworkClient(host, port)
        self.state = ClientState()
        self.ui = GameUI(self.state)
        self.session_token = None
        self.running = False

        # Привязываем обработчик сообщений
        self.network.message_handler = self.process_message

    def connect(self):
        """Подключение к серверу"""
        return self.network.connect()

    def process_message(self, msg):
        """Обработка входящих сообщений"""
        msg_type = msg.get('type', '')
        print(f"[DEBUG] Клиент получил: {msg_type}")

        if msg_type == MSG_AUTH:
            self.state.add_log(f"[yellow]{msg.get('message', '')}[/yellow]")

        elif msg_type == MSG_AUTH_SUCCESS:
            self.session_token = msg.get('token')
            self.ui.authenticated = True
            self.state.add_log(f"[green]{msg.get('message', '')}[/green]")

        elif msg_type == MSG_GAME_STATE:
            self.state.update_full(msg.get('data', {}))
            self.state.add_log("[green]✓ Игровые данные загружены[/green]")

        elif msg_type == MSG_UPDATE:
            self.state.update_partial(msg.get('data', {}))

        elif msg_type == MSG_MESSAGE:
            self.state.add_log(f"[cyan]{msg.get('data', '')}[/cyan]")

        elif msg_type == MSG_COOLDOWN:
            self.ui.set_cooldown(
                msg.get('remaining', 3),
                msg.get('message', '')
            )

        elif msg_type == MSG_WEAPON_COOLDOWN:
            self.ui.set_weapon_cooldown(
                msg.get('weapon', ''),
                msg.get('remaining', 0),
                msg.get('message', '')
            )

        elif msg_type == "overview":
            self.state.overview = msg.get('data', [])
            self.state.add_log(f"[green]✓ Обзор обновлён: {len(self.state.overview)} объектов[/green]")

        elif msg_type == "target":
            self.state.target = msg.get('target')
            if msg.get('target'):
                self.state.add_log(f"[cyan]🎯 Цель: {msg.get('target')}[/cyan]")
            else:
                self.state.add_log(f"[yellow]🎯 Цель сброшена[/yellow]")

        elif msg_type == MSG_ERROR:
            self.state.add_log(f"[red]Ошибка: {msg.get('data', '')}[/red]")

    def send_command(self, cmd):
        """Отправка команды на сервер"""
        if not self.network.connected:
            self.state.add_log("[red]Нет соединения[/red]")
            return

        if not self.ui.authenticated:
            data = {"cmd": cmd}
        else:
            self.state.add_log(f"[yellow]>> {cmd}[/yellow]")
            data = {"cmd": cmd, "token": self.session_token}

        self.network.send(data)

    def run(self):
        """Запуск клиента"""
        if not self.connect():
            return

        self.running = True

        console.clear()
        console.print("[bold cyan]Добро пожаловать в космический симулятор![/bold cyan]")
        console.print("Для входа используйте: [yellow]login имя_пользователя пароль[/yellow]")
        console.print("Для регистрации: [yellow]register имя_пользователя пароль[/yellow]")
        console.print("[dim]⚠️ После каждой команды будет кулдаун 3 секунды[/dim]\n")

        with Live(self.ui.draw_layout(), refresh_per_second=20, screen=True) as live:
            def input_thread():
                while self.running:
                    try:
                        if select.select([sys.stdin], [], [], 0.1)[0]:
                            cmd = sys.stdin.readline().strip()
                            if cmd:
                                self.ui.current_input = cmd
                                live.update(self.ui.draw_layout())

                                if cmd == CMD_QUIT:
                                    self.send_command(cmd)
                                    self.running = False
                                    break

                                self.send_command(cmd)
                                live.update(self.ui.draw_layout())  # ← принудительно обновляем сразу
                                self.ui.current_input = ""
                                live.update(self.ui.draw_layout())
                    except:
                        break

            t = threading.Thread(target=input_thread, daemon=True)
            t.start()

            while self.running and self.network.connected:
                live.update(self.ui.draw_layout())
                time.sleep(0.05)

        self.network.disconnect()
        console.print("\n[yellow]Отключено[/yellow]")