"""Модуль аутентификации"""

import secrets


class AuthManager:
    def __init__(self):
        self.active_sessions = {}  # {session_token: player_name}

    def create_session(self, player_name):
        """Создание новой сессии"""
        session_token = secrets.token_hex(32)
        self.active_sessions[session_token] = player_name
        return session_token

    def validate_session(self, token, player_name):
        """Проверка валидности сессии"""
        return token in self.active_sessions and self.active_sessions[token] == player_name

    def remove_session(self, token):
        """Удаление сессии"""
        if token in self.active_sessions:
            del self.active_sessions[token]

    def get_player_name(self, token):
        """Получение имени игрока по токену"""
        return self.active_sessions.get(token)