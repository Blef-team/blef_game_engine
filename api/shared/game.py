def get_player_by_nickname(players, nickname):
    filtered_players = [p for p in players if p["nickname"] == nickname]
    if filtered_players and filtered_players[0]:
        return filtered_players[0]

def get_nickname_by_uuid(players, player_uuid):
    filtered_players = [p for p in players if p["uuid"] == player_uuid]
    if filtered_players:
        return filtered_players[0]["nickname"]

def is_active_player(players, nickname):
    player = get_player_by_nickname(players, nickname)
    if player:
        return player["n_cards"] != 0
    return False

def get_revealed_hands(game, current_round, current_status, player_authenticated, player_nickname):
    revealed_hands = []
    if game["round_number"] < current_round or current_status == "Finished":
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"])]
    elif player_authenticated and game["round_number"] == current_round:
        revealed_hands = [hand for hand in game["hands"] if is_active_player(game["players"], hand["nickname"]) and hand["nickname"] == player_nickname]
    return revealed_hands

def censor_game(game, current_round, player_authenticated, player_nickname):
    revealed_hands = get_revealed_hands(game, current_round, game["status"], player_authenticated, player_nickname)

    private_players = []
    for player in game["players"]:
        private_players.append({key: player[key] for key in player if key != "uuid"})

    return {
        "admin_nickname": game["admin_nickname"],
        "public": game["public"],
        "room": game["room"],
        "status": game["status"],
        "round_number": game["round_number"],
        "max_cards": game["max_cards"],
        "players": private_players,
        "hands": revealed_hands,
        "cp_nickname": game["cp_nickname"],
        "history": game["history"],
        "last_modified": game["last_modified"]
    }
