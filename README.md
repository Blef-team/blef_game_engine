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

* If he checks Alice, then every player reveals their cards. If the set specified by Alice (a pair of aces) can be found among all players' cards, this means that Alice's bet was correct and Bob loses the round. If only one ace or no aces at all could be found among the cards, then Bob loses the round. 
* If he bets on a more senior set, the next player in the circle makes a move (if there is only Alice and Bob, the game comes back to Alice), which, again, can be either a check or a more senior bet. 

In general, players proceed in a circle betting on more and more senior sets until one player checks the previous player.

On one hand, a player should use the knowledge of their own cards to make bets (about everybody's pooled cards) which have a better chance of being correct. For example, if Alice has two aces she knows that if she says "Pair of aces" she will not lose when Bob checks her. On the other hand, Alice doesn't want other players to know her cards. If other players don't know her cards, there is a better chance that they will make an incorrect bet and lose. If they know her cards, they will bet on sets which include Alice's cards and Alice will have trouble making a correct, more senior bet. 

### Next rounds

The second round begins with the player who lost the first round. That player begins the second round with two cards, while others still have one. However, all cards are reshuffled and redrawn. Each round follows the same rules. That means that the starting player bets on a specific set and the subsequent players in the circle bet on more and more senior sets until one player checks the player before them (if a player bets on the most senior set out of all 88, the next player can only check). After each round, the losing player is assigned one more card and makes the first bet in the next round. 

However, there is a maximum number of cards that can be held by a player. This number is determined before the game starts and adjusted to the number of players in the game. If a player has that number of cards and loses a round, instead of getting one more card, they lose the game completely, which means that they do not participate in any subsequent rounds. If a player loses the game, the next round starts from the next player in the circle. The game ends when only one player remains. That player is the winner. 

### The sets

There are 88 sets in the game. They are the following:

| Type of set     | How it's said          | Number of sets | Composition of the set                                   |
|-----------------|------------------------|----------------|----------------------------------------------------------|
| High card       | *High card: X*         | 6              | at least 1 X                                             |
| Pair            | *Pair of Xs*           | 6              | at least 2 Xs                                            |
| Two pairs       | *Two pairs: Xs and Ys* | 15             | at least 2 Xs and at least 2 Ys                          |
| Small straight  | *Small straight*       | 1              | at least one 9, one 10, one J, one Q and one K           |
| Big straight    | *Big straight*         | 1              | at least one 10, one J, one Q, one K and one A           |
| Great straight  | *Great straight*       | 1              | at least one 9, one 10, one J, one Q, one K and one A    |
| Three of a kind | *Three Xs*             | 6              | at least 3 Xs                                            |
| Full house      | *Full house: Xs on Ys* | 30             | at least 3 Xs and 2 Ys                                   |
| Colour          | *Colour: Cs*           | 4              | at least 5 cards of Cs                                   |
| Four of a kind  | *Four Xs*              | 6              | at least 4 Xs                                            |
| Small flush     | *Small flush: Cs*      | 4              | 9 of Cs, 10 of Cs, J of Cs, Q of Cs and K of Cs          |
| Big flush       | *Big flush: Cs*        | 4              | 10 of Cs, J of Cs, Q of Cs, K of Cs and A of Cs          |
| Great flush     | *Great flush: Cs*      | 4              | 9 of Cs, 10 of Cs, J of Cs, Q of Cs, K of Cs and A of Cs |

where X and Y are one of: 9, 10, J, Q, K, or A (in this order of seniority), and C is one of club, diamond, heart, or spade (in this order of seniority). X must be more senior than than Y. If two pairs or two full houses are compared, the one with the more senior X is more senior overall. If X is equal in both, the one with the more senior Y is more senior overall.

## How the API implements the game

The starting player is drawn at random.

## Deployment
The service is deployed to EC2 with CodeDeploy integration.

You can see deployment instructions in the [deployment readme](deployment/README.md)
