library(uuid)
library(magrittr)
library(dplyr)

get_path <- function(game_uuid) paste0("game_data/", game_uuid, ".RDS")


draw_cards <- function(players) {
  possible_cards <- expand.grid(0:5, 0:3)
  all_cards <- possible_cards[sample(1:24, sum(players$n_cards)), ] 
  nicknames <- sapply(1:nrow(players), function(p) rep(players$nickname[p], players$n_cards[p])) %>% unlist()
  cbind(nicknames, all_cards) %>% 
    as.data.frame() %>%
    mutate_all(as.numeric) %>%
    set_colnames(c("player", "value", "colour")) %>%
    arrange(player, -value, -colour)
}

#* Create a new game
#* @serializer unboxedJSON
#* @get /games/create
function() {
  game_uuid <- UUIDgenerate(use.time = F)
  
  empty_game <- list(
    game_uuid = game_uuid,
    admin_nickname = NULL,
    status = "Not started",
    round_number = 0,
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
#* @get /games/<game_uuid>/join
function(game_uuid, nickname, res) {
  
  player_uuid <- UUIDgenerate(use.time = F)
  game <- readRDS(get_path(game_uuid))
  nick_taken <- nickname %in% game$players$nickname
  if (!nick_taken & game$status == "Not started") {
    if (nrow(game$players) == 0) game$admin_nickname <- nickname
    game$players %<>% rbind(data.frame(uuid = as.character(player_uuid), nickname = as.character(nickname), n_cards = 0))
    
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
#* @get /games/<game_uuid>/start
function(game_uuid, admin_uuid, res) {
  
  game <- readRDS(get_path(game_uuid))
  auth_correct <- admin_uuid == game$players$uuid[game$players$nickname == game$admin_nickname]
  
  if (auth_correct & game$status == "Not started" & nrow(game$players) %in% 2:8) {

      # Give each player 1 card
      game$players$n_cards <- rep(1, nrow(game$players))
      
      # Shuffle the order of the players
      game$players <- game$players[order(rnorm(nrow(game$players))), ]
      
      # Deal cards
      game$hands <- draw_cards(game$players)
      
      # Fill in the current player
      game$cp_nickname <- game$players$nickname[1]
      
      # Set game status
      game$status <- "Running"
      
      saveRDS(game, get_path(game_uuid))
      
      res$status <- 202
      list(message = "Game started")
  } else if (!nrow(game$players) %in% 2:8) {
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