"""Основной класс игрового сервера"""

import socket
import threading
import json
from server.database import Database
from server.auth import AuthManager
from server.game_logic import GameLogic
from server.data_loader import DataLoader
from common.protocols import *


class GameServer:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.running = False

        self.db = Database()
        self.auth = AuthManager()
        self.data = DataLoader()
        self.logic = GameLogic(self.db, self.data)

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        print(f"✓ Сервер запущен на {self.host}:{self.port}")
        print("Ожидание подключения игроков...")

        while self.running:
            client, addr = self.server_socket.accept()
            print(f"Новое подключение от {addr}")
            threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()

    def handle_client(self, client):
        # Этап 1: Аутентификация
        authenticated = False
        player_name = None
        token = None

        client.send((json.dumps({
            "type": MSG_AUTH,
            "message": "Введите команду: login или register"
        }) + "\n").encode())

        while not authenticated:
            try:
                data = client.recv(4096).decode().strip()
                if not data:
                    break

                msg = json.loads(data)
                cmd = msg.get('cmd', '')

                if cmd.startswith(CMD_REGISTER):
                    parts = cmd.split()
                    if len(parts) == 3:
                        _, username, password = parts
                        success, message = self.db.create_player(username, password)
                        client.send((json.dumps({
                            "type": MSG_AUTH,
                            "message": message
                        }) + "\n").encode())
                        if success:
                            client.send((json.dumps({
                                "type": MSG_AUTH,
                                "message": "Теперь войдите: login имя_пользователя пароль"
                            }) + "\n").encode())
                    else:
                        client.send((json.dumps({
                            "type": MSG_AUTH,
                            "message": "Использование: register имя_пользователя пароль"
                        }) + "\n").encode())

                elif cmd.startswith(CMD_LOGIN):
                    parts = cmd.split()
                    if len(parts) == 3:
                        _, username, password = parts
                        player_id = self.db.verify_player(username, password)
                        if player_id:
                            authenticated = True
                            player_name = username
                            token = self.auth.create_session(player_name)

                            client.send((json.dumps({
                                "type": MSG_AUTH_SUCCESS,
                                "token": token,
                                "message": f"Добро пожаловать, {player_name}!"
                            }) + "\n").encode())

                            state = self.db.load_state(player_name)
                            if state:
                                client.send((json.dumps({
                                    "type": MSG_GAME_STATE,
                                    "data": state
                                }) + "\n").encode())
                        else:
                            client.send((json.dumps({
                                "type": MSG_AUTH,
                                "message": "Неверное имя пользователя или пароль!"
                            }) + "\n").encode())
                    else:
                        client.send((json.dumps({
                            "type": MSG_AUTH,
                            "message": "Использование: login имя_пользователя пароль"
                        }) + "\n").encode())

                else:
                    client.send((json.dumps({
                        "type": MSG_AUTH,
                        "message": "Сначала войдите или зарегистрируйтесь!"
                    }) + "\n").encode())

            except Exception as e:
                print(f"Ошибка аутентификации: {e}")
                break

        if not authenticated:
            client.close()
            return

        # Этап 2: Игровой цикл
        print(f"Игрок {player_name} вошел в игру")
        state = self.db.load_state(player_name)
        last_state = state.copy() if state else None

        while self.running:
            try:
                data = client.recv(4096).decode().strip()
                if not data:
                    break

                msg = json.loads(data)
                cmd = msg.get('cmd', '')
                client_token = msg.get('token', '')

                if not self.auth.validate_session(client_token, player_name):
                    client.send((json.dumps({
                        "type": MSG_ERROR,
                        "data": "Недействительная сессия"
                    }) + "\n").encode())
                    break

                response = self.logic.process_command(cmd, state, player_name)

                if response and isinstance(response, dict):
                    # Проверка на кулдаун (отказ)
                    if response.get("cooldown"):
                        client.send((json.dumps({
                            "type": MSG_COOLDOWN,
                            "remaining": response["remaining"],
                            "message": response["message"]
                        }) + "\n").encode())
                        continue

                    # Проверка на кулдаун оружия (отказ)
                    if response.get("weapon_cooldown"):
                        client.send((json.dumps({
                            "type": MSG_WEAPON_COOLDOWN,
                            "weapon": response["weapon"],
                            "remaining": response["remaining"],
                            "message": response["message"]
                        }) + "\n").encode())
                        continue

                    # Отправка изменений состояния
                    if 'state' in response:
                        new_state = response['state']
                        if new_state != last_state:
                            self.db.save_state(new_state)
                            changes = self.logic.get_changes(last_state, new_state)
                            if changes:
                                client.send((json.dumps({
                                    "type": MSG_UPDATE,
                                    "data": changes
                                }) + "\n").encode())
                            last_state = new_state.copy()
                            state = new_state

                    # Отправка сообщения
                    if 'message' in response:
                        client.send((json.dumps({
                            "type": MSG_MESSAGE,
                            "data": response['message']
                        }) + "\n").encode())

                    # Отправка глобального кулдауна после выполнения
                    if response.get("cooldown_after"):
                        cd = response["cooldown_after"]
                        client.send((json.dumps({
                            "type": MSG_COOLDOWN,
                            "remaining": cd["remaining"],
                            "message": cd["message"]
                        }) + "\n").encode())

                    # Отправка кулдауна оружия после выстрела
                    if response.get("weapon_cooldown_after"):
                        wc = response["weapon_cooldown_after"]
                        client.send((json.dumps({
                            "type": MSG_WEAPON_COOLDOWN,
                            "weapon": wc["weapon"],
                            "remaining": wc["remaining"],
                            "message": wc["message"]
                        }) + "\n").encode())

            except Exception as e:
                print(f"Ошибка в игровом цикле {player_name}: {e}")
                break

        self.auth.remove_session(token)
        client.close()
        print(f"Игрок {player_name} отключился")

    def stop(self):
        self.running = False
        if hasattr(self, 'server_socket'):
            self.server_socket.close()