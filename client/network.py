"""Модуль сетевого взаимодействия"""

import socket
import json
import threading


class NetworkClient:
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.running = False
        self.message_handler = None

    def connect(self):
        """Подключение к серверу"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.running = True
            threading.Thread(target=self._receive_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False

    def _receive_loop(self):
        """Цикл приема сообщений"""
        while self.running:
            try:
                data = self.socket.recv(4096).decode().strip()
                if not data:
                    break
                for line in data.split('\n'):
                    if line and self.message_handler:
                        msg = json.loads(line)
                        self.message_handler(msg)
            except Exception:
                break
        self.connected = False

    def send(self, data):
        """Отправка данных на сервер"""
        if not self.connected:
            return False
        try:
            self.socket.send((json.dumps(data) + "\n").encode())
            return True
        except:
            self.connected = False
            return False

    def disconnect(self):
        """Отключение от сервера"""
        self.running = False
        if self.socket:
            self.socket.close()