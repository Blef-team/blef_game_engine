library(uuid)
library(magrittr)
library(readr)
library(dplyr)
library(stringr)

source("game_routines.R")

validate_uuid <- function(x) str_detect(x, "\\b[0-9a-fA-F]{8}\\b-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-\\b[0-9a-fA-F]{12}\\b")

#* Get the number of active games
#* @serializer unboxedJSON
#* @get /v2/games/active
function(res) {
  # Count games active at most 30 minutes ago
  active_game_count <- strtoi(system("find ~/game_data/v2/ \\( -name '*.RDS' \\) -mmin -30 | grep -Ev '_[0-9]+.RDS' | wc -l", intern = TRUE))
  res$status <- 200
  return(list(active_games = active_game_count))
}


#* Get the service version
#* @serializer unboxedJSON
#* @get /v2/version
function(res) {
  # Return the service version
  list(version = "2.3.0")
}

#* Create a new game
#* @serializer unboxedJSON
#* @get /v2/games/create
function(res) {

  # Count started games, prevent abuse
  games_count <- length(grep(list.files(game_data_path, pattern=".RDS$"), pattern="(_[0-9]+.RDS$)", inv=T))
  if (games_count > 10000) {
    res$status <- 429
    return(list(message = "Too many games started"))
  }

  game_uuid <- UUIDgenerate(use.time = F)

  empty_game <- list(
    game_uuid = game_uuid,
    admin_nickname = NULL,
    public = F,
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
#* @get /v2/games/<game_uuid>/join
function(game_uuid, nickname, res) {

  # Check if the supplied game UUID is a valid UUID before loading the game
  if(!validate_uuid(game_uuid)) {
    res$status <- 400
    return(list(error = "Invalid game UUID"))
  }

  # Check if game exists
  if(!file.exists(get_path(game_uuid))) {
    res$status <- 400
    return(list(error = "Game does not exist"))
  }

  game <- readRDS(get_path(game_uuid))

  # Check whether the game has already started, in which case users shouldn't be able to join
  if (game$status != "Not started") {
    res$status <- 403
    return(list(error = "Game already started"))
  }

  # Check if the game is not full
  if (nrow(game$players) == 8) {
    res$status <- 403
    return(list(error = "The game room is full"))
  }

  # Check if the nickname argument has been supplied
  if(missing(nickname)) {
    res$status <- 400
    return(list(error = "Nickname missing - please supply it"))
  }

  # Check whether the nickname is not longer than 32 characters
  if(str_length(nickname) > 32) {
    res$status <- 400
    return(list(error = "Nickname too long - must be within 32 characters"))
  }

  # Check whether the nickname is in an acceptable format
  if(!str_detect(nickname, "^[a-zA-Z]\\w*$")) {
    res$status <- 400
    return(list(error = "Nickname must start with a letter and only contain alphanumeric characters"))
  }

  # Check whether the nickname is available
  if (nickname %in% game$players$nickname) {
    res$status <- 409
    return(list(error = "Nickname already taken"))
  }

  player_uuid <- UUIDgenerate(use.time = F)
  if (nrow(game$players) == 0) game$admin_nickname <- nickname
  game$players %<>% rbind(data.frame(uuid = player_uuid, nickname = nickname, n_cards = 0)) %>%
    mutate(uuid = as.character(uuid), nickname = as.character(nickname))

  saveRDS(game, get_path(game_uuid))
  list(player_uuid = player_uuid)
}

#* Start the game
#* @serializer unboxedJSON
#* @param admin_uuid The identifier of the admin, passed as verification.
#* @get /v2/games/<game_uuid>/start
function(game_uuid, admin_uuid, res) {

  # Check if the supplied game UUID is a valid UUID before loading the game
  if (!validate_uuid(game_uuid)) {
    res$status <- 400
    return(list(error = "Invalid game UUID"))
  }

  # Check if game exists
  if(!file.exists(get_path(game_uuid))) {
    res$status <- 400
    return(list(error = "Game does not exist"))
  }

  # See if the game has already started
  game <- readRDS(get_path(game_uuid))
  if (game$status != "Not started") {
    res$status <- 403
    return(list(error = "Game already started"))
  }

  # Check if admin UUID has been supplied
  if(missing(admin_uuid)) {
    res$status <- 400
    return(list(error = "Admin UUID missing - please supply it"))
  }

  # Check if the supplied admin UUID is a valid UUID
  admin_uuid %<>% str_to_lower()
  if (!validate_uuid(admin_uuid)) {
    res$status <- 400
    return(list(error = "Invalid admin UUID"))
  }

  # Check whether the supplied UUID matches the admin UUID
  auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]
  if (!auth_correct) {
    res$status <- 403
    return(list(error = "Admin UUID does not match"))
  }

  # Check if we have at least 2 players. We won't have too many players because the join endpoint takes care of that
  n_players <- nrow(game$players)
  if (n_players < 2) {
    res$status <- 403
    return(list(error = "At least 2 players needed to start a game"))
  }

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
}

#* Get the game state
#* @serializer unboxedJSON
#* @param player_uuid The UUID of the player whose cards the user wants to see before the round finishes.
#* @param round The round for which information is requested. If no round specified, current round info is returned.
#* @get /v2/games/<game_uuid>
function(game_uuid, player_uuid = "", res, round = -1) {

  player_uuid %<>% str_to_lower()

  # Check if the supplied game UUID is a valid UUID before loading the game
  if(!validate_uuid(game_uuid)) {
    res$status <- 400
    return(list(error = "Invalid game UUID"))
  }

  # Check if game exists
  if(!file.exists(get_path(game_uuid))) {
    res$status <- 400
    return(list(error = "Game does not exist"))
  }

  # Check whether, if a player UUID has been supplied, it is a valid UUID
  if (!player_uuid == "" & !validate_uuid(player_uuid)) {
    res$status <- 400
    return(list(error = "Invalid player UUID"))
  }

  # Check whether the round parameter is OK
  round %<>% as.numeric()
  current_r <- readRDS(get_path(game_uuid))$round_number
  if (round > current_r) {
    res$status <- 400
    return(list(error = "The game has not reached this round"))
  }
  if (round < -1 | round == 0 | round %% 1 != 0) {
    res$status <- 400
    return(list(error = "The round parameter is invalid - must be an integer between 1 and the current round, or -1, or blank"))
  }

  # If the game is finished and last round is queried, return the snapshot of the state before card was added and status changed
  present_status <- readRDS(get_path(game_uuid))$status
  if (round == -1 | (round == current_r & present_status == "Running")) {
    r <- current_r
    game <- readRDS(get_path(game_uuid))
  } else {
    r <- round
    game <- readRDS(get_path(game_uuid, r))
  }

  # Authenticate a player
  auth_attempt <-player_uuid != ""
  auth_success <- player_uuid %in% game$players$uuid
  auth_problem <- auth_attempt & !auth_success
  if (auth_problem) {
    res$status <- 400
    return(list(error = "The UUID does not match any active player"))
  }

  # Fetch the appropriate hands
  if (r < current_r | present_status == "Finished") {
    revealed_hands <- jsonise_hands(game)
  } else if (r == current_r & auth_success) {
    user_nickname <- game$players %>% filter(uuid == player_uuid) %>% pull(nickname)
    revealed_hands <- jsonise_hands(game, nicknames = user_nickname)
  } else if (r == current_r & !auth_success) {
    revealed_hands <- data.frame()
  }

  # Hide UUIDs
  privatised_players <- game$players %<>% select(-uuid)

  return(
    list(
      admin_nickname = game$admin_nickname,
      public = game$public,
      status = game$status,
      round_number = game$round_number,
      max_cards = game$max_cards,
      players = privatised_players,
      hands = revealed_hands,
      cp_nickname = game$cp_nickname,
      history = game$history
    )
  )
}

#* Make a move
#* @serializer unboxedJSON
#* @param player_uuid The UUID of the current player for authentication.
#* @param action_id The id of the action (bet or check).
#* @get /v2/games/<game_uuid>/play
function(game_uuid, player_uuid, res, action_id) {

  # Check if the supplied game UUID is a valid UUID before loading the game
  if (!validate_uuid(game_uuid)) {
    res$status <- 400
    return(list(error = "Invalid game UUID"))
  }

  # Check if game exists
  if (!file.exists(get_path(game_uuid))) {
    res$status <- 400
    return(list(error = "Game does not exist"))
  }

  game <- readRDS(get_path(game_uuid))
  # Check if game is currently running
  if (game$status == "Not started") {
    res$status <- 400
    return(list(error = "This game has not yet started"))
  }
  if (game$status == "Finished") {
    res$status <- 400
    return(list(error = "This game has already finished"))
  }

  # Check if player UUID has been supplied
  if (missing(player_uuid)) {
    res$status <- 400
    return(list(error = "Player UUID missing - please supply it"))
  }

  player_uuid %<>% str_to_lower()
  # Check whether the player UUID is a valid UUID
  if (!validate_uuid(player_uuid)) {
    res$status <- 400
    return(list(error = "Invalid player UUID"))
  }

  # Check if the player UUID matches the UUID of the current player
  auth_success <- player_uuid == game$players$uuid[game$players$nickname == game$cp_nickname]
  if (!auth_success) {
    res$status <- 400
    return(list(error = "The submitted UUID does not match the UUID of the current player"))
  }

  # Check if action ID has been supplied
  if (missing(action_id)) {
    res$status <- 400
    return(list(error = "Action ID missing - please supply it"))
  }

  # Check whether the particular action is allowed right now
  action_id <- as.numeric(action_id)
  if (!action_id %in% c(0:88)) {
    res$status <- 400
    return(list(error = "Action ID must be an integer between 0 and 88"))
  }

  if (nrow(game$history) == 0) {
    action_allowed <- action_id %in% 0:87
  } else {
    action_allowed <- action_id %in% 0:88 & action_id > game$history[nrow(game$history), 2]
  }
  if (!action_allowed) {
    res$status <- 400
    return(list(error = "This action not allowed right now"))
  }

  # If the action was a bet
  if (action_id != 88) {

    # Attach action to history
    game$history %<>% rbind(c(game$cp_nickname, action_id)) %>% format_history()

    # Increment the current player
    game$cp_nickname <- find_next_active_player(game$players, game$cp_nickname)

    # Save game state
    saveRDS(game, get_path(game_uuid))

  } else { # If the action was a check

    last_bet <- tail(game$history$action_id, 1)
    set_exists <- determine_set_existence(game$hands, last_bet)

    # Determine losing player (the last player in the history table)
    if (set_exists) {
      losing_player <- game$cp_nickname
    } else if (!set_exists) {
      losing_player <- tail(game$history$player, 1)
    }
    game$history %<>% rbind(c(game$cp_nickname, 88)) %>% format_history()
    game$history %<>% rbind(c(losing_player, 89)) %>% format_history()

    # Keep in mind the cp_nickname but nullify it before saving snapshot, to not confuse UIs
    cp_nickname <- game$cp_nickname
    game$cp_nickname <- NULL

    # Save snapshot of the game
    saveRDS(game, get_path(game_uuid, game$round_number))

    # Add a card to the losing player
    game$players$n_cards[game$players$nickname == losing_player] %<>% add(1)

    # If a player surpasses max cards, make them inactive (set their n_cards to 0) and either finish the game or set up next round
    if (game$players$n_cards[game$players$nickname == losing_player] > game$max_cards) {
      game$players$n_cards[game$players$nickname == losing_player] <- 0
      if (sum(game$players$n_cards > 0) == 1) {
        game$status <- "Finished"
      } else {
        # If the game is not finished, increment round number, redraw cards and set new current player
        game$round_number %<>% add(1)
        game$history <- data.frame(nickname = character(), action_id = numeric())
        game$hands <- draw_cards(game$players)
        # If the checking player was eliminated, figure out the next player
        # Otherwise the current player doesn't change
        if (losing_player == cp_nickname) {
          game$cp_nickname <- find_next_active_player(game$players, cp_nickname)
        } else {
          game$cp_nickname <- cp_nickname
        }
      }
    } else {
      # If no one is kicked out, picking the next player is easier
      game$round_number %<>% add(1)
      game$history <- data.frame(nickname = character(), action_id = numeric())
      game$hands <- draw_cards(game$players)
      game$cp_nickname <- losing_player
    }

    # Save game state
    saveRDS(game, get_path(game_uuid))
  }
}

#* Make game public
#* @serializer unboxedJSON
#* @param admin_uuid The identifier of the admin, passed as verification.
#* @get /v2/games/<game_uuid>/make-public
function(game_uuid, admin_uuid, res) {

  admin_uuid %<>% str_to_lower()

  # Check if the supplied game UUID is a valid UUID before loading the game
  if (!validate_uuid(game_uuid)) {
    res$status <- 400
    return(list(error = "Invalid game UUID"))
  }

  # Check if game exists
  if(!file.exists(get_path(game_uuid))) {
    res$status <- 400
    return(list(error = "Game does not exist"))
  }

  # See if the game has already started
  game <- readRDS(get_path(game_uuid))
  if (game$status != "Not started") {
    res$status <- 403
    return(list(error = "Cannot make the change - game already started"))
  }

  # Check if admin UUID has been supplied
  if(missing(admin_uuid)) {
    res$status <- 400
    return(list(error = "Admin UUID missing - please supply it"))
  }

  # Check if the supplied admin UUID is a valid UUID
  if (!validate_uuid(admin_uuid)) {
    res$status <- 400
    return(list(error = "Invalid admin UUID"))
  }

  # Check whether the supplied UUID matches the admin UUID
  auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]
  if (!auth_correct) {
    res$status <- 403
    return(list(error = "Admin UUID does not match"))
  }

  # Check whether the request isn't redundant
  if (game$public == T) {
    res$status <- 200
    return(list(error = "Request redundant - game already public"))
  }

  game$public <- T

  # Save current game data
  saveRDS(game, get_path(game_uuid))

  res$status <- 200
  list(message = "Game made public")
}

#* Make game private
#* @serializer unboxedJSON
#* @param admin_uuid The identifier of the admin, passed as verification.
#* @get /v2/games/<game_uuid>/make-private
function(game_uuid, admin_uuid, res) {

  admin_uuid %<>% str_to_lower()

  # Check if the supplied game UUID is a valid UUID before loading the game
  if (!validate_uuid(game_uuid)) {
    res$status <- 400
    return(list(error = "Invalid game UUID"))
  }

  # Check if game exists
  if(!file.exists(get_path(game_uuid))) {
    res$status <- 400
    return(list(error = "Game does not exist"))
  }

  # See if the game has already started
  game <- readRDS(get_path(game_uuid))
  if (game$status != "Not started") {
    res$status <- 403
    return(list(error = "Cannot make the change - game already started"))
  }

  # Check if admin UUID has been supplied
  if(missing(admin_uuid)) {
    res$status <- 400
    return(list(error = "Admin UUID missing - please supply it"))
  }

  # Check if the supplied admin UUID is a valid UUID
  if (!validate_uuid(admin_uuid)) {
    res$status <- 400
    return(list(error = "Invalid admin UUID"))
  }

  # Check whether the supplied UUID matches the admin UUID
  auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]
  if (!auth_correct) {
    res$status <- 403
    return(list(error = "Admin UUID does not match"))
  }

  # Check whether the request isn't redundant
  if (game$public == F) {
    res$status <- 200
    return(list(error = "Request redundant - game already private"))
  }

  game$public <- F

  # Save current game data
  saveRDS(game, get_path(game_uuid))

  res$status <- 200
  list(message = "Game made private")
}

#* List public games
#* @serializer unboxedJSON
#* @get /v2/games
function() {
  files <- list.files(game_data_path, full.names = T)

  # Check if there are any games at all
  if (length(files) == 0) {
    return(list())
  }

  snapshots <- str_detect(files, "_\\d")
  relevant_files <- files[!snapshots]

  contents <- lapply(relevant_files, readRDS)
  public <- sapply(contents, extract2, var = "public")

  lapply(which(public), function(i) {
    content <- contents[[i]]
    list(
      uuid = relevant_files[i] %>% str_remove(paste0(game_data_path, "/")) %>% str_remove("\\.RDS"),
      players = as.list(content$players$nickname),
      started = content$status != "Not started"
    )
  })
}
