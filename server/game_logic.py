"""Модуль игровой логики"""

from common.protocols import *
import time


class GameLogic:
    def __init__(self, database, data_loader):
        self.db = database
        self.data = data_loader
        self.last_action_time = {}  # глобальный кулдаун
        self.cooldown_seconds = 3

        # Кулдауны оружия
        self.weapon_cooldowns = {}  # {player_name: {weapon: last_use_time}}

    def _execute_command(self, command, state, player_name):
        """Выполнение команды без проверки кулдауна"""

        if command == CMD_HELP:
            return {"message": """Доступные команды:
- status - показать текущий статус
- move x 10 y 5 sector Бета - перемещение
- damage bow 15 - нанести урон
- repair bow 20 - отремонтировать (тратит ремкомплекты)
- fire laser - выстрелить из оружия
- weapons - список доступного оружия
- ships - список доступных кораблей
- stats - показать статистику
- save - принудительное сохранение
- quit - выход из игры"""}

        elif command == CMD_STATUS:
            return {"message": "Статус обновлен", "state": state}

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

        elif command == "ships":
            ships = self.data.get_all_ship_ids()
            message = "Доступные корабли:\n"
            for s_id in ships:
                s = self.data.get_ship(s_id)
                message += f"- {s_id}: {s['name']} (слоты: {s['weapon_slots']})\n"
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

        # Активные команды требуют глобального кулдауна
        if command.startswith((CMD_MOVE, CMD_DAMAGE, CMD_REPAIR, "fire")):
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

        # Остальные команды без кулдауна
        return self._execute_command(command, state, player_name)

    def _handle_fire(self, command, state, player_name):
        """Обработка выстрела из оружия"""
        parts = command.split()
        if len(parts) != 2:
            return {"message": "Использование: fire [weapon_id]"}

        weapon_id = parts[1]
        weapon_data = self.data.get_weapon(weapon_id)
        if not weapon_data:
            return {"message": f"Неизвестное оружие: {weapon_id}. Доступно: {', '.join(self.data.get_all_weapon_ids())}"}

        # Проверка, установлено ли оружие на корабле
        ship = state.get("ship", {})
        installed = ship.get("installed_weapons", [])
        if weapon_id not in installed:
            return {"message": f"Оружие {weapon_id} не установлено на корабле!"}

        # Проверка кулдауна оружия
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

        # Выстрел
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
            elif parts[i] == 'sector' and i + 1 < len(parts):
                new_state['coordinates']['sector'] = parts[i + 1]
                i += 2
            else:
                i += 1

        return {
            "message": f"Перемещение в сектор {new_state['coordinates']['sector']}",
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
                    # Для корабля сравниваем hull и installed_weapons
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