# Game engine service for `Blef`
> The API service to create manage and run games of Blef

![CI](https://github.com/maciej-pomykala/blef_game_engine/workflows/CI/badge.svg?branch=master)

This repository contains the code to run the Blef game engine API service.

At the initial stage it consists of a few basic endpoints, to create, join, start and run a game.

Game states are currently stored in and retrieved from `.rds` files. When necessary, this data will be migrated to an appropriate database, which will run alongside the API, or on separate infrastructure.

## The rules of the game

*Blef* is a Polish* card game inspired by Poker. In the game, each player has a certain number of playing cards between 9 and Ace, each card only known to its owner, and players have to make guesses about other players' cards.

*We could find no traces of the game being known outside Poland.

### Preparation

The game starts with a fixed number of players arranged in a circle and a shuffled deck of 24 cards, with six different values (from 9 to Ace) and four different colours. In the first round, each player is dealt 1 card. A starting player is determined (for example, drawn at random).

### First round

The starting player makes a *bet*, which has to specify a certain *set* of cards. For example, Alice is the starting player and makes a bet saying "Pair of aces". This means that she is claiming that if every player revealed their cards and the cards were pooled together, at least two aces would be found among them. There are 88 sets on which players can bet and they are ranked - some sets are more *senior* than others. 

Suppose that Bob is the next player. Bob has two choices: either he checks Alice, or he bets on a more senior set than a pair of aces. 

* If he checks Alice, then every player reveals their cards. If the set specified by Alice (a pair of aces) can be found among all players' cards, this means that Alice's bet was correct and Bob loses the round. If only one ace or no aces at all could be found among the cards, then Alice loses the round. 
* If he bets on a more senior set, the next player in the circle makes a move (if there is only Alice and Bob, the game comes back to Alice), which, again, can be either a check or a more senior bet. 

In general, players proceed in a circle betting on more and more senior sets until one player checks the previous player.

On one hand, a player should use the knowledge of their own cards to make bets (about everybody's pooled cards) which have a better chance of being correct. For example, if Alice has two aces she knows that if she says "Pair of aces" she will not lose when Bob checks her. On the other hand, Alice doesn't want other players to know her cards. If other players don't know her cards, there is a better chance that they will make an incorrect bet and lose. If they know her cards, they will bet on sets which include Alice's cards and Alice will have trouble making a correct, more senior bet. 

### Next rounds

The second round begins with the player who lost the first round. That player begins the second round with two cards, while others still have one. However, all cards are reshuffled and redrawn. Each round follows the same rules. That means that the starting player bets on a specific set and the subsequent players in the circle bet on more and more senior sets until one player checks the player before them (if a player bets on the most senior set out of all 88, the next player can only check). After each round, the losing player is assigned one more card and makes the first bet in the next round. 

However, there is a maximum number of cards that can be held by a player. This number is determined before the game starts and adjusted to the number of players in the game. If a player has that number of cards and loses a round, instead of getting one more card, they lose the game completely, which means that they do not participate in any subsequent rounds. If a player loses the game, the next round starts from the next player in the circle. The game ends when only one player remains. That player is the winner. 

### The sets

There are 88 sets in the game. They are the following:

| Type of set              | How we specify it                | Number of sets | Composition of the set                                   |
|--------------------------|----------------------------------|----------------|----------------------------------------------------------|
| High card                | *High card, X*                   | 6              | at least 1 X                                             |
| Pair                     | *Pair of Xs*                     | 6              | at least 2 Xs                                            |
| Two pair                 | *Two pair, Xs and Ys*            | 15             | at least 2 Xs and at least 2 Ys                          |
| Small straight           | *Small straight (9-K)*           | 1              | at least one 9, one 10, one J, one Q and one K           |
| Big straight             | *Big straight (10-A)*            | 1              | at least one 10, one J, one Q, one K and one A           |
| Great straight           | *Great straight (9-A)*           | 1              | at least one 9, one 10, one J, one Q, one K and one A    |
| Three of a kind          | *Three of a kind, Xs*            | 6              | at least 3 Xs                                            |
| Full house               | *Full house, Xs over Ys*         | 30             | at least 3 Xs and 2 Ys                                   |
| Flush                    | *Flush, Cs*                      | 4              | at least 5 cards of Cs                                   |
| Four of a kind           | *Four of a kind, Xs*             | 6              | at least 4 Xs                                            |
| Small straight flush     | *Small straight flush (9-K), Cs* | 4              | 9 of Cs, 10 of Cs, J of Cs, Q of Cs and K of Cs          |
| Big straight flush       | *Big straight flush (10-A), Cs*  | 4              | 10 of Cs, J of Cs, Q of Cs, K of Cs and A of Cs          |
| Great straight flush     | *Great straight flush (9-A), Cs* | 4              | 9 of Cs, 10 of Cs, J of Cs, Q of Cs, K of Cs and A of Cs |

where X and Y are one of: 9, 10, J, Q, K, or A (in this order of seniority), and C is one of club, diamond, heart, or spade (in this order of seniority). X must be more senior than than Y. If two pairs or two full houses are compared, the one with the more senior X is more senior overall. If X is equal in both, the one with the more senior Y is more senior overall.

## How we implement the game

The game is implemented in the form of an API service deployed on a remote (AWS) server. The API has endpoints fulfilling the following roles respectively:

* letting a user create a game room
* letting a player join a game room
* letting the first player in a game room start the game
* informing a user about the state of a given game
* letting a player make a move in a game 

### Creating a game

At first, a user has to create a game. This action creates and saves a game object on the API server. As part of this, the relevatn API endpoint provisions a unique UUID for the game and informs the user who created the game of this UUID. 

### Joining a game

Then, the user who created the game informs other users with whom they want to play of the unique UUID of the game. Using that UUID, users can join the game. Each player has a unique nickname (picked by them) by which they will be known to other players and observers and a unique UUID, which is provisioned by the server, relayed to the player and used for authentication when checking own cards or making moves (and therefore intended to be private). The user who creates the game has to join the game in the same way - they are not automatically enrolled at the point the game is created.

### Starting a game

The first user to join the game is made the 'admin'. Users know the nickname of the admin. The admin, using their player UUID for authentication, will start the game, at which point no more players can join it. 

The players are shuffled - i.e. the order of the players in the game (the order in which players make bets) may not be the one in which players join the game. In particular, the game admin might not be the starting player in the first round.

The maximum number of cards is a deterministic function of the number of players who are starting the game. It is equal to 24 (the number of cards available) divided by the number of players and rounded downwards. This ensures that at no point more cards will be needed than are available in the deck. The rule has one exception. With 2 players, the maximum number of cards is 11, not 12. This is because there is a simple strategy to ensure that the first player who reaches 12 cards loses the game. Specifically, in order for them to win the game, it would require the other player to also reach 12 cards and lose a round. However, when the second player reaches 12 cards this player will begin the final round and, knowing that each of the 24 cards is owned by either of the two players, can bet the highest set (Great flush spades) and be guaranteed a win. 

### Querying the game state

Players and observers can query the state of the game, choosing either to get the latest state of the game or the state at the end of a specific round. If a user requests to see the state of the game at the end of a past round, they will be shown all cards possessed by each player in that round. However, when users query the current state of the game, they will not be shown any cards unless they provide a valid player UUID to authenticate themselves as a specific player. In that case, they will be shown the cards of that player. 

Users can query the (current or past, as mentioned above) state of the game at any point. When they do so, they get the following information about the game:

* the nickname of the admin
* whether the game is public
* the status of the game
* the round number (starting at 1 and incremented by 1 every time a round ends)
* the maximum number of cards permitted for a player
* the nicknames of the players who are still participating in the game at the given point, together with the number of cards that each of these players have
* the cards of the players. This field is either empty (for an ongoing round reported to an observer), filled with the cards of one player (for an ongoing round reported to an authenticated player) or filled with the cards of each player (for a finished round)
* the nickname of the player who is now supposed to make a move
* the history of the events in the (current or past) round. An event is a player making a bet (of which there will be at least one but potentially many in a given round), a player checking another player (which will happen once by the end of the round) or a player losing a round (which will be recorded as the last event of that round).

By recording the current state of the game and snapshots of the game at the end of each round, the API will preserve virtually all strategic information about the game (except for details such as the time taken for a user to make a move) and eliminate the need for players or observers to make notes if they would like to learn from the game.

### Making a move

There is an endpoint dedicated to letting the current player make a move. The player provides their UUID (for authentication) and the action they are trying to make (a bet or a check), represented with an action ID.

### Public / private games

A game can be public or private. A public game is visible to any observer. A private game can only be seen by the users who have its UUID. A game starts private and it can be made public by the admin of the game requesting such change from a dedicated API endpoint. The admin can also switch the game back to private using a different endpoint. However, these changes can only be made before the game starts. 

Finally, there is an endpoint which allows a user to see all public games (their UUID, list of players and an indication whether they have started). 

### Full API documentation

In order to play using the API, one should use the full API documentation available in the [API readme](api/README.md).

## Deployment

The service is deployed to EC2 with CodeDeploy integration.

The deployment instructions are in the [deployment readme](deployment/README.md)
