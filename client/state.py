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
        self.logs = deque(maxlen=100)  # храним больше строк
        self.log_scroll_offset = 0  # 0 = показываем последние строки
        self.ship = {"ship_id": "fighter", "hull": {}, "installed_weapons": []}
        self.overview = []  # список объектов вокруг
        self.target = None  # текущая цель


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
        if 'ship' in data:
            self.ship = data['ship']

    def update_partial(self, data):
        """Частичное обновление состояния"""
        if 'coordinates' in data:
            for k, v in data['coordinates'].items():
                self.coordinates[k] = v
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
        if 'ship' in data:
            if 'ship' not in self.__dict__:
                self.ship = {}
            if 'hull' in data['ship']:
                for k, v in data['ship']['hull'].items():
                    old = self.hull.get(k, 100)
                    self.hull[k] = v
            if 'installed_weapons' in data['ship']:
                self.ship['installed_weapons'] = data['ship']['installed_weapons']

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
        from datetime import datetime
        timestamp = datetime.now().strftime('%H:%M:%S')
        lines = text.split('\n')
        for i, line in enumerate(reversed(lines)):  # разворачиваем чтобы первая строка была сверху
            if i == 0:
                self.logs.appendleft(f"[dim]{timestamp}[/dim] {line}")
            else:
                self.logs.appendleft(f"   {line}")