library(uuid)
library(magrittr)
library(readr)
library(dplyr)
library(stringr)

source("game_routines.R")

validate_uuid <- function(x) str_detect(x, "\\b[0-9a-f]{8}\\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\\b[0-9a-f]{12}\\b")

#* Create a new game
#* @serializer unboxedJSON
#* @get /v1/games/create
function(res) {
  
  # Count started games, prevent abuse
  games_count <- length(grep(list.files("../game_data", pattern=".RDS$"), pattern="(_[0-9]+.RDS$)", inv=T))
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
#* @get /v1/games/<game_uuid>/join
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
#* @get /v1/games/<game_uuid>/start
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
    res$status <- 405
    return(list(error = "Game already started"))
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
  
  # Check if we have at least 2 players. We won't have too many players because the join endpoint takes care of that
  n_players <- nrow(game$players)
  if (n_players < 2) {
    res$status <- 405
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
#* @get /v1/games/<game_uuid>
function(game_uuid, player_uuid = "", res, round = -1) {
  
  game_uuid_valid <- validate_uuid(game_uuid)
  player_uuid_valid_or_empty <- player_uuid == "" | validate_uuid(player_uuid)
  
  if (game_uuid_valid & player_uuid_valid_or_empty) {
    
    game_path <- get_path(game_uuid)
    
    if(file.exists(game_path)) {
      current_r <- readRDS(game_path)$round_number
      if (round == -1 | round == current_r) {
        r <- current_r
        game <- readRDS(get_path(game_uuid))
      } else {
        r <- as.numeric(round)
        game <- readRDS(get_path(game_uuid, r))
      }
      
      auth_attempt <-player_uuid != ""
      auth_success <- player_uuid %in% game$players$uuid
      auth_problem <- auth_attempt & !auth_success
      
      if (!auth_problem & r %in% 0:current_r) {
        
        if (r < current_r | game$status == "Finished") {
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
        
      } else if (auth_problem) {
        res$status <- 400
        list(message = "The UUID does not match any active player")
      } else if (r > current_r) {
        res$status <- 400
        list(message = "Round parameter too high")
      }
    } else {
      res$status <- 400
      list(message = "Game does not exist")
    }
  } else if (!game_uuid_valid) {
    res$status <- 400
    list(error = "Invalid game UUID")
  } else if (!player_uuid_valid_or_empty) {
    res$status <- 400
    list(error = "Invalid player UUID")
  }
}

#* Make a move
#* @serializer unboxedJSON
#* @param player_uuid The UUID of the current player for authentication.
#* @param action_id The id of the action (bet or check).
#* @get /v1/games/<game_uuid>/play
function(game_uuid, player_uuid, res, action_id) {
 
  game_uuid_valid <- validate_uuid(game_uuid)
  player_uuid_valid <- validate_uuid(player_uuid)
  
  if (game_uuid_valid & player_uuid_valid) {
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
        game$cp_nickname <- find_next_active_player(game$players, game$cp_nickname)
        
        # Save game state
        saveRDS(game, get_path(game_uuid))
        
      } else if (action_id == 88) {
        # If the action was a check
        
        last_bet <- tail(game$history$action_id, 1)
        set_exists <- determine_set_existence(game$hands, last_bet)
        
        # Determine losing player (the last player in the history table)
        if (set_exists) {
          losing_player <- game$cp_nickname
        } else if (!set_exists) {
          losing_player <- tail(game$history$player, 1)
        } 
        game$history %<>% rbind(c(game$cp_nickname, 88)) %>% format_history()
        game$history %<>% rbind(c(losing_player, 89))
        
        # Save snapshot of the game
        saveRDS(game, get_path(game_uuid, game$round_number))
        
        # Add a card to the losing player
        game$players$n_cards[game$players$nickname == losing_player] %<>% add(1)
        
        # If a player surpasses max cards, make them inactive (set their n_cards to 0) and either finish the game or set up next round
        if (game$players$n_cards[game$players$nickname == losing_player] > game$max_cards) {
          game$players$n_cards[game$players$nickname == losing_player] <- 0
          if (sum(game$players$n_cards > 0) == 1) {
            game$status <- "Finished"
            game$cp_nickname <- NULL
          } else {
            game$round_number %<>% add(1)
            game$history <- data.frame(nickname = character(), action_id = numeric())
            game$hands <- draw_cards(game$players)
            # If the checking player was eliminated, figure out the next player
            # Otherwise the current player doesn't change
            if (losing_player == game$cp_nickname) {
              game$cp_nickname <- find_next_active_player(game$players, game$cp_nickname)
            }
          }
        } else {
          # If no one should be kicked out, increment round number, redraw cards and set new current player
          game$round_number %<>% add(1)
          game$history <- data.frame(nickname = character(), action_id = numeric())
          game$hands <- draw_cards(game$players)
          game$cp_nickname <- losing_player
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
  } else if (!game_uuid_valid) {
    res$status <- 400
    list(error = "Invalid game UUID")
  } else if (!player_uuid_valid) {
    res$status <- 400
    list(error = "Invalid player UUID")
  }
}

#* Make game public
#* @serializer unboxedJSON
#* @param admin_uuid The identifier of the admin, passed as verification.
#* @get /v1/games/<game_uuid>/make-public
function(game_uuid, admin_uuid, res) {
  
  game_uuid_valid <- validate_uuid(game_uuid)
  admin_uuid_valid <- validate_uuid(admin_uuid)
  
  if (game_uuid_valid & admin_uuid_valid) {
    
    game <- readRDS(get_path(game_uuid))
    auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]
    
    if (auth_correct & game$public == F) {
      game$public <- T
      
      # Save current game data
      saveRDS(game, get_path(game_uuid))
      
      res$status <- 200
      list(message = "Game made public")
    } else if (!auth_correct) {
      res$status <- 403
      list(error = "Admin UUID does not match")
    } else if (game$public == T) {
      res$status <- 200
      list(message = "Request redundant - game already public")
    } else if (game$status != "Not started") {
      res$status <- 403
      list(message = "Cannot make the change - game already started")
    }
  } else if(!game_uuid_valid) {
    res$status <- 400
    list(error = "Invalid game UUID")
  } else if(!admin_uuid_valid) {
    res$status <- 400
    list(error = "Invalid admin UUID")
  }
}

#* Make game private
#* @serializer unboxedJSON
#* @param admin_uuid The identifier of the admin, passed as verification.
#* @get /v1/games/<game_uuid>/make-private
function(game_uuid, admin_uuid, res) {

  game_uuid_valid <- validate_uuid(game_uuid)
  admin_uuid_valid <- validate_uuid(admin_uuid)
  
  if (game_uuid_valid & admin_uuid_valid) {
    
    game <- readRDS(get_path(game_uuid))
    auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]
    
    if (auth_correct & game$public == T) {
      game$public <- F
      
      # Save current game data
      saveRDS(game, get_path(game_uuid))
      
      res$status <- 200
      list(message = "Game made private")
    } else if (!auth_correct) {
      res$status <- 403
      list(error = "Admin UUID does not match")
    } else if (game$public == F) {
      res$status <- 200
      list(message = "Request redundant - game already private")
    } else if (game$status != "Not started") {
    res$status <- 403
    list(message = "Cannot make the change - game already started")
    }
  } else if(!game_uuid_valid) {
    res$status <- 400
    list(error = "Invalid game UUID")
  } else if(!admin_uuid_valid) {
    res$status <- 400
    list(error = "Invalid admin UUID")
  }
}

#* List public games
#* @serializer unboxedJSON
#* @get /v1/games
function() {
  files <- list.files("../game_data/", full.names = T)
  snapshots <- str_detect(files, "_\\d")
  relevant_files <- files[!snapshots]

  contents <- lapply(relevant_files, readRDS)
  public <- sapply(contents, extract2, var = "public")

  lapply(which(public), function(i) {
    content <- contents[[i]]
    list(
      uuid = relevant_files[i] %>% str_remove("../game_data/") %>% str_remove("\\.RDS"),
      players = as.list(content$players$nickname),
      started = content$status != "Not started"
    )
  })
}
