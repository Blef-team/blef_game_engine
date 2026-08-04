from shared.response import response_payload, parameter_error_payload, error_payload, conflict_payload, internal_error_payload, nickname_rejected_payload
from shared.profanity_filter import is_offensive
from shared.inputs import parse_nickname, parse_team
from shared.db import update_players_conditionally
from shared.constants import GameStatus, validate_avatar
from shared.game import create_player, calculate_actual_max_cards, unset_human_readiness
from shared.decorators import validate_game_request
from shared.logging import logger

@validate_game_request(
    required_status=GameStatus.NOT_STARTED, 
    status_error_message="Game already started"
)
def lambda_handler(event, context, body, game):
    try:
        players = game.get("players", [])
        if len(players) == 8:
            return error_payload(403, "Game room full")

        nickname = body.get("nickname")
        if not nickname:
            return parameter_error_payload("nickname", nickname, message="Nickname missing - please supply it")
        try:
            nickname = parse_nickname(nickname)
        except ValueError as err:
            return parameter_error_payload("nickname", nickname, message=str(err))

        if is_offensive(nickname):
            return nickname_rejected_payload(reason="profanity")

        if nickname in [p["nickname"] for p in players]:
            return parameter_error_payload("nickname", nickname, message="Nickname already taken")

        avatar, avatar_error = validate_avatar(body)
        if avatar_error:
            return parameter_error_payload("avatar", None, message=avatar_error)

        try:
            team = parse_team(body.get("team"))
        except ValueError as err:
            return parameter_error_payload("team", body.get("team"), message=str(err))

        new_player = create_player(game, nickname, avatar, team)
        players.append(new_player)
        if team is not None:
            players = unset_human_readiness(players)
        admin_nickname = game.get("admin_nickname") or new_player.get("nickname")
        max_cards = calculate_actual_max_cards(game.get("rules", {}), len(players))

        if update_players_conditionally(game["game_uuid"], players, game["last_modified"], admin_nickname=admin_nickname, max_cards=max_cards):
            return response_payload(200, {"player_uuid": new_player.get("uuid")})
        
        logger.info(f"Join failed for '{nickname}' due to race condition.")
        return conflict_payload()

    except Exception as err:
        return internal_error_payload(err)
