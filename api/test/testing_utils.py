import os
from uuid import UUID

n_players_to_max_cards = {
    2: 11,
    3: 8,
    4: 6,
    5: 4,
    6: 4,
    7: 3,
    8: 3
}


def test_games(response):
    """ Test the /games endpoint response"""
    games = response.json()
    assert isinstance(games, list)
    for game in games:
        UUID(game.get("uuid"))
        assert isinstance(game.get("players"), list)
        assert all(isinstance(nickname, str) for nickname in game.get("players", []))
        assert isinstance(game.get("started"), bool)


def test_create(response):
    """ Test the /games/create endpoint response """
    new_game = response.json()
    assert isinstance(new_game, dict)
    uuid = UUID(new_game.get("game_uuid"))


def test_game_state(response):
    """ Test the /games/{id} endpoint response """
    game_state = response.json()
    assert isinstance(game_state, dict)
    assert "admin_nickname" in game_state
    assert isinstance(game_state.get("public"), bool)
    assert game_state.get("status") in ["Not started", "Running", "Finished"]
    assert game_state.get("round_number") in range(24)
    assert game_state.get("max_cards") in [0, 3, 4, 6, 8, 11]
    assert isinstance(game_state.get("players"), list)
    assert isinstance(game_state.get("hands"), list)
    assert "cp_nickname" in game_state
    assert isinstance(game_state.get("history"), list)


def test_running_game_state_with_player_uuid(response):
    test_game_state(response)
    game_state = response.json()
    assert isinstance(game_state.get("admin_nickname"), str) and game_state.get("admin_nickname")
    assert game_state.get("status") == "Running"
    assert game_state.get("round_number") in range(1, 24)
    assert game_state.get("players")
    n_players = len(game_state.get("players"))
    assert game_state.get("max_cards") == n_players_to_max_cards[n_players]
    for hand_player in game_state.get("hands"):
        assert isinstance(hand_player.get("nickname"), str) and hand_player.get("nickname")
        assert isinstance(hand_player.get("hand"), list) and hand_player.get("hand")
        for card in hand_player.get("hand"):
            assert card.get("value") in range(6)
            assert card.get("colour") in range(4)
    assert isinstance(game_state.get("cp_nickname"), str) and game_state.get("cp_nickname")
    for action in game_state.get("history"):
        assert isinstance(action["player"], str) and action["player"]
        assert action["action_id"] in range(90)


def test_join(response):
    """ Test the /games/{id}/join endpoint response """
    new_player = response.json()
    UUID(new_player.get("player_uuid"))


def test_start(response):
    message = response.json()
    assert message.get("message") == "Game started"
