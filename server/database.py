"""Модуль работы с базой данных"""

import sqlite3
from datetime import datetime
import hashlib
import json
from common.protocols import *


class Database:
    def __init__(self, db_file="game_state.db"):
        self.db_file = db_file
        self.init_database()

    def init_database(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Таблица для игроков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                total_play_time INTEGER DEFAULT 0
            )
        ''')

        # Таблица для координат (обновленная)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS coordinates (
                player_id INTEGER PRIMARY KEY,
                system TEXT DEFAULT 'nexus',
                star TEXT DEFAULT 'nexus_alpha',
                x REAL DEFAULT 0,
                y REAL DEFAULT 0,
                z REAL DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')

        # Таблица для состояния корпуса (устаревшая, для совместимости)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hull (
                player_id INTEGER PRIMARY KEY,
                bow INTEGER DEFAULT 100,
                stern INTEGER DEFAULT 100,
                port INTEGER DEFAULT 100,
                starboard INTEGER DEFAULT 100,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')

        # Таблица для инвентаря
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                player_id INTEGER PRIMARY KEY,
                repair_kits INTEGER DEFAULT 3,
                missiles INTEGER DEFAULT 8,
                scrap INTEGER DEFAULT 150,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')

        # Таблица для статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                player_id INTEGER PRIMARY KEY,
                enemies_defeated INTEGER DEFAULT 0,
                missions_completed INTEGER DEFAULT 0,
                total_damage_dealt INTEGER DEFAULT 0,
                total_damage_taken INTEGER DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')

        # Таблица кораблей игроков
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_ships (
                player_id INTEGER PRIMARY KEY,
                ship_id TEXT DEFAULT 'fighter',
                current_hull_bow INTEGER DEFAULT 100,
                current_hull_stern INTEGER DEFAULT 100,
                current_hull_port INTEGER DEFAULT 100,
                current_hull_starboard INTEGER DEFAULT 100,
                installed_weapons TEXT DEFAULT '[]',
                FOREIGN KEY (player_id) REFERENCES players(player_id)
            )
        ''')

        conn.commit()
        conn.close()
        print("✓ База данных инициализирована")

    @staticmethod
    def hash_password(password):
        """Хеширование пароля"""
        return hashlib.sha256(password.encode()).hexdigest()

    def create_player(self, player_name, password, starting_ship="fighter"):
        """Создание нового игрока"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            password_hash = self.hash_password(password)
            cursor.execute(
                "INSERT INTO players (player_name, password_hash, last_login) VALUES (?, ?, ?)",
                (player_name, password_hash, datetime.now())
            )
            player_id = cursor.lastrowid

            # Загружаем данные корабля из JSON (через DataLoader)
            from server.data_loader import DataLoader
            data = DataLoader()
            ship_data = data.get_ship(starting_ship)

            if ship_data:
                hull = ship_data["hull"]
                default_weapons = ship_data.get("default_weapons", ["laser"])
            else:
                hull = {"bow": 100, "stern": 80, "port": 80, "starboard": 80}
                default_weapons = ["laser"]

            cursor.execute("INSERT INTO coordinates (player_id) VALUES (?)", (player_id,))
            cursor.execute("INSERT INTO hull (player_id) VALUES (?)", (player_id,))
            cursor.execute("INSERT INTO inventory (player_id) VALUES (?)", (player_id,))
            cursor.execute("INSERT INTO stats (player_id) VALUES (?)", (player_id,))

            cursor.execute('''
                INSERT INTO player_ships 
                (player_id, ship_id, current_hull_bow, current_hull_stern, 
                 current_hull_port, current_hull_starboard, installed_weapons)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id,
                starting_ship,
                hull["bow"],
                hull["stern"],
                hull["port"],
                hull["starboard"],
                json.dumps(default_weapons)
            ))

            conn.commit()
            return True, "Игрок успешно создан!"
        except sqlite3.IntegrityError:
            return False, "Игрок с таким именем уже существует!"
        finally:
            conn.close()

    def verify_player(self, player_name, password):
        """Проверка учетных данных игрока"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        password_hash = self.hash_password(password)
        cursor.execute(
            "SELECT player_id FROM players WHERE player_name = ? AND password_hash = ?",
            (player_name, password_hash)
        )

        result = cursor.fetchone()
        if result:
            cursor.execute(
                "UPDATE players SET last_login = ? WHERE player_id = ?",
                (datetime.now(), result[0])
            )
            conn.commit()
            player_id = result[0]
        else:
            player_id = None

        conn.close()
        return player_id

    def get_player_id(self, player_name):
        """Получение ID игрока по имени"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT player_id FROM players WHERE player_name = ?", (player_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None

    def get_player_ship(self, player_name):
        """Получить корабль игрока"""
        player_id = self.get_player_id(player_name)
        if not player_id:
            return None

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ship_id, current_hull_bow, current_hull_stern, 
                   current_hull_port, current_hull_starboard, installed_weapons
            FROM player_ships WHERE player_id = ?
        ''', (player_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "ship_id": row[0],
                "hull": {
                    "bow": row[1],
                    "stern": row[2],
                    "port": row[3],
                    "starboard": row[4]
                },
                "installed_weapons": json.loads(row[5])
            }
        return None

    def save_player_ship(self, player_name, ship_data):
        """Сохранить корабль игрока"""
        player_id = self.get_player_id(player_name)
        if not player_id:
            return False

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE player_ships 
            SET ship_id = ?, current_hull_bow = ?, current_hull_stern = ?,
                current_hull_port = ?, current_hull_starboard = ?, installed_weapons = ?
            WHERE player_id = ?
        ''', (
            ship_data["ship_id"],
            ship_data["hull"]["bow"],
            ship_data["hull"]["stern"],
            ship_data["hull"]["port"],
            ship_data["hull"]["starboard"],
            json.dumps(ship_data["installed_weapons"]),
            player_id
        ))
        conn.commit()
        conn.close()
        return True

    def load_state(self, player_name):
        """Загрузка состояния игрока из БД"""
        player_id = self.get_player_id(player_name)
        if not player_id:
            return None

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Координаты
        cursor.execute("SELECT system, star, x, y, z FROM coordinates WHERE player_id = ?", (player_id,))
        coords = cursor.fetchone()

        # Инвентарь
        cursor.execute("SELECT repair_kits, missiles, scrap FROM inventory WHERE player_id = ?", (player_id,))
        inventory = cursor.fetchone()

        # Статистика
        cursor.execute('''
            SELECT enemies_defeated, missions_completed, total_damage_dealt, total_damage_taken 
            FROM stats WHERE player_id = ?
        ''', (player_id,))
        stats = cursor.fetchone()

        # Корабль игрока
        cursor.execute('''
            SELECT ship_id, current_hull_bow, current_hull_stern, 
                   current_hull_port, current_hull_starboard, installed_weapons
            FROM player_ships WHERE player_id = ?
        ''', (player_id,))
        ship_row = cursor.fetchone()

        # Формируем состояние
        state = {
            "player": player_name,
            "coordinates": {
                "system": coords[0] if coords else "nexus",
                "star": coords[1] if coords else "nexus_alpha",
                "x": coords[2] if coords else 0,
                "y": coords[3] if coords else 0,
                "z": coords[4] if coords else 0
            },
            "inventory": {
                "repair_kits": inventory[0] if inventory else 3,
                "missiles": inventory[1] if inventory else 8,
                "scrap": inventory[2] if inventory else 150
            },
            "stats": {
                "enemies_defeated": stats[0] if stats else 0,
                "missions_completed": stats[1] if stats else 0,
                "total_damage_dealt": stats[2] if stats else 0,
                "total_damage_taken": stats[3] if stats else 0
            }
        }

        # Добавляем данные корабля
        if ship_row:
            state["ship"] = {
                "ship_id": ship_row[0],
                "hull": {
                    "bow": ship_row[1],
                    "stern": ship_row[2],
                    "port": ship_row[3],
                    "starboard": ship_row[4]
                },
                "installed_weapons": json.loads(ship_row[5])
            }
            state["hull"] = state["ship"]["hull"].copy()
        else:
            # Загружаем из старой таблицы hull
            cursor.execute("SELECT bow, stern, port, starboard FROM hull WHERE player_id = ?", (player_id,))
            hull = cursor.fetchone()
            if hull:
                state["hull"] = {
                    "bow": hull[0], "stern": hull[1], "port": hull[2], "starboard": hull[3]
                }
            else:
                state["hull"] = {"bow": 100, "stern": 100, "port": 100, "starboard": 100}

            state["ship"] = {
                "ship_id": "fighter",
                "hull": state["hull"].copy(),
                "installed_weapons": ["laser"]
            }

        conn.close()
        return state

    def save_state(self, state):
        """Сохранение состояния в БД"""
        player_id = self.get_player_id(state["player"])
        if not player_id:
            return False

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        try:
            # Координаты
            coords = state["coordinates"]
            cursor.execute('''
                UPDATE coordinates 
                SET system = ?, star = ?, x = ?, y = ?, z = ?
                WHERE player_id = ?
            ''', (coords["system"], coords["star"], coords["x"], coords["y"], coords["z"], player_id))

            # Инвентарь
            inventory = state["inventory"]
            cursor.execute('''
                UPDATE inventory 
                SET repair_kits = ?, missiles = ?, scrap = ?
                WHERE player_id = ?
            ''', (inventory["repair_kits"], inventory["missiles"], inventory["scrap"], player_id))

            # Статистика
            if "stats" in state:
                stats = state["stats"]
                cursor.execute('''
                    UPDATE stats 
                    SET enemies_defeated = ?, missions_completed = ?, 
                        total_damage_dealt = ?, total_damage_taken = ?
                    WHERE player_id = ?
                ''', (stats["enemies_defeated"], stats["missions_completed"],
                      stats["total_damage_dealt"], stats["total_damage_taken"], player_id))

            # Корабль
            if "ship" in state:
                ship = state["ship"]
                cursor.execute('''
                    UPDATE player_ships 
                    SET ship_id = ?, current_hull_bow = ?, current_hull_stern = ?,
                        current_hull_port = ?, current_hull_starboard = ?, installed_weapons = ?
                    WHERE player_id = ?
                ''', (
                    ship["ship_id"],
                    ship["hull"]["bow"],
                    ship["hull"]["stern"],
                    ship["hull"]["port"],
                    ship["hull"]["starboard"],
                    json.dumps(ship["installed_weapons"]),
                    player_id
                ))

                # Для совместимости обновляем старую таблицу hull
                cursor.execute('''
                    UPDATE hull 
                    SET bow = ?, stern = ?, port = ?, starboard = ?
                    WHERE player_id = ?
                ''', (ship["hull"]["bow"], ship["hull"]["stern"],
                      ship["hull"]["port"], ship["hull"]["starboard"], player_id))
            else:
                # Старый формат
                hull = state["hull"]
                cursor.execute('''
                    UPDATE hull 
                    SET bow = ?, stern = ?, port = ?, starboard = ?
                    WHERE player_id = ?
                ''', (hull["bow"], hull["stern"], hull["port"], hull["starboard"], player_id))

            conn.commit()
            return True
        except Exception as e:
            print(f"Ошибка сохранения: {e}")
            return False
        finally:
            conn.close()

    def update_stats(self, player_name, stat_type, value):
        """Обновление статистики игрока"""
        allowed_stats = {'enemies_defeated', 'missions_completed', 'total_damage_dealt', 'total_damage_taken'}
        if stat_type not in allowed_stats:
            return

        player_id = self.get_player_id(player_name)
        if not player_id:
            return

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute(f'''
            UPDATE stats 
            SET {stat_type} = {stat_type} + ?
            WHERE player_id = ?
        ''', (value, player_id))
        conn.commit()
        conn.close()