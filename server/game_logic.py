"""Модуль игровой логики"""

from common.protocols import *
import time
import random
from server.enemy_logic import EnemyLogic


class GameLogic:
    def __init__(self, database, data_loader):
        self.db = database
        self.data = data_loader
        self.last_action_time = {}
        self.cooldown_seconds = 3
        self.weapon_cooldowns = {}
        self.enemy_logic = EnemyLogic(data_loader)
        self.auto_attack = {}  # {player_name: {"weapon": weapon_id, "active": True}}


    def _calculate_distance(self, x1, y1, z1, x2, y2, z2):
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2) ** 0.5

    def _execute_command(self, command, state, player_name):

        if command == CMD_HELP:
            return {"message": """Доступные команды:
- status - показать текущий статус
- systems - список всех систем
- stars - список звёзд в текущей системе
- scan - что вокруг (объекты в секторе)
- jump [system] - прыжок в другую систему
- warp [star] - варп к другой звезде
- move x 10 y 5 z -5 - перемещение
- attack [имя] - атаковать врага
- fire [weapon] - выстрелить
- flee - сбежать из боя
- repair bow 20 - отремонтировать
- stats - статистика
- save - сохранить
- quit - выход"""}
        elif command.startswith("auto "):
            return self._handle_auto(command, state, player_name)

        elif command == "auto off":
            return self._handle_auto_off(player_name)

        elif command == "systems":
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

        elif command == "stars":
            current_sys = state["coordinates"]["system"]
            sys_data = self.data.get_system(current_sys)
            if not sys_data:
                return {"message": "Система не найдена!"}

            stars = sys_data.get("stars", {})
            current_star = state["coordinates"]["star"]
            message = f"Звёзды в системе {sys_data['name']}:\n"
            for star_id, star_data in stars.items():
                if star_id == current_star:
                    message += f"- {star_data['name']} (вы здесь)\n"
                else:
                    message += f"- {star_data['name']}\n"
            return {"message": message}

        elif command == "scan":
            current_sys = state["coordinates"]["system"]
            current_star = state["coordinates"]["star"]
            sys_data = self.data.get_system(current_sys)
            if not sys_data:
                return {"message": "Система не найдена!"}

            star_data = sys_data["stars"].get(current_star, {})
            objects = star_data.get("objects", [])

            if not objects:
                return {"message": "Пустой сектор."}

            message = f"Объекты в {star_data['name']}:\n"
            for obj in objects:
                obj_coords = obj["coordinates"]
                dist = self._calculate_distance(
                    state["coordinates"]["x"], state["coordinates"]["y"], state["coordinates"]["z"],
                    obj_coords["x"], obj_coords["y"], obj_coords["z"]
                )
                danger = obj.get("danger", "safe")
                danger_icon = {"safe": "🟢", "moderate": "🟡", "dangerous": "🟠", "deadly": "🔴"}.get(danger, "")

                if obj["type"] == "station":
                    message += f"- 🛸 {obj['name']} (станция) на дистанции {dist:.1f}\n"
                elif obj["type"] == "planet":
                    message += f"- 🪐 {obj['name']} (планета) на дистанции {dist:.1f}\n"
                elif obj["type"] in ["belt", "debris_field", "ice_field"]:
                    message += f"- ☄️ {obj['name']} (пояс) на дистанции {dist:.1f} {danger_icon}\n"
                    if "enemies" in obj:
                        message += f"  Враги: {', '.join(obj['enemies'])}\n"

            combat_info = self.enemy_logic.get_combat_info(player_name)
            if combat_info:
                hull_percent = (combat_info["total_hull"] / combat_info["max_hull"]) * 100 if combat_info["max_hull"] > 0 else 0
                message += f"\n⚔️ В БОЮ: {combat_info['enemy_name']} ({hull_percent:.0f}% HP) на дистанции {combat_info['distance']:.1f}"

            return {"message": message}

        elif command.startswith("jump "):
            target_sys = command[5:].strip().lower()
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

            new_state = state.copy()
            new_state["coordinates"] = {
                "system": target_sys,
                "star": first_star,
                "x": star_data["coordinates"]["x"],
                "y": star_data["coordinates"]["y"],
                "z": star_data["coordinates"]["z"]
            }

            return {
                "message": f"✨ Прыжок через врата в систему {target_data['name']}!\nВы прибыли к звезде {star_data['name']}.",
                "state": new_state
            }

        elif command.startswith("warp "):
            target_star = command[5:].strip().lower()
            current_sys = state["coordinates"]["system"]
            current_star = state["coordinates"]["star"]

            if self.enemy_logic.is_in_combat(player_name):
                return {"message": "Нельзя варпать во время боя! Используйте 'flee' для побега."}

            if target_star == current_star:
                return {"message": "Вы уже у этой звезды!"}

            sys_data = self.data.get_system(current_sys)
            if not sys_data:
                return {"message": "Система не найдена!"}

            stars = sys_data.get("stars", {})

            if target_star not in stars:
                return {"message": f"Звезда {target_star} не найдена в системе!"}

            star_data = stars[target_star]

            new_state = state.copy()
            new_state["coordinates"] = {
                "system": current_sys,
                "star": target_star,
                "x": star_data["coordinates"]["x"],
                "y": star_data["coordinates"]["y"],
                "z": star_data["coordinates"]["z"]
            }

            return {
                "message": f"🚀 Варп-прыжок к звезде {star_data['name']}!",
                "state": new_state
            }

        elif command == CMD_STATUS:
            coords = state["coordinates"]
            sys_data = self.data.get_system(coords["system"])
            sys_name = sys_data["name"] if sys_data else coords["system"]
            star_name = coords["star"]
            if sys_data and coords["star"] in sys_data["stars"]:
                star_name = sys_data["stars"][coords["star"]]["name"]

            message = f"""📍 Статус:
Система: {sys_name}
Звезда: {star_name}
Координаты: X:{coords['x']:.1f} Y:{coords['y']:.1f} Z:{coords['z']:.1f}"""

            combat_info = self.enemy_logic.get_combat_info(player_name)
            if combat_info:
                message += f"\n⚔️ В бою с {combat_info['enemy_name']} ({combat_info['total_hull']}/{combat_info['max_hull']} HP)"

            return {"message": message, "state": state}

        elif command == CMD_STATS:
            stats = state.get("stats", {})
            ship = state.get("ship", {})
            message = f"""📊 Статистика {player_name}:
- Корабль: {ship.get('ship_id', 'fighter')}
- Врагов побеждено: {stats.get('enemies_defeated', 0)}
- Миссий выполнено: {stats.get('missions_completed', 0)}
- Урона нанесено: {stats.get('total_damage_dealt', 0)}
- Урона получено: {stats.get('total_damage_taken', 0)}
- Установлено оружия: {', '.join(ship.get('installed_weapons', []))}"""
            return {"message": message}

        elif command == CMD_SAVE:
            self.db.save_state(state)
            return {"message": "Игра сохранена!"}

        elif command == "weapons":
            weapons = self.data.get_all_weapon_ids()
            message = "Доступное оружие:\n"
            for w_id in weapons:
                w = self.data.get_weapon(w_id)
                message += f"- {w_id}: {w['name']} (урон: {w['damage']}, кулдаун: {w['cooldown']}с)\n"
            return {"message": message}

        elif command.startswith("attack "):
            return self._handle_attack(command, state, player_name)

        elif command == "flee":
            return self._handle_flee(state, player_name)

        elif command.startswith(CMD_MOVE):
            return self._handle_move(command, state, player_name)

        elif command.startswith(CMD_REPAIR):
            return self._handle_repair(command, state)

        elif command.startswith("fire"):
            return self._handle_fire(command, state, player_name)

        elif command == CMD_QUIT:
            self.enemy_logic.end_combat(player_name)
            return {"message": "До свидания!"}

        elif command == "inv" or command == "inventory":
            inventory = state.get("inventory", {})
            message = "🎒 Инвентарь:\n"
            for k, v in inventory.items():
                message += f"- {k}: {v}\n"
            return {"message": message}

        else:
            return {"message": f"Неизвестная команда: {command}"}

    def process_command(self, command, state, player_name):
        now = time.time()
        last = self.last_action_time.get(player_name, 0)

        if command.startswith((CMD_MOVE, "fire", "jump", "warp", "attack", "flee", CMD_REPAIR)):
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
                if result and not result.get("weapon_cooldown") and not result.get("cooldown"):
                    result["cooldown_after"] = {
                        "remaining": self.cooldown_seconds,
                        "message": "Системы перезаряжаются..."
                    }
                return result

        return self._execute_command(command, state, player_name)

    def _handle_attack(self, command, state, player_name):
        target_name = command[7:].strip()

        current_sys = state["coordinates"]["system"]
        current_star = state["coordinates"]["star"]
        sys_data = self.data.get_system(current_sys)
        if not sys_data:
            return {"message": "Система не найдена!"}

        star_data = sys_data["stars"].get(current_star, {})
        objects = star_data.get("objects", [])

        target_obj = None
        for obj in objects:
            if obj.get("name", "").lower() == target_name.lower():
                target_obj = obj
                break

        if not target_obj:
            return {"message": f"Цель '{target_name}' не найдена!"}

        if "enemies" not in target_obj:
            return {"message": f"{target_obj['name']} не является врагом!"}

        enemy_id = target_obj["enemies"][0]

        combat_data = self.enemy_logic.start_combat(player_name, enemy_id, target_obj["coordinates"], state)
        if not combat_data:
            return {"message": f"Неизвестный враг: {enemy_id}"}

        enemy_data = combat_data["enemy_data"]

        return {
            "message": f"⚔️ Бой начат с {enemy_data['name']}! Дистанция: {combat_data['distance']:.1f}\nHP врага: {sum(enemy_data['hull'].values())}"
        }

    def _handle_flee(self, state, player_name):
        if not self.enemy_logic.is_in_combat(player_name):
            return {"message": "Вы не в бою!"}

        combat_info = self.enemy_logic.get_combat_info(player_name)
        enemy_name = combat_info["enemy_name"]
        distance = combat_info["distance"]

        flee_chance = min(0.9, 0.3 + distance / 200)

        if random.random() < flee_chance:
            self.enemy_logic.end_combat(player_name)
            return {"message": f"🏃 Вы успешно сбежали от {enemy_name}!"}
        else:
            return {"message": f"❌ Не удалось сбежать от {enemy_name}!"}

    def _handle_fire(self, command, state, player_name):
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

        self.weapon_cooldowns[player_name][weapon_id] = now
        damage = weapon_data["damage"]

        if self.enemy_logic.is_in_combat(player_name):
            hit_result, error = self.enemy_logic.player_hit_enemy(player_name, weapon_id, state)

            if error:
                return {"message": error}

            if hit_result.get("enemy_destroyed"):
                return {
                    "message": hit_result["message"],
                    "state": hit_result["state"],
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

        new_state = state.copy()
        new_state['stats'] = state.get('stats', {}).copy()
        new_state['stats']['total_damage_dealt'] = new_state['stats'].get('total_damage_dealt', 0) + damage

        return {
            "message": f"💥 Выстрел из {weapon_data['name']}!",
            "state": new_state,
            "weapon_cooldown_after": {
                "weapon": weapon_id,
                "remaining": cooldown_time,
                "message": f"{weapon_data['name']} перезаряжается..."
            }
        }

    def _handle_move(self, command, state, player_name):
        parts = command.split()
        new_state = state.copy()
        new_state['coordinates'] = state['coordinates'].copy()

        i = 1
        while i < len(parts):
            if parts[i] == 'x' and i + 1 < len(parts):
                new_state['coordinates']['x'] += float(parts[i + 1])
                i += 2
            elif parts[i] == 'y' and i + 1 < len(parts):
                new_state['coordinates']['y'] += float(parts[i + 1])
                i += 2
            elif parts[i] == 'z' and i + 1 < len(parts):
                new_state['coordinates']['z'] += float(parts[i + 1])
                i += 2
            else:
                i += 1

        coords = new_state['coordinates']
        message = f"Перемещение: X:{coords['x']:.1f} Y:{coords['y']:.1f} Z:{coords['z']:.1f}"

        combat_info = self.enemy_logic.get_combat_info(player_name)
        if combat_info:
            message += f"\nДистанция до врага: {combat_info['distance']:.1f}"

        return {
            "message": message,
            "state": new_state
        }

    def _handle_repair(self, command, state):
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
                    "message": f"🔧 Отремонтирован {part}: +{repaired} "
                              f"(Осталось ремкомплектов: {new_state['inventory']['repair_kits']})",
                    "state": new_state
                }

        return {"message": "Недостаточно ремкомплектов или неверная команда!"}

    @staticmethod
    def get_changes(old_state, new_state):
        if not old_state:
            return new_state

        changes = {}

        for section in ['coordinates', 'hull', 'inventory', 'ship', 'stats']:
            if section in new_state and section in old_state:
                if section == 'ship':
                    section_changes = {}
                    old_ship = old_state.get('ship', {})
                    new_ship = new_state.get('ship', {})

                    if old_ship.get('ship_id') != new_ship.get('ship_id'):
                        section_changes['ship_id'] = new_ship['ship_id']

                    old_hull = old_ship.get('hull', {})
                    new_hull = new_ship.get('hull', {})
                    hull_changes = {}
                    for k in new_hull:
                        if k in old_hull and new_hull[k] != old_hull[k]:
                            hull_changes[k] = new_hull[k]
                    if hull_changes:
                        section_changes['hull'] = hull_changes

                    old_weapons = old_ship.get('installed_weapons', [])
                    new_weapons = new_ship.get('installed_weapons', [])
                    if old_weapons != new_weapons:
                        section_changes['installed_weapons'] = new_weapons

                    if section_changes:
                        changes[section] = section_changes
                elif section == 'coordinates':
                    section_changes = {}
                    for key in new_state[section]:
                        if key in old_state[section] and new_state[section][key] != old_state[section][key]:
                            section_changes[key] = new_state[section][key]
                    if section_changes:
                        changes[section] = section_changes
                elif isinstance(new_state[section], dict):
                    section_changes = {}
                    for key in new_state[section]:
                        if key in old_state[section] and new_state[section][key] != old_state[section][key]:
                            section_changes[key] = new_state[section][key]
                    if section_changes:
                        changes[section] = section_changes
                else:
                    if new_state[section] != old_state[section]:
                        changes[section] = new_state[section]
            elif section in new_state:
                changes[section] = new_state[section]

        return changes

    def _handle_auto(self, command, state, player_name):
        """Включить авто-атаку"""
        parts = command.split()
        if len(parts) != 2:
            return {"message": "Использование: auto [weapon_id] или auto off"}

        weapon_id = parts[1]
        weapon_data = self.data.get_weapon(weapon_id)
        if not weapon_data:
            return {"message": f"Неизвестное оружие: {weapon_id}"}

        ship = state.get("ship", {})
        installed = ship.get("installed_weapons", [])
        if weapon_id not in installed:
            return {"message": f"Оружие {weapon_id} не установлено на корабле!"}

        self.auto_attack[player_name] = {
            "weapon": weapon_id,
            "active": True
        }

        return {"message": f"🔄 Авто-атака включена: {weapon_data['name']}"}

    def _handle_auto_off(self, player_name):
        """Выключить авто-атаку"""
        if player_name in self.auto_attack:
            del self.auto_attack[player_name]
            return {"message": "🔴 Авто-атака выключена"}
        return {"message": "Авто-атака не была включена"}

    def process_auto_attacks(self):
        """Обработка авто-атак (вызывается из фонового потока)"""
        for player_name, auto_data in list(self.auto_attack.items()):
            if not auto_data["active"]:
                continue

            if not self.enemy_logic.is_in_combat(player_name):
                continue

            state = self.enemy_logic.server.get_player_state(player_name) if self.enemy_logic.server else None
            if not state:
                continue

            weapon_id = auto_data["weapon"]

            # Проверяем кулдаун оружия
            now = time.time()
            if player_name not in self.weapon_cooldowns:
                self.weapon_cooldowns[player_name] = {}

            last_fire = self.weapon_cooldowns[player_name].get(weapon_id, 0)
            weapon_data = self.data.get_weapon(weapon_id)
            if not weapon_data:
                continue

            if now - last_fire < weapon_data["cooldown"]:
                continue  # кулдаун ещё не прошёл

            # Атакуем!
            self.weapon_cooldowns[player_name][weapon_id] = now

            hit_result, error = self.enemy_logic.player_hit_enemy(player_name, weapon_id, state)

            if error:
                continue

            if hit_result:
                if self.enemy_logic.server:
                    # Отправляем обновление состояния
                    if "state" in hit_result:
                        self.enemy_logic.server.save_player_state(player_name, hit_result["state"])
                        self.enemy_logic.server.send_to_player(player_name, {
                            "type": "update",
                            "data": {"hull": hit_result["state"]["hull"]}
                        })

                    # Отправляем сообщение
                    self.enemy_logic.server.send_to_player(player_name, {
                        "type": "message",
                        "data": f"[cyan]🔄 {hit_result['message']}[/cyan]"
                    })

                    # Отправляем кулдаун оружия
                    self.enemy_logic.server.send_to_player(player_name, {
                        "type": "weapon_cooldown",
                        "weapon": weapon_id,
                        "remaining": weapon_data["cooldown"],
                        "message": f"{weapon_data['name']} перезаряжается..."
                    })

                    # Если враг уничтожен - выключаем авто-атаку
                    if hit_result.get("enemy_destroyed"):
                        auto_data["active"] = False
                        self.enemy_logic.server.send_to_player(player_name, {
                            "type": "message",
                            "data": "[yellow]🔴 Авто-атака остановлена (враг уничтожен)[/yellow]"
                        })