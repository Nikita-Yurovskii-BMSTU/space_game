"""Общие протоколы и константы для клиента и сервера"""

# Типы сообщений
MSG_AUTH = "auth"
MSG_AUTH_SUCCESS = "auth_success"
MSG_GAME_STATE = "game_state"
MSG_UPDATE = "update"
MSG_MESSAGE = "message"
MSG_COOLDOWN = "cooldown"
MSG_ERROR = "error"

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
MSG_WEAPON_COOLDOWN = "weapon_cooldown"