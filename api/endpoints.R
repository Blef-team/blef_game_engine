library(uuid)
library(magrittr)
library(readr)
library(dplyr)

source("api/game_routines.R")

#* Create a new game
#* @serializer unboxedJSON
#* @get /v1/games/create
function() {
  game_uuid <- UUIDgenerate(use.time = F)

  empty_game <- list(
    game_uuid = game_uuid,
    admin_nickname = NULL,
    status = "Not started",
    round_number = 0,
    max_cards = 0,
    players = data.frame(uuid = character(), nickname = character(), n_cards = numeric()), # Player uuids not public
    hands = data.frame(nickname = character(), value = numeric(), colour = numeric()),
    cp_nickname = NULL,
    history = data.frame(nickname = character(), action_id = numeric())
  )
  saveRDS(empty_game, file = get_path(game_uuid))

  list(game_uuid = game_uuid)
}

#* Add a player to a game
#* @serializer unboxedJSON
#* @param nickname The nickname chosen by the user.
#* @get /v1/games/<game_uuid>/join
function(game_uuid, nickname, res) {

  player_uuid <- UUIDgenerate(use.time = F)
  game <- readRDS(get_path(game_uuid))
  nick_taken <- nickname %in% game$players$nickname
  if (!nick_taken & game$status == "Not started") {
    if (nrow(game$players) == 0) game$admin_nickname <- nickname
    game$players %<>% rbind(data.frame(uuid = player_uuid, nickname = nickname, n_cards = 0)) %>%
      mutate(uuid = as.character(uuid), nickname = as.character(nickname))

    saveRDS(game, get_path(game_uuid))
    list(player_uuid = player_uuid)
  } else if (nick_taken) {
    res$status <- 409
    list(error = "Nickname already taken")
  } else if (game$status != "Not started") {
    res$status <- 405
    list(error = "Game already started")
  }
}

#* Start the game
#* @serializer unboxedJSON
#* @param admin_uuid The identifier of the admin, passed as verification.
#* @get /v1/games/<game_uuid>/start
function(game_uuid, admin_uuid, res) {

  game <- readRDS(get_path(game_uuid))
  auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]

  n_players <- nrow(game$players)

  if (auth_correct & game$status == "Not started" & n_players %in% 2:8) {

    game$status <- "Running"
    game$round_number <- 1

    # Determine maximum number of cards
    if (n_players == 2) game$max_cards <- 11
    if (n_players != 2) game$max_cards <- floor(24 / n_players)

    # Give each player 1 card
    game$players$n_cards <- rep(1, nrow(game$players))

    # Shuffle the order of the players
    game$players <- game$players[order(rnorm(n_players)), ]

    # Deal cards
    game$hands <- draw_cards(game$players)

    # Fill in the current player
    game$cp_nickname <- game$players$nickname[1]

    # Save current game data
    saveRDS(game, get_path(game_uuid))

    res$status <- 202
    list(message = "Game started")
  } else if (!n_players %in% 2:8) {
    res$status <- 405
    list(message = "Number of players not between 2 and 8")
  } else if (game$status != "Not started") {
    res$status <- 405
    list(message = "Game already started")
  } else if (!auth_correct) {
    res$status <- 403
    list(error = "Admin UUID does not match")
  }
}

#* Get the game state
#* @serializer unboxedJSON
#* @param player_uuid The UUID of the player whose cards the user wants to see before the round finishes.
#* @param requested_r The round for which information is requested. If no round specified, current round info is returned.
#* @get /v1/games/<game_uuid>
function(game_uuid, player_uuid = "", res, requested_r = -1) {

  current_r <- readRDS(get_path(game_uuid))$round_number
  if (requested_r == -1 | requested_r == current_r) {
    r <- current_r
    game <- readRDS(get_path(game_uuid))
  } else {
    r <- requested_r
    game <- readRDS(get_path(game_uuid, r))
  }

  auth_attempt <-player_uuid != ""
  auth_success <- player_uuid %in% game$players$uuid
  auth_problem <- auth_attempt & !auth_success

  if (!auth_problem & r %in% 0:current_r) {

    if (r < current_r) {
      revealed_hands <- jsonise_hands(game)
    } else if (r == current_r & auth_success) {
      user_nickname <- game$players %>% filter(uuid == player_uuid) %>% pull(nickname)
      revealed_hands <- jsonise_hands(game, nicknames = user_nickname)
    } else if (r == current_r & !auth_success) {
      revealed_hands <- data.frame()
    }
    privatised_players <- game$players %<>% select(-uuid)

    return(
      list(
        admin_nickname = game$admin_nickname,
        status = game$status,
        round_number = game$round_number,
        max_cards = game$max_cards,
        players = privatised_players,
        hands = revealed_hands,
        cp_nickname = game$cp_nickname,
        history = game$history
      )
    )

  } else if (auth_problem) {
    res$status <- 400
    list(message = "The UUID does not match any player")
  } else if (r > current_r) {
    res$status <- 400
    list(message = "Round parameter too high")
  }
}

#* Make a move
#* @serializer unboxedJSON
#* @param player_uuid The UUID of the current player for authentication.
#* @param action_id The id of the action (bet or check).
#* @get /v1/games/<game_uuid>/play
function(game_uuid, player_uuid, res, action_id) {
  action_id <- as.numeric(action_id)
  game <- readRDS(get_path(game_uuid))
  auth_success <- player_uuid == game$players$uuid[game$players$nickname == game$cp_nickname]

  if (nrow(game$history) == 0) {
    action_allowed <- action_id %in% 0:87
  } else {
    action_allowed <- action_id %in% 0:88 & action_id > game$history[nrow(game$history), 2]
  }

  if (auth_success & action_allowed) {

    # If the action was a bet
    if (action_id != 88) {

      # Attach action to history
      game$history %<>% rbind(c(game$cp_nickname, action_id)) %>% format_history()

      # Increment the current player
      if (game$cp_nickname == tail(game$players$nickname, 1)) {
        game$cp_nickname <- game$players$nickname[1]
      } else {
        game$cp_nickname <- game$players$nickname[which(game$players$nickname == game$cp_nickname) + 1]
      }

      # Save game state
      saveRDS(game, get_path(game_uuid))

    } else if (action_id == 88) {
      # If the action was a check

      last_bet <- game$history[nrow(game$history), 2] %>% unlist()
      set_exists <- determine_set_existence(game$hands, last_bet)

      # Determine losing player. If cp is 1st in the table and the previous player lost, go to last player in the table
      if (set_exists) {
        losing_player_i <- which(game$players$nickname == game$cp_nickname)
      } else if (!set_exists & game$cp_nickname == game$players$nickname[1]) {
        losing_player_i <- nrow(game$players)
      } else if (!set_exists & game$cp_nickname != game$players$nickname[1]) {
        losing_player_i <- which(game$players$nickname == game$cp_nickname) - 1
      }
      game$history %<>% rbind(c(game$cp_nickname, 88)) %>% format_history()
      game$history %<>% rbind(c(game$players$nickname[losing_player_i], 89))

      # Save snapshot of the game
      saveRDS(game, get_path(game_uuid, game$round_number))

      # Add a card to the losing player
      game$players$n_cards[losing_player_i] %<>% add(1)

      # If a player surpasses max cards, finish game or only kick them out
      if (game$players$n_cards[losing_player_i] > game$max_cards) {
        game$players <- game$players[-losing_player_i, ]
        if (nrow(game$players) == 1) {
          game$status <- "Finished"
          game$cp_nickname <- NULL
        } else {
          game$round_number %<>% add(1)
          game$history <- data.frame(nickname = character(), action_id = numeric())
          game$hands <- draw_cards(game$players)
          # If the checking player was eliminated, the one who now occupies the same row should be the next player
          # Otherwise the current player doesn't change
          if (game$players$nickname[losing_player_i] == game$cp_nickname) {
            if (losing_player_i > nrow(game$players)) new_cp_i <- 1
            if (losing_player_i <= nrow(game$players)) new_cp_i <- losing_player_i
          }
        }
      } else {
        # If no one should be kicked out, increment round number, redraw cards and set new current player
        game$round_number %<>% add(1)
        game$history <- data.frame(nickname = character(), action_id = numeric())
        game$hands <- draw_cards(game$players)
        game$cp_nickname <- game$players$nickname[losing_player_i]
      }

      # Save game state
      saveRDS(game, get_path(game_uuid))
    }
  } else if (!auth_success) {
    res$status <- 400
    list(message = "The submitted UUID does not match the UUID of the current player")
  } else if (!action_allowed) {
    res$status <- 400
    list(message = "Action with this ID is not allowed")
  }
}
