from server.game_server import GameServer

if __name__ == "__main__":
    server = GameServer()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
        print("\n✓ Сервер остановлен")