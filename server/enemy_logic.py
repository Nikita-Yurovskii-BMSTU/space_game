"""Логика поведения врагов"""

import time
import random
import math
import threading


class EnemyLogic:
    def __init__(self, data_loader):
        self.data = data_loader
        self.active_combats = {}  # {player_name: combat_data}
        self.enemy_attack_timers = {}  # {player_name: last_attack_time}
        self.enemy_move_timers = {}  # {player_name: last_move_time}

        # Ссылка на game_server для отправки сообщений
        self.server = None

        # Запускаем фоновый поток для врагов
        self.running = True
        self.combat_thread = threading.Thread(target=self._combat_loop, daemon=True)
        self.combat_thread.start()

    def set_server(self, server):
        """Установить ссылку на сервер для отправки обновлений"""
        self.server = server

    def stop(self):
        """Остановить фоновый поток"""
        self.running = False

    def _combat_loop(self):
        """Фоновый цикл обработки боёв"""
        while self.running:
            time.sleep(0.3)
            if self.server and hasattr(self.server, 'logic'):
                self.server.logic.process_auto_attacks()
            for player_name in list(self.active_combats.keys()):
                if self.server and hasattr(self.server, 'get_player_state'):
                    state = self.server.get_player_state(player_name)
                    if state:
                        combat, attack_result = self.update_combat(player_name, state)

                        if attack_result and self.server:
                            self.server.send_to_player(player_name, {
                                "type": "update",
                                "data": {"hull": attack_result["state"]["hull"]}
                            })
                            self.server.send_to_player(player_name, {
                                "type": "message",
                                "data": f"[red]💥 {attack_result['message']}[/red]"
                            })

    def start_combat(self, player_name, enemy_id, enemy_position, state):
        """Начать бой с врагом"""
        enemy_data = self.data.get_enemy(enemy_id)
        if not enemy_data:
            return None

        player_coords = state["coordinates"]
        distance = self._calculate_distance(
            player_coords["x"], player_coords["y"], player_coords["z"],
            enemy_position["x"], enemy_position["y"], enemy_position["z"]
        )

        combat_data = {
            "enemy_id": enemy_id,
            "enemy_data": enemy_data.copy(),
            "enemy_hull": enemy_data["hull"].copy(),
            "position": enemy_position.copy(),
            "distance": distance,
            "target_position": None
        }

        self.active_combats[player_name] = combat_data
        self.enemy_attack_timers[player_name] = 0
        self.enemy_move_timers[player_name] = 0

        return combat_data

    def update_combat(self, player_name, state):
        """Обновление состояния боя"""
        if player_name not in self.active_combats:
            return None, None

        combat = self.active_combats[player_name]
        player_coords = state["coordinates"]
        enemy_pos = combat["position"]

        distance = self._calculate_distance(
            player_coords["x"], player_coords["y"], player_coords["z"],
            enemy_pos["x"], enemy_pos["y"], enemy_pos["z"]
        )
        combat["distance"] = distance

        attack_result = self._try_attack(player_name, state, combat)
        move_result = self._try_move(player_name, state, combat)
        if move_result:
            combat = move_result
            self.active_combats[player_name] = combat

        return combat, attack_result

    def _try_attack(self, player_name, state, combat):
        """Попытка атаки игрока"""
        now = time.time()
        last_attack = self.enemy_attack_timers.get(player_name, 0)
        enemy_data = combat["enemy_data"]

        if now - last_attack < enemy_data["attack_cooldown"]:
            return None

        attack_range = enemy_data.get("attack_range", 60)
        if combat["distance"] > attack_range:
            return None

        self.enemy_attack_timers[player_name] = now
        damage = enemy_data["damage"]
        hull_parts = ["bow", "stern", "port", "starboard"]
        target_part = random.choice(hull_parts)

        new_state = state.copy()
        new_state['hull'] = state['hull'].copy()
        if 'ship' in new_state:
            new_state['ship'] = state['ship'].copy()
            new_state['ship']['hull'] = state['ship']['hull'].copy()
        new_state['stats'] = state.get('stats', {}).copy()

        new_state['hull'][target_part] = max(0, new_state['hull'][target_part] - damage)
        if 'ship' in new_state:
            new_state['ship']['hull'][target_part] = new_state['hull'][target_part]
        new_state['stats']['total_damage_taken'] = new_state['stats'].get('total_damage_taken', 0) + damage

        if self.server:
            self.server.save_player_state(player_name, new_state)

        return {
            "state": new_state,
            "message": f"{enemy_data['name']} атакует {target_part}! -{damage} HP",
            "target_part": target_part,
            "damage": damage
        }

    def _try_move(self, player_name, state, combat):
        """Попытка движения врага"""
        now = time.time()
        last_move = self.enemy_move_timers.get(player_name, 0)
        enemy_data = combat["enemy_data"]

        move_cooldown = 0.5
        if now - last_move < move_cooldown:
            return None

        attack_range = enemy_data.get("attack_range", 60)
        optimal_range = attack_range * 0.7
        speed = enemy_data.get("speed", 10)

        player_coords = state["coordinates"]
        enemy_pos = combat["position"]

        dx = player_coords["x"] - enemy_pos["x"]
        dy = player_coords["y"] - enemy_pos["y"]
        dz = player_coords["z"] - enemy_pos["z"]
        distance = combat["distance"]

        if distance < 0.1:
            return None

        dx /= distance
        dy /= distance
        dz /= distance

        if distance > attack_range:
            move_distance = min(speed, distance - optimal_range)
            direction = 1
        elif distance < optimal_range:
            move_distance = min(speed, optimal_range - distance)
            direction = -1
        else:
            return None

        self.enemy_move_timers[player_name] = now

        new_pos = {
            "x": enemy_pos["x"] + dx * move_distance * direction,
            "y": enemy_pos["y"] + dy * move_distance * direction,
            "z": enemy_pos["z"] + dz * move_distance * direction
        }

        combat["position"] = new_pos
        combat["distance"] = self._calculate_distance(
            player_coords["x"], player_coords["y"], player_coords["z"],
            new_pos["x"], new_pos["y"], new_pos["z"]
        )

        return combat

    def player_hit_enemy(self, player_name, weapon_id, state):
        """Игрок атакует врага"""
        if player_name not in self.active_combats:
            return None, "Вы не в бою!"

        combat = self.active_combats[player_name]
        weapon_data = self.data.get_weapon(weapon_id)
        if not weapon_data:
            return None, f"Неизвестное оружие: {weapon_id}"

        weapon_range = 100
        if combat["distance"] > weapon_range:
            return None, f"Враг слишком далеко! Дистанция: {combat['distance']:.1f}"

        damage = weapon_data["damage"]
        hull_parts = ["bow", "stern", "port", "starboard"]
        target_part = random.choice(hull_parts)

        combat["enemy_hull"][target_part] = max(0, combat["enemy_hull"][target_part] - damage)

        total_hull = sum(combat["enemy_hull"].values())
        if total_hull <= 0:
            enemy_data = combat["enemy_data"]
            loot = enemy_data.get("loot", {})

            new_state = state.copy()
            new_state['inventory'] = state.get('inventory', {}).copy()
            for item, amount in loot.items():
                new_state['inventory'][item] = new_state['inventory'].get(item, 0) + amount
            new_state['stats'] = state.get('stats', {}).copy()
            new_state['stats']['enemies_defeated'] = new_state['stats'].get('enemies_defeated', 0) + 1
            new_state['stats']['total_damage_dealt'] = new_state['stats'].get('total_damage_dealt', 0) + damage

            del self.active_combats[player_name]
            if player_name in self.enemy_attack_timers:
                del self.enemy_attack_timers[player_name]
            if player_name in self.enemy_move_timers:
                del self.enemy_move_timers[player_name]

            if self.server:
                self.server.save_player_state(player_name, new_state)

            loot_msg = ", ".join([f"{v} {k}" for k, v in loot.items()]) if loot else "ничего"

            return {
                "state": new_state,
                "enemy_destroyed": True,
                "message": f"💀 {enemy_data['name']} уничтожен! Получено: {loot_msg}"
            }, None

        new_state = state.copy()
        new_state['stats'] = state.get('stats', {}).copy()
        new_state['stats']['total_damage_dealt'] = new_state['stats'].get('total_damage_dealt', 0) + damage

        if self.server:
            self.server.save_player_state(player_name, new_state)

        return {
            "state": new_state,
            "enemy_hull": combat["enemy_hull"],
            "target_part": target_part,
            "damage": damage,
            "message": f"💥 Попадание по {target_part} врага! -{damage} HP"
        }, None

    def end_combat(self, player_name):
        """Принудительно завершить бой"""
        if player_name in self.active_combats:
            del self.active_combats[player_name]
        if player_name in self.enemy_attack_timers:
            del self.enemy_attack_timers[player_name]
        if player_name in self.enemy_move_timers:
            del self.enemy_move_timers[player_name]

    def is_in_combat(self, player_name):
        return player_name in self.active_combats

    def get_combat_info(self, player_name):
        if player_name not in self.active_combats:
            return None

        combat = self.active_combats[player_name]
        enemy_data = combat["enemy_data"]
        enemy_hull = combat["enemy_hull"]
        total_hull = sum(enemy_hull.values())
        max_hull = sum(enemy_data["hull"].values())

        return {
            "enemy_name": enemy_data["name"],
            "enemy_hull": enemy_hull,
            "total_hull": total_hull,
            "max_hull": max_hull,
            "distance": combat["distance"],
            "position": combat["position"]
        }

    @staticmethod
    def _calculate_distance(x1, y1, z1, x2, y2, z2):
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2 + (z2 - z1) ** 2)