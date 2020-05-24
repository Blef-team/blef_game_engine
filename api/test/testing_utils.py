import os
from uuid import UUID


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


def test_join(response):
    """ Test the /games/{id}/join endpoint response """
    new_player = response.json()
    UUID(new_player.get("player_uuid"))


def test_start(response):
    message = response.json()
    assert message.get("message") == "Game started"
