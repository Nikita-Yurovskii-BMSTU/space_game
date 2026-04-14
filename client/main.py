from client.game_client import GameClient

if __name__ == "__main__":
    client = GameClient()
    try:
        client.run()
    except KeyboardInterrupt:
        pass