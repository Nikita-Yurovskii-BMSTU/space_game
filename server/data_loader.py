"""Загрузчик данных из JSON"""

import json
import os


class DataLoader:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.ships = {}
        self.weapons = {}
        self.systems = {}
        self.enemies = {}  # ← добавить
        self.load_all()

    def load_all(self):
        self.ships = self.load_json("ships.json")
        self.weapons = self.load_json("weapons.json")
        self.systems = self.load_json("systems.json")
        self.enemies = self.load_json("enemies.json")  # ← добавить
        print(f"✓ Загружено кораблей: {len(self.ships)}")
        print(f"✓ Загружено оружия: {len(self.weapons)}")
        print(f"✓ Загружено систем: {len(self.systems)}")
        print(f"✓ Загружено врагов: {len(self.enemies)}")  # ← добавить

    def load_json(self, filename):
        """Загрузка одного JSON файла"""
        path = os.path.join(self.data_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠ Файл {path} не найден, создаю пустой")
            return {}

    def get_ship(self, ship_id):
        """Получить данные корабля по ID"""
        return self.ships.get(ship_id)

    def get_weapon(self, weapon_id):
        """Получить данные оружия по ID"""
        return self.weapons.get(weapon_id)

    def get_system(self, system_id):
        """Получить данные системы по ID"""
        return self.systems.get(system_id)

    def get_weapon_cooldown(self, weapon_id):
        """Получить кулдаун оружия"""
        weapon = self.weapons.get(weapon_id, {})
        return weapon.get("cooldown", 5)

    def get_weapon_damage(self, weapon_id):
        """Получить урон оружия"""
        weapon = self.weapons.get(weapon_id, {})
        return weapon.get("damage", 10)

    def get_all_weapon_ids(self):
        """Список всех ID оружия"""
        return list(self.weapons.keys())

    def get_all_ship_ids(self):
        """Список всех ID кораблей"""
        return list(self.ships.keys())

    def get_all_system_ids(self):
        """Список всех ID систем"""
        return list(self.systems.keys())

    def get_enemy(self, enemy_id):
        """Получить данные врага по ID"""
        return self.enemies.get(enemy_id)