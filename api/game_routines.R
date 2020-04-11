indexation <- read_csv("./indexation.csv")

get_path <- function(game_uuid, r = -1) {
  if (r == -1) return(paste0("../game_data/", game_uuid, ".RDS"))
  if (r >= 0) return(paste0("../game_data/", game_uuid, "_", r, ".RDS"))
}

draw_cards <- function(players) {
  possible_cards <- expand.grid(0:5, 0:3)
  all_cards <- possible_cards[sample(1:24, sum(players$n_cards)), ]
  nicknames <- lapply(1:nrow(players), function(p) rep(players$nickname[p], players$n_cards[p])) %>% unlist()
  cbind(nicknames, all_cards) %>%
    as.data.frame() %>%
    set_colnames(c("player", "value", "colour")) %>%
    mutate(player = as.character(player), value = as.numeric(value), colour = as.numeric(colour)) %>%
    arrange(player, -value, -colour)
}

jsonise_hands <- function(game, nicknames = unique(game$players$nickname)) {
  lapply(nicknames, function(p) {
    list(Nickname = p, Hand = game$hands %>% filter(player == p) %>% select(-player))
  })
}

determine_set_existence <- function(cards, set_id) {

  set_id %<>% as.numeric()
  set_type <- unlist(indexation$hand_type[set_id + 1])
  detail_1 <- as.numeric(unlist(indexation$detail_1[set_id + 1]))
  detail_2 <- as.numeric(unlist(indexation$detail_2[set_id + 1]))

  card_values <- cards[, 2]
  card_colours <- cards[, 3]

  if (set_type == "High card") {
    outcome <- sum(card_values == detail_1) >= 1
    return(outcome)
  } else if (set_type == "Pair") {
    outcome <- sum(card_values == detail_1) >= 2
    return(outcome)
  } else if (set_type == "Two pairs") {
    outcome <- sum(card_values == detail_1) >= 2 & sum(card_values == detail_2) >= 2
    return(outcome)
  } else if (set_type == "Small straight") {
    outcome <- any(card_values == 0) & any(card_values == 1) & any(card_values == 2) & any(card_values == 3) & any(card_values == 4)
    return(outcome)
  } else if (set_type == "Big straight") {
    outcome <- any(card_values == 1) & any(card_values == 2) & any(card_values == 3) & any(card_values == 4) & any(card_values == 5)
    return(outcome)
  } else if (set_type == "Great straight") {
    outcome <- any(card_values == 0) & any(card_values == 1) & any(card_values == 2) & any(card_values == 3) & any(card_values == 4) & any(card_values == 5)
    return(outcome)
  } else if (set_type == "Three of a kind") {
    outcome <- sum(card_values == detail_1) >= 3
    return(outcome)
  } else if (set_type == "Full house") {
    outcome <- sum(card_values == detail_1) >= 3 & sum(card_values == detail_2) >= 2
    return(outcome)
  } else if (set_type == "Colour") {
    outcome <- sum(card_colours == detail_1) >= 5
    return(outcome)
  } else if (set_type == "Four of a kind") {
    outcome <- sum(card_values == detail_1) >= 4
    return(outcome)
  } else if (set_type == "Small flush") {
    relevant_values <- card_values[card_colours == detail_1]
    if (all(is.na(relevant_values))) {
      return(F)
    } else {
      outcome <- any(relevant_values == 0) & any(relevant_values == 1) & any(relevant_values == 2) & any(relevant_values == 3) & any(relevant_values == 4)
      return(outcome)
    }
  } else if (set_type == "Big flush") {
    relevant_values <- card_values[card_colours == detail_1]
    if (all(is.na(relevant_values))) {
      return(F)
    } else {
      outcome <- any(relevant_values == 1) & any(relevant_values == 2) & any(relevant_values == 3) & any(relevant_values == 4) & any(relevant_values == 5)
      return(outcome)
    }
  } else if (set_type == "Great flush") {
    relevant_values <- card_values[card_colours == detail_1]
    if (all(is.na(relevant_values))) {
      return(F)
    } else {
      outcome <- any(relevant_values == 0) & any(relevant_values == 1) & any(relevant_values == 2) & any(relevant_values == 3) & any(relevant_values == 4) & any(relevant_values == 5)
      return(outcome)
    }
  }
}

format_history <- function(history) {
  history %>%
    set_colnames(c("player", "action_id")) %>%
    mutate(player = as.character(player), action_id = as.numeric(as.character(action_id)))
}
