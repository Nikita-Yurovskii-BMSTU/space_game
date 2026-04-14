"""Модуль управления состоянием клиента"""

from collections import deque
from common.protocols import *


class ClientState:
    def __init__(self):
        self.player = "Неизвестно"
        self.coordinates = DEFAULT_COORDINATES.copy()
        self.hull = DEFAULT_HULL.copy()
        self.inventory = DEFAULT_INVENTORY.copy()
        self.weapons = DEFAULT_WEAPONS.copy()
        self.stats = DEFAULT_STATS.copy()
        self.logs = deque(maxlen=50)

    def update_full(self, data):
        """Полное обновление состояния"""
        if 'player' in data:
            self.player = data['player']
        if 'coordinates' in data:
            self.coordinates = data['coordinates']
        if 'hull' in data:
            self.hull = data['hull']
        if 'inventory' in data:
            self.inventory = data['inventory']
        if 'weapons' in data:
            self.weapons = data['weapons']
        if 'stats' in data:
            self.stats = data['stats']

    def update_partial(self, data):
        """Частичное обновление состояния"""
        if 'coordinates' in data:
            self.coordinates.update(data['coordinates'])
        if 'hull' in data:
            for k, v in data['hull'].items():
                old = self.hull.get(k, 100)
                self.hull[k] = v
                if v < old:
                    self.add_log(f"[red]💥 Повреждение {k}: {v}%[/red]")
        if 'inventory' in data:
            self.inventory.update(data['inventory'])
        if 'weapons' in data:
            self.weapons.update(data['weapons'])
        if 'stats' in data:
            self.stats.update(data['stats'])

    def add_log(self, text):
        """Добавление записи в лог"""
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.logs.append(f"[dim]{timestamp}[/dim] {text}")