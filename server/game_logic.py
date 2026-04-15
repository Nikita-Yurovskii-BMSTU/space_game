"""Модуль игровой логики"""

from common.protocols import *
import time
import random
import threading
import math
from server.enemy_logic import EnemyLogic


class GameLogic:
    def __init__(self, database, data_loader):
        self.db = database
        self.data = data_loader
        self.last_action_time = {}
        self.cooldown_seconds = 3
        self.weapon_cooldowns = {}
        self.enemy_logic = EnemyLogic(data_loader)
        self.auto_attack = {}
        self.enemy_hp_cache = {}
        self.player_targets = {}
        self.auto_attack_lock = threading.Lock()

        # Таймеры перемещения
        self.move_timers = {}  # {player_name: {"end_time": timestamp, "target_coords": {...}, "type": "move/warp"}}

    def _calculate_distance(self, x1, y1, z1, x2, y2, z2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)

    def _calculate_travel_time(self, distance, speed):
        """Расчёт времени в секундах (не больше 20)"""
        time_sec = distance / speed
        return min(time_sec, 20.0)

    def _get_overview(self, state, player_name):
        """Получить обзор объектов вокруг игрока"""
        current_sys = state["coordinates"]["system"]
        current_star = state["coordinates"]["star"]
        player_x = state["coordinates"]["x"]
        player_y = state["coordinates"]["y"]
        player_z = state["coordinates"]["z"]

        sys_data = self.data.get_system(current_sys)
        if not sys_data:
            return []

        star_data = sys_data["stars"].get(current_star, {})
        objects = star_data.get("objects", [])

        overview = []

        for obj in objects:
            obj_coords = obj["coordinates"]
            dist = self._calculate_distance(
                player_x, player_y, player_z,
                obj_coords["x"], obj_coords["y"], obj_coords["z"]
            )

            if "enemies" in obj:
                for enemy_id in obj["enemies"]:
                    enemy_data = self.data.get_enemy(enemy_id)
                    if enemy_data:
                        cache_key = f"{current_sys}|{current_star}|{obj['name']}|{enemy_id}"
                        enemy_hp = self.enemy_hp_cache.get(cache_key, sum(enemy_data["hull"].values()))
                        max_hp = sum(enemy_data["hull"].values())

                        overview.append({
                            "type": "enemy",
                            "name": enemy_data["name"],
                            "distance": dist,
                            "danger": obj.get("danger", "moderate"),
                            "hp": enemy_hp,
                            "max_hp": max_hp,
                            "enemy_id": enemy_id,
                            "location": obj["name"],
                            "cache_key": cache_key
                        })
            else:
                overview.append({
                    "type": obj["type"],
                    "name": obj["name"],
                    "distance": dist,
                    "danger": obj.get("danger", "safe")
                })

        if hasattr(self, 'server') and self.server:
            sector_players = self.server.get_players_in_sector(current_sys, current_star)
            for p_name, p_coords in sector_players.items():
                if p_name != player_name:
                    dist = self._calculate_distance(
                        player_x, player_y, player_z,
                        p_coords["x"], p_coords["y"], p_coords["z"]
                    )
                    overview.append({
                        "type": "player",
                        "name": p_name,
                        "distance": dist,
                        "danger": "safe"
                    })

        overview.sort(key=lambda x: x["distance"])
        return overview

    def _handle_target(self, target_name, state, player_name):
        """Захват цели"""
        overview = self._get_overview(state, player_name)

        if not overview:
            return {"message": "Нет объектов для захвата! Используйте scan."}

        target = None

        for obj in overview:
            if obj["name"].lower() == target_name.lower():
                target = obj
                break

        if not target and target_name.isdigit():
            idx = int(target_name) - 1
            if 0 <= idx < len(overview):
                target = overview[idx]

        if not target:
            return {"message": f"Цель '{target_name}' не найдена!"}

        self.player_targets[player_name] = target

        return {
            "target": target["name"],
            "message": f"🎯 Цель захвачена: {target['name']} (дистанция: {target['distance']:.0f})"
        }

    def _handle_fire(self, command, state, player_name):
        """Обработка команды fire"""
        parts = command.split()
        if len(parts) != 2:
            return {"message": "Использование: fire [weapon_id]"}

        weapon_id = parts[1]
        weapon_data = self.data.get_weapon(weapon_id)
        if not weapon_data:
            return {"message": f"Неизвестное оружие: {weapon_id}"}

        ship = state.get("ship", {})
        installed = ship.get("installed_weapons", [])
        if weapon_id not in installed:
            return {"message": f"Оружие {weapon_id} не установлено на корабле!"}

        now = time.time()
        if player_name not in self.weapon_cooldowns:
            self.weapon_cooldowns[player_name] = {}

        last_fire = self.weapon_cooldowns[player_name].get(weapon_id, 0)
        cooldown_time = weapon_data["cooldown"]

        if now - last_fire < cooldown_time:
            remaining = cooldown_time - (now - last_fire)
            return {
                "weapon_cooldown": True,
                "weapon": weapon_id,
                "remaining": remaining,
                "message": f"{weapon_data['name']} перезаряжается... {remaining:.1f}с"
            }

        target = self.player_targets.get(player_name)
        if not target:
            return {"message": "Нет захваченной цели! Используйте target [имя/номер]"}

        if target['type'] != 'enemy':
            return {"message": f"{target['name']} не является врагом!"}

        self.weapon_cooldowns[player_name][weapon_id] = now
        damage = weapon_data["damage"]

        if not self.enemy_logic.is_in_combat(player_name):
            current_sys = state["coordinates"]["system"]
            current_star = state["coordinates"]["star"]
            sys_data = self.data.get_system(current_sys)
            if sys_data:
                star_data = sys_data["stars"].get(current_star, {})
                objects = star_data.get("objects", [])

                for obj in objects:
                    if "enemies" in obj:
                        for enemy_id in obj["enemies"]:
                            enemy_data = self.data.get_enemy(enemy_id)
                            if enemy_data and enemy_data["name"] == target['name']:
                                self.enemy_logic.start_combat(player_name, enemy_id, obj["coordinates"], state)
                                break
                        if self.enemy_logic.is_in_combat(player_name):
                            break

        hit_result, error = self.enemy_logic.player_hit_enemy(player_name, weapon_id, state)

        if error:
            return {"message": error}

        if hit_result.get("enemy_destroyed"):
            if player_name in self.player_targets:
                del self.player_targets[player_name]

            return {
                "message": hit_result["message"],
                "state": hit_result["state"],
                "target_cleared": True,
                "weapon_cooldown_after": {
                    "weapon": weapon_id,
                    "remaining": cooldown_time,
                    "message": f"{weapon_data['name']} перезаряжается..."
                }
            }

        return {
            "message": hit_result["message"],
            "state": hit_result["state"],
            "weapon_cooldown_after": {
                "weapon": weapon_id,
                "remaining": cooldown_time,
                "message": f"{weapon_data['name']} перезаряжается..."
            }
        }

    def _handle_auto(self, command, state, player_name):
        """Включить авто-атаку"""
        parts = command.split()
        if len(parts) != 2:
            return {"message": "Использование: auto [weapon_id]"}

        weapon_id = parts[1]
        weapon_data = self.data.get_weapon(weapon_id)
        if not weapon_data:
            return {"message": f"Неизвестное оружие: {weapon_id}"}

        ship = state.get("ship", {})
        installed = ship.get("installed_weapons", [])
        if weapon_id not in installed:
            return {"message": f"Оружие {weapon_id} не установлено на корабле!"}

        with self.auto_attack_lock:
            self.auto_attack[player_name] = {
                "weapon": weapon_id,
                "active": True
            }

        return {"message": f"🔄 Авто-атака включена: {weapon_data['name']}"}

    def _handle_auto_off(self, player_name):
        """Выключить авто-атаку"""
        with self.auto_attack_lock:
            if player_name in self.auto_attack:
                del self.auto_attack[player_name]
                return {"message": "🔴 Авто-атака выключена"}
        return {"message": "Авто-атака не была включена"}

    def process_auto_attacks(self):
        """Обработка авто-атак"""
        with self.auto_attack_lock:
            players = list(self.auto_attack.items())

        for player_name, auto_data in players:
            if not auto_data["active"]:
                continue

            target = self.player_targets.get(player_name)
            if not target or target['type'] != 'enemy':
                auto_data["active"] = False
                if hasattr(self, 'server') and self.server:
                    self.server.send_to_player(player_name, {
                        "type": "message",
                        "data": "[yellow]🔴 Авто-атака остановлена (нет цели)[/yellow]"
                    })
                continue

            if not self.enemy_logic.is_in_combat(player_name):
                continue

            state = self.server.get_player_state(player_name) if hasattr(self, 'server') and self.server else None
            if not state:
                continue

            weapon_id = auto_data["weapon"]

            now = time.time()
            if player_name not in self.weapon_cooldowns:
                self.weapon_cooldowns[player_name] = {}

            last_fire = self.weapon_cooldowns[player_name].get(weapon_id, 0)
            weapon_data = self.data.get_weapon(weapon_id)
            if not weapon_data:
                continue

            if now - last_fire < weapon_data["cooldown"]:
                continue

            self.weapon_cooldowns[player_name][weapon_id] = now
            hit_result, error = self.enemy_logic.player_hit_enemy(player_name, weapon_id, state)

            if error:
                continue

            if hit_result and hasattr(self, 'server') and self.server:
                server = self.server
                if "state" in hit_result:
                    server.save_player_state(player_name, hit_result["state"])
                    server.send_to_player(player_name, {
                        "type": "update",
                        "data": {"hull": hit_result["state"]["hull"]}
                    })

                server.send_to_player(player_name, {
                    "type": "message",
                    "data": f"[cyan]🔄 {hit_result['message']}[/cyan]"
                })

                server.send_to_player(player_name, {
                    "type": "weapon_cooldown",
                    "weapon": weapon_id,
                    "remaining": weapon_data["cooldown"],
                    "message": f"{weapon_data['name']} перезаряжается..."
                })

                if hit_result.get("enemy_destroyed"):
                    auto_data["active"] = False
                    if player_name in self.player_targets:
                        del self.player_targets[player_name]
                    server.send_to_player(player_name, {
                        "type": "target",
                        "target": None
                    })
                    server.send_to_player(player_name, {
                        "type": "message",
                        "data": "[yellow]🔴 Авто-атака остановлена (враг уничтожен)[/yellow]"
                    })

    def _handle_scan(self, state, player_name):
        """Сканирование сектора"""
        overview = self._get_overview(state, player_name)
        return {
            "overview": overview,
            "message": f"🔍 Сканирование завершено. Обнаружено объектов: {len(overview)}"
        }

    def _handle_systems(self, state):
        """Список систем"""
        systems = self.data.get_all_system_ids()
        current = state["coordinates"]["system"]
        message = f"Текущая система: {current}\nДоступные системы:\n"
        current_sys_data = self.data.get_system(current)
        connections = current_sys_data.get("connections", []) if current_sys_data else []

        for s_id in systems:
            sys_data = self.data.get_system(s_id)
            if s_id == current:
                message += f"- {sys_data['name']} (вы здесь)\n"
            elif s_id in connections:
                message += f"- {sys_data['name']} (врата доступны)\n"
            else:
                message += f"- {sys_data['name']}\n"
        return {"message": message}

    def _handle_stars(self, state):
        """Список звёзд в текущей системе"""
        current_sys = state["coordinates"]["system"]
        sys_data = self.data.get_system(current_sys)
        if not sys_data:
            return {"message": "Система не найдена!"}

        stars = sys_data.get("stars", {})
        current_star = state["coordinates"]["star"]
        message = f"✨ Звёзды в системе {sys_data['name']}:\n"

        for star_id, star_data in stars.items():
            if star_id == current_star:
                message += f"  🌟 {star_data['name']} (вы здесь)\n"
            else:
                dist = self._calculate_distance(
                    state["coordinates"]["x"], state["coordinates"]["y"], state["coordinates"]["z"],
                    star_data["coordinates"]["x"], star_data["coordinates"]["y"], star_data["coordinates"]["z"]
                )
                travel_time = self._calculate_travel_time(dist, WARP_SPEED)

                # Форматируем дистанцию
                if dist < 0.01:
                    dist_str = f"{dist * 149597.87:.0f}тыс.км"
                elif dist < 1:
                    dist_str = f"{dist * 1000:.0f}мАЕ"
                else:
                    dist_str = f"{dist:.2f}АЕ"

                message += f"  ⭐ {star_data['name']} (дист: {dist_str}, варп: {travel_time:.1f}с)\n"

        return {"message": message}

    def _handle_jump(self, command, state, player_name):
        """Прыжок в другую систему"""
        parts = command.split()
        if len(parts) != 2:
            return {"message": "Использование: jump [system]"}

        target_sys = parts[1].lower()
        current_sys = state["coordinates"]["system"]

        if self.enemy_logic.is_in_combat(player_name):
            return {"message": "Нельзя прыгать во время боя! Используйте 'flee' для побега."}

        sys_data = self.data.get_system(current_sys)
        if not sys_data:
            return {"message": f"Система {current_sys} не найдена!"}

        if target_sys not in sys_data.get("connections", []):
            return {"message": f"Нет врат в систему {target_sys}!"}

        target_data = self.data.get_system(target_sys)
        if not target_data:
            return {"message": f"Система {target_sys} не найдена!"}

        first_star = list(target_data["stars"].keys())[0]
        star_data = target_data["stars"][first_star]

        travel_time = JUMP_SPEED

        # Запускаем таймер прыжка
        self.move_timers[player_name] = {
            "end_time": time.time() + travel_time,
            "target_coords": {
                "system": target_sys,
                "star": first_star,
                "x": star_data["coordinates"]["x"],
                "y": star_data["coordinates"]["y"],
                "z": star_data["coordinates"]["z"]
            },
            "type": "jump",
            "start_state": state.copy()
        }

        return {
            "travel": True,
            "travel_time": travel_time,
            "travel_type": "jump",
            "message": f"✨ Прыжок через врата в систему {target_data['name']}... прибытие через {travel_time:.1f}с"
        }

    def _handle_warp(self, command, state, player_name):
        """Варп к другой звезде или объекту"""
        parts = command.split()
        if len(parts) < 2:
            return {"message": "Использование: warp [star/object_name]"}

        target_name = parts[1].lower()
        current_sys = state["coordinates"]["system"]
        current_star = state["coordinates"]["star"]
        player_coords = (state["coordinates"]["x"], state["coordinates"]["y"], state["coordinates"]["z"])

        if self.enemy_logic.is_in_combat(player_name):
            return {"message": "Нельзя варпать во время боя! Используйте 'flee' для побега."}

        sys_data = self.data.get_system(current_sys)
        if not sys_data:
            return {"message": "Система не найдена!"}

        stars = sys_data.get("stars", {})
        target_coords = None
        target_display_name = None

        # Ищем среди звёзд
        for star_id, star_data in stars.items():
            if star_data["name"].lower() == target_name or star_id.lower() == target_name:
                target_coords = star_data["coordinates"]
                target_display_name = star_data["name"]
                break

        # Если не звезда, ищем среди объектов
        if not target_coords:
            star_data = stars.get(current_star, {})
            objects = star_data.get("objects", [])
            for obj in objects:
                if obj["name"].lower() == target_name:
                    target_coords = obj["coordinates"]
                    target_display_name = obj["name"]
                    break

        if not target_coords:
            return {"message": f"Цель '{target_name}' не найдена!"}

        # Рассчитываем дистанцию в АЕ
        distance = self._calculate_distance(
            player_coords[0], player_coords[1], player_coords[2],
            target_coords["x"], target_coords["y"], target_coords["z"]
        )

        # Проверяем, нужно ли варпать
        if distance < WARP_MIN_DISTANCE:
            return {"message": f"Слишком близко! Дистанция {distance:.4f}АЕ < {WARP_MIN_DISTANCE}АЕ. Используйте move."}

        travel_time = self._calculate_travel_time(distance, WARP_SPEED)

        # Запускаем таймер варпа
        self.move_timers[player_name] = {
            "end_time": time.time() + travel_time,
            "target_coords": {
                "system": current_sys,
                "star": current_star,
                "x": target_coords["x"],
                "y": target_coords["y"],
                "z": target_coords["z"]
            },
            "type": "warp",
            "start_state": state.copy(),
            "target_name": target_display_name
        }

        # Форматируем дистанцию для красивого вывода
        if distance < 0.01:
            dist_str = f"{distance * 149597.87:.0f}тыс.км"
        elif distance < 1:
            dist_str = f"{distance * 1000:.0f}мАЕ"
        else:
            dist_str = f"{distance:.2f}АЕ"

        return {
            "travel": True,
            "travel_time": travel_time,
            "travel_type": "warp",
            "message": f"🚀 Варп к {target_display_name}! Дистанция: {dist_str}, время: {travel_time:.1f}с"
        }

    def _handle_move(self, command, state, player_name):
        """Обычное перемещение с таймером"""
        parts = command.split()

        # Парсим дельты
        dx, dy, dz = 0, 0, 0
        i = 1
        while i < len(parts):
            if parts[i] == 'x' and i + 1 < len(parts):
                dx += float(parts[i + 1])
                i += 2
            elif parts[i] == 'y' and i + 1 < len(parts):
                dy += float(parts[i + 1])
                i += 2
            elif parts[i] == 'z' and i + 1 < len(parts):
                dz += float(parts[i + 1])
                i += 2
            else:
                i += 1

        if dx == 0 and dy == 0 and dz == 0:
            return {"message": "Использование: move x 10 y 5 z -3"}

        # Рассчитываем дистанцию и время
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        travel_time = self._calculate_travel_time(distance, MOVE_SPEED)

        current_coords = state["coordinates"]
        target_coords = {
            "system": current_coords["system"],
            "star": current_coords["star"],
            "x": current_coords["x"] + dx,
            "y": current_coords["y"] + dy,
            "z": current_coords["z"] + dz
        }

        # Запускаем таймер перемещения
        self.move_timers[player_name] = {
            "end_time": time.time() + travel_time,
            "target_coords": target_coords,
            "type": "move",
            "start_state": state.copy(),
            "dx": dx, "dy": dy, "dz": dz,
            "distance": distance
        }

        return {
            "travel": True,
            "travel_time": travel_time,
            "travel_type": "move",
            "message": f"🛸 Перемещение на {distance:.1f}км, время: {travel_time:.1f}с"
        }

    def check_travel_completion(self, player_name, current_state):
        """Проверить, завершилось ли перемещение"""
        if player_name not in self.move_timers:
            return None

        timer = self.move_timers[player_name]
        now = time.time()

        if now >= timer["end_time"]:
            # Перемещение завершено
            target = timer["target_coords"]
            travel_type = timer["type"]

            # Очищаем таймер
            del self.move_timers[player_name]

            # Обновляем состояние
            new_state = current_state.copy()
            new_state["coordinates"] = target

            # Очищаем цель при перемещении
            if player_name in self.player_targets:
                del self.player_targets[player_name]

            return {
                "state": new_state,
                "target_cleared": True,
                "message": f"✅ {'Варп' if travel_type == 'warp' else 'Прыжок' if travel_type == 'jump' else 'Перемещение'} завершён!"
            }

        # Ещё в пути
        remaining = timer["end_time"] - now
        return {
            "travel_in_progress": True,
            "remaining": remaining,
            "travel_type": timer["type"],
            "message": f"⏳ В пути... осталось {remaining:.1f}с"
        }

    def _handle_repair(self, command, state):
        """Ремонт корпуса"""
        parts = command.split()
        if len(parts) == 3 and state['inventory']['repair_kits'] > 0:
            part, value = parts[1], int(parts[2])
            new_state = state.copy()
            new_state['hull'] = state['hull'].copy()
            if 'ship' in new_state:
                new_state['ship'] = state['ship'].copy()
                new_state['ship']['hull'] = state['ship']['hull'].copy()
            new_state['inventory'] = state['inventory'].copy()

            if part in new_state['hull']:
                old_value = new_state['hull'][part]
                new_state['hull'][part] = min(100, new_state['hull'][part] + value)
                if 'ship' in new_state:
                    new_state['ship']['hull'][part] = new_state['hull'][part]
                new_state['inventory']['repair_kits'] -= 1
                repaired = new_state['hull'][part] - old_value
                return {
                    "message": f"🔧 Отремонтирован {part}: +{repaired} (Осталось ремкомплектов: {new_state['inventory']['repair_kits']})",
                    "state": new_state
                }
        return {"message": "Недостаточно ремкомплектов или неверная команда! Используйте: repair [нос/лев/прав/корм] [количество]"}

    def _execute_command(self, command, state, player_name):
        # Сначала проверяем, не в пути ли игрок
        if player_name in self.move_timers:
            travel_check = self.check_travel_completion(player_name, state)
            if travel_check and travel_check.get("travel_in_progress"):
                return {
                    "cooldown": True,
                    "remaining": travel_check["remaining"],
                    "message": travel_check["message"]
                }
            elif travel_check and "state" in travel_check:
                # Перемещение завершено, возвращаем новое состояние
                return travel_check

        # HELP
        if command == CMD_HELP:
            return {"message": """Доступные команды:
- status - показать текущий статус
- systems - список всех систем
- stars - список звёзд в текущей системе
- scan - что вокруг (объекты в секторе)
- jump [system] - прыжок в другую систему
- warp [star/object] - варп к звезде или объекту (>1000км)
- move x 10 y 5 z -3 - перемещение
- target [имя/номер] - захватить цель
- fire [weapon] - выстрелить по цели
- auto [weapon] - авто-атака
- auto off - выключить авто-атаку
- flee - сбежать из боя
- repair [часть] [количество] - ремонт
- stats - статистика
- save - сохранить
- quit - выход"""}

        # СИСТЕМЫ
        elif command == "systems":
            return self._handle_systems(state)

        # ЗВЁЗДЫ
        elif command == "stars":
            return self._handle_stars(state)

        # СКАНИРОВАНИЕ
        elif command == "scan":
            return self._handle_scan(state, player_name)

        # ПРЫЖОК
        elif command.startswith("jump "):
            return self._handle_jump(command, state, player_name)

        # ВАРП
        elif command.startswith("warp "):
            return self._handle_warp(command, state, player_name)

        # ПЕРЕМЕЩЕНИЕ
        elif command.startswith(CMD_MOVE):
            return self._handle_move(command, state, player_name)

        # ЦЕЛЬ
        elif command.startswith("target "):
            target_name = command[7:].strip()
            return self._handle_target(target_name, state, player_name)

        # ОГОНЬ
        elif command.startswith("fire "):
            return self._handle_fire(command, state, player_name)

        # АВТО-АТАКА
        elif command.startswith("auto "):
            return self._handle_auto(command, state, player_name)

        elif command == "auto off":
            return self._handle_auto_off(player_name)

        # ПОБЕГ
        elif command == "flee":
            if self.enemy_logic.is_in_combat(player_name):
                self.enemy_logic.end_combat(player_name)
                if player_name in self.player_targets:
                    del self.player_targets[player_name]
                return {"message": "🏃 Вы сбежали из боя!", "target_cleared": True}
            return {"message": "Вы не в бою!"}

        # СТАТУС
        elif command == CMD_STATUS:
            coords = state["coordinates"]
            target = self.player_targets.get(player_name)
            target_str = f"\n🎯 Цель: {target['name']}" if target else ""
            sys_data = self.data.get_system(coords["system"])
            sys_name = sys_data["name"] if sys_data else coords["system"]
            return {"message": f"📍 Система: {sys_name} | Коорд: {coords['x']:.0f} {coords['y']:.0f} {coords['z']:.0f}{target_str}"}

        # СТАТИСТИКА
        elif command == CMD_STATS:
            stats = state.get("stats", {})
            return {"message": f"📊 Побед: {stats.get('enemies_defeated', 0)} | Урон: {stats.get('total_damage_dealt', 0)}"}

        # СОХРАНЕНИЕ
        elif command == CMD_SAVE:
            self.db.save_state(state)
            return {"message": "💾 Игра сохранена!"}

        # РЕМОНТ
        elif command.startswith(CMD_REPAIR):
            return self._handle_repair(command, state)

        # ИНВЕНТАРЬ
        elif command == "inv" or command == "inventory":
            inv = state.get("inventory", {})
            return {"message": f"🎒 Инвентарь: ремки={inv.get('repair_kits',0)} ракеты={inv.get('missiles',0)} лом={inv.get('scrap',0)}"}

        # ВЫХОД
        elif command == CMD_QUIT:
            self.enemy_logic.end_combat(player_name)
            if player_name in self.player_targets:
                del self.player_targets[player_name]
            return {"message": "До свидания!"}

        else:
            return {"message": f"Неизвестная команда: {command}"}

    def process_command(self, command, state, player_name):
        now = time.time()
        last = self.last_action_time.get(player_name, 0)

        # Команды с кулдауном
        action_commands = (CMD_MOVE, "fire", "target", "attack", "flee", CMD_REPAIR, "auto", "jump", "warp")
        if any(command.startswith(cmd) for cmd in action_commands):
            if now - last < self.cooldown_seconds:
                remaining = self.cooldown_seconds - (now - last)
                return {
                    "cooldown": True,
                    "remaining": remaining,
                    "message": f"Системы перезаряжаются... {remaining:.1f}с"
                }
            else:
                self.last_action_time[player_name] = now
                result = self._execute_command(command, state, player_name)
                if result and not result.get("weapon_cooldown") and not result.get("cooldown") and not result.get("travel"):
                    if not result.get("no_cooldown"):
                        result["cooldown_after"] = {
                            "remaining": self.cooldown_seconds,
                            "message": "Системы перезаряжаются..."
                        }
                return result

        return self._execute_command(command, state, player_name)

    @staticmethod
    def get_changes(old_state, new_state):
        if not old_state:
            return new_state
        changes = {}
        for section in ['coordinates', 'hull', 'inventory', 'ship', 'stats']:
            if section in new_state and section in old_state:
                if isinstance(new_state[section], dict):
                    section_changes = {}
                    for key in new_state[section]:
                        if key in old_state[section] and new_state[section][key] != old_state[section][key]:
                            section_changes[key] = new_state[section][key]
                    if section_changes:
                        changes[section] = section_changes
                elif new_state[section] != old_state[section]:
                    changes[section] = new_state[section]
            elif section in new_state:
                changes[section] = new_state[section]
        return changes