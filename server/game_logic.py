"""Модуль игровой логики"""

from common.protocols import *
import time


class GameLogic:
    def __init__(self, database, data_loader):
        self.db = database
        self.data = data_loader
        self.last_action_time = {}
        self.cooldown_seconds = 3
        self.weapon_cooldowns = {}

    def _calculate_distance(self, x1, y1, z1, x2, y2, z2):
        """Расчёт расстояния между точками"""
        return ((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2) ** 0.5

    def _execute_command(self, command, state, player_name):
        """Выполнение команды без проверки кулдауна"""

        if command == CMD_HELP:
            return {"message": """Доступные команды:
- status - показать текущий статус
- systems - список всех систем
- stars - список звёзд в текущей системе
- scan - что вокруг (объекты в секторе)
- jump [system] - прыжок в другую систему (через врата)
- warp [star] - варп к другой звезде в системе
- move x 10 y 5 z -5 - перемещение в секторе
- damage bow 15 - нанести урон
- repair bow 20 - отремонтировать
- fire [weapon] - выстрелить
- weapons - список оружия
- stats - статистика
- save - сохранить
- quit - выход"""}

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
                message += f"- {obj['name']} ({obj['type']}) на дистанции {dist:.1f} {danger_icon}\n"
            return {"message": message}

        elif command.startswith("jump "):
            target_sys = command[5:].strip().lower()
            current_sys = state["coordinates"]["system"]

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

        elif command.startswith(CMD_MOVE):
            return self._handle_move(command, state)

        elif command.startswith(CMD_DAMAGE):
            return self._handle_damage(command, state)

        elif command.startswith(CMD_REPAIR):
            return self._handle_repair(command, state)

        elif command.startswith("fire"):
            return self._handle_fire(command, state, player_name)

        elif command == CMD_QUIT:
            return {"message": "До свидания!"}

        else:
            return {"message": f"Неизвестная команда: {command}"}

    def process_command(self, command, state, player_name):
        """Обработка игровых команд с кулдауном"""

        now = time.time()
        last = self.last_action_time.get(player_name, 0)

        if command.startswith((CMD_MOVE, CMD_DAMAGE, CMD_REPAIR, "fire", "jump", "warp")):
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
                if result and not result.get("weapon_cooldown"):
                    result["cooldown_after"] = {
                        "remaining": self.cooldown_seconds,
                        "message": "Системы перезаряжаются..."
                    }
                return result

        return self._execute_command(command, state, player_name)

    def _handle_fire(self, command, state, player_name):
        """Обработка выстрела из оружия"""
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

        new_state = state.copy()
        new_state['stats'] = state.get('stats', {}).copy()
        new_state['stats']['total_damage_dealt'] = new_state['stats'].get('total_damage_dealt', 0) + damage

        return {
            "message": f"💥 Выстрел из {weapon_data['name']}! Нанесено {damage} урона.",
            "state": new_state,
            "weapon_cooldown_after": {
                "weapon": weapon_id,
                "remaining": cooldown_time,
                "message": f"{weapon_data['name']} перезаряжается..."
            }
        }

    def _handle_move(self, command, state):
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
        return {
            "message": f"Перемещение: X:{coords['x']:.1f} Y:{coords['y']:.1f} Z:{coords['z']:.1f}",
            "state": new_state
        }

    def _handle_damage(self, command, state):
        parts = command.split()
        if len(parts) == 3:
            part, value = parts[1], int(parts[2])
            new_state = state.copy()
            new_state['hull'] = state['hull'].copy()
            if 'ship' in new_state:
                new_state['ship'] = state['ship'].copy()
                new_state['ship']['hull'] = state['ship']['hull'].copy()
            new_state['stats'] = state.get('stats', {}).copy()

            if part in new_state['hull']:
                new_state['hull'][part] = max(0, new_state['hull'][part] - value)
                if 'ship' in new_state:
                    new_state['ship']['hull'][part] = new_state['hull'][part]
                new_state['stats']['total_damage_taken'] = \
                    new_state['stats'].get('total_damage_taken', 0) + value
                return {
                    "message": f"⚠ Нанесен урон {part}: -{value}",
                    "state": new_state
                }

        return {"message": "Неверный формат. Используйте: damage [часть] [значение]"}

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