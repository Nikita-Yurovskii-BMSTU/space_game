"""Общие протоколы и константы для клиента и сервера"""

# Типы сообщений
MSG_AUTH = "auth"
MSG_AUTH_SUCCESS = "auth_success"
MSG_GAME_STATE = "game_state"
MSG_UPDATE = "update"
MSG_MESSAGE = "message"
MSG_COOLDOWN = "cooldown"
MSG_ERROR = "error"
MSG_WEAPON_COOLDOWN = "weapon_cooldown"

# Команды
CMD_HELP = "help"
CMD_STATUS = "status"
CMD_STATS = "stats"
CMD_MOVE = "move"
CMD_DAMAGE = "damage"
CMD_REPAIR = "repair"
CMD_SAVE = "save"
CMD_QUIT = "quit"
CMD_LOGIN = "login"
CMD_REGISTER = "register"

# Начальные значения
DEFAULT_COORDINATES = {"x": 0, "y": 0, "z": 0, "sector": "Альфа"}
DEFAULT_HULL = {"bow": 100, "stern": 100, "port": 100, "starboard": 100}
DEFAULT_INVENTORY = {"repair_kits": 3, "missiles": 8, "scrap": 150}
DEFAULT_WEAPONS = {"laser": 100, "missile": 85, "railgun": 95}
DEFAULT_STATS = {
    "enemies_defeated": 0,
    "missions_completed": 0,
    "total_damage_dealt": 0,
    "total_damage_taken": 0
}

# ========== СКОРОСТИ В АСТРОНОМИЧЕСКИХ ЕДИНИЦАХ ==========
# 1 АЕ = 149 597 870 км ~ 150 млн км

MOVE_SPEED = 0.0005       # 0.0005 АЕ/сек ≈ 75 000 км/сек (быстро, но реалистично для игры)
WARP_SPEED = 0.5          # 0.5 АЕ/сек ≈ 75 млн км/сек (варп в 1000 раз быстрее)
JUMP_SPEED = 2            # прыжок между системами 2 секунды

# Дистанции
WARP_MIN_DISTANCE = 0.01  # минимальная дистанция для варпа (0.01 АЕ ≈ 1.5 млн км)

# Типичные дистанции (для справки)
# Земля - Солнце: 1 АЕ
# Юпитер - Солнце: 5.2 АЕ
# Ближайшая звезда: 268 000 АЕ (4.24 световых года)