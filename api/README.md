## Documentation of endpoints

**Create game**
  ----
  Creates an empty game object with default rules. Optionally, joins the newly created game.

* **URL**

  /games/create

* **Data Params**

  **Optional:**

  `"nickname"=string`

* **URL Params**

  None

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"game_uuid":"f2fdd601-bc82-438b-a4ee-a871dc35561a"}`

* **Sample Call:**

```
curl <HOST>/games/create
```

**Join game**
  ----
  Allows a player to join a specific game under a specific nickname. Joining a game will reset the 'ready' status of all human players.

* **URL**

  /games/{game_uuid}/join

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  **Required:**

  `"nickname"=string`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"player_uuid":"f65e08df-d82a-46b1-979b-550cbc04d56d"}`

* **Sample Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error": "Bad input value in 'nickname': 1\nNickname must start with a letter and only contain alphanumeric characters"}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/join?nickname=coolcat
```

**Set Readiness**
  ----
  Allows a player to set their readiness state. If all players are ready and there are at least 2, the game will start automatically.

* **URL**

  /games/{game_uuid}/set-readiness

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

   **Required:**

   `"player_uuid"=string`
   `"ready"=boolean`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"message":"Readiness updated"}` or `{"message":"All players ready. Game started."}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/set-readiness?player_uuid=f65e08df-d82a-46b1-979b-550cbc04d56d&ready=True
```

**Change Rules**
  ----
  Allows the game admin to change the rules of the game before it starts. Changing rules will reset the readiness of all human players.

* **URL**

  /games/{game_uuid}/change-rules

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

   **Required:**

   `"admin_uuid"=string`
   `"rules"=object`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"message":"Rules updated"}`

* **Rules Object Details:**
    * `time_limit`: integer (0-300 seconds)
    * `deck_size`: integer (24 or 32)
    * `common_cards`: integer (0-12)
    * `jokers`: integer (0-12)
    * `blanks`: integer (0-12)
    * `standard_order`: boolean

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/change-rules?admin_uuid=f65e08df-d82a-46b1-979b-550cbc04d56d&rules={"common_cards":4}
```

**Start game (Legacy)**
  ----
  Allows the first player who joined the game to start it. **This is a legacy endpoint.** The recommended way to start a game is for all players to set their readiness to `true`.

* **URL**

  /games/{game_uuid}/start

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

   `"admin_uuid"=string`

* **Success Response:**

  * **Code:** 202 Accepted <br />
  **Content:** `"Game started"`

* **Sample Error Response:**

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"At least 2 players needed to start a game"}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/start?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**Get game state**
  ----
  Allows a user to query the current (or past) state of the game, restricting information about players hands as appropriate.

* **URL**

  /games/{game_uuid}

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  **Optional:**

  `"player_uuid"=string`
  `"round"=integer`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"admin_nickname": "a", "public": "false", "status": "Running", "round_number": 1, "max_cards": 11, "players": [{"nickname": "b", "n_cards": 1}, {"nickname": "a", "n_cards": 1}], "hands": [{"nickname": "a", "hand": [{"value": 5, "colour": 2}]}], "cp_nickname": "b", "history": []}`

* **Sample Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error": "Bad input value in 'game_uuid': 2e24183f-419f-443b-8ce9-4b29ae8a75a5\nGame does not exist"}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a
```

**Play**
  ----
  Allows a user to make a move in a game. The `action_id` required is determined by the game's rules, specifically the `deck_size`.

* **URL**

  /games/{game_uuid}/play

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  **Required:**

  `"player_uuid"=string`
  `"action_id"=integer`

* **Success Response:**

  * **Code:** 200 OK <br/>

* **Sample Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Action ID must be an integer between 0 and 88"}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/play?player_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53&action_id=88
```

**Make game public**
  ----
  Allows the first player who joined the game to make it public (visible to anyone).

* **URL**

  /games/{game_uuid}/make-public

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  `"admin_uuid"=string`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `"Game made public"`

  OR

  * **Code:** 200 OK <br />
  **Content:** `"Request redundant - game already public"`

* **Sample Error Response:**

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"Cannot make the change - game already started"}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/make-public?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**Make game private**
  ----
  Allows the first player who joined the game to make it private (visible to only those who know its UUID).

* **URL**

  /games/{game_uuid}/make-private

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  `"admin_uuid"=string`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `"Game made private"`

  OR

  * **Code:** 200 OK <br />
  **Content:** `"Request redundant - game already private"`

* **Sample Error Response:**

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"Cannot make the change - game already started"}`

* **Sample Call:**

```
curl <HOST>/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/make-private?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**List public games**
  ----
  Allows users to see all public games.

* **URL**

  /games

* **URL Params**

  NONE

*  **Data Params**

  NONE

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `[{"uuid":"4acb8354-e0d2-4a0c-941d-6f6289bdac63","players":["a"],"started":false},{"uuid":"e10ee626-f05f-4229-bb8d-fee28aecce4b","players":["a","b"],"started":true}]`

* **Error Response:**

  NONE

* **Sample Call:**

```
curl <HOST>/games
```

**Send reaction**
  ----
  Allows users to send reactions to specific games or to the public game lobby.

* **URL**

  /send-reaction

* **URL Params**

  NONE

* **Data Params**

  **Required:**

  `"reaction"=string`

  **Optional:**

  `"player_uuid"=string`

  `"game_uuid"=string`

  `"nickname"=integer`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"message": "Reaction received"}`

* **Sample Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error": "This reaction contains forbidden characters or forbidden content"}`

* **Sample Call:**

```
curl <HOST>/send-reaction?game_uuid=6f3e8308-1170-4b3d-87b9-b62916df330f&nickname=Rando&reaction=🤨
```

## Action IDs

Action IDs are determined dynamically based on the `deck_size` rule.
* **24-Card Deck:** `action_id` ranges from 0 to 87 for bets. **88 is a check.**
* **32-Card Deck:** `action_id` ranges from 0 to 139 for bets. **140 is a check.**

The seniority of bets is calculated programmatically. A higher `action_id` represents betting on a more senior set. However, if the betting order is reversed, players can only bet on less senior sets (or check, if applicable).

| Action ID | Set description                      |
|-----------|--------------------------------------|
| 0         | High card, 9                         |
| 1         | High card, 10                        |
| 2         | High card, J                         |
| 3         | High card, Q                         |
| 4         | High card, K                         |
| 5         | High card, A                         |
| 6         | Pair of 9s                           |
| 7         | Pair of 10s                          |
| 8         | Pair of Js                           |
| 9         | Pair of Qs                           |
| 10        | Pair of Ks                           |
| 11        | Pair of As                           |
| 12        | Two pair, 10s and 9s                 |
| 13        | Two pair, Js and 9s                  |
| 14        | Two pair, Js and 10s                 |
| 15        | Two pair, Qs and 9s                  |
| 16        | Two pair, Qs and 10s                 |
| 17        | Two pair, Qs and Js                  |
| 18        | Two pair, Ks and 9s                  |
| 19        | Two pair, Ks and 10s                 |
| 20        | Two pair, Ks and Js                  |
| 21        | Two pair, Ks and Qs                  |
| 22        | Two pair, As and 9s                  |
| 23        | Two pair, As and 10s                 |
| 24        | Two pair, As and Js                  |
| 25        | Two pair, As and Qs                  |
| 26        | Two pair, As and Ks                  |
| 27        | Small straight (9-K)                 |
| 28        | Big straight (10-A)                  |
| 29        | Great straight (9-A)                 |
| 30        | Three of a kind, 9s                  |
| 31        | Three of a kind, 10s                 |
| 32        | Three of a kind, Js                  |
| 33        | Three of a kind, Qs                  |
| 34        | Three of a kind, Ks                  |
| 35        | Three of a kind, As                  |
| 36        | Full house, 9s over 10s              |
| 37        | Full house, 9s over Js               |
| 38        | Full house, 9s over Qs               |
| 39        | Full house, 9s over Ks               |
| 40        | Full house, 9s over As               |
| 41        | Full house, 10s over 9s              |
| 42        | Full house, 10s over Js              |
| 43        | Full house, 10s over Qs              |
| 44        | Full house, 10s over Ks              |
| 45        | Full house, 10s over As              |
| 46        | Full house, Js over 9s               |
| 47        | Full house, Js over 10s              |
| 48        | Full house, Js over Qs               |
| 49        | Full house, Js over Ks               |
| 50        | Full house, Js over As               |
| 51        | Full house, Qs over 9s               |
| 52        | Full house, Qs over 10s              |
| 53        | Full house, Qs over Js               |
| 54        | Full house, Qs over Ks               |
| 55        | Full house, Qs over As               |
| 56        | Full house, Ks over 9s               |
| 57        | Full house, Ks over 10s              |
| 58        | Full house, Ks over Js               |
| 59        | Full house, Ks over Qs               |
| 60        | Full house, Ks over As               |
| 61        | Full house, As over 9s               |
| 62        | Full house, As over 10s              |
| 63        | Full house, As over Js               |
| 64        | Full house, As over Qs               |
| 65        | Full house, As over Ks               |
| 66        | Flush, clubs                         |
| 67        | Flush, diamonds                      |
| 68        | Flush, hearts                        |
| 69        | Flush, spades                        |
| 70        | Four of a kind, 9s                   |
| 71        | Four of a kind, 10s                  |
| 72        | Four of a kind, Js                   |
| 73        | Four of a kind, Qs                   |
| 74        | Four of a kind, Ks                   |
| 75        | Four of a kind, As                   |
| 76        | Small straight flush (9-K), clubs    |
| 77        | Small straight flush (9-K), diamonds |
| 78        | Small straight flush (9-K), hearts   |
| 79        | Small straight flush (9-K), spades   |
| 80        | Big straight flush (10-A), clubs     |
| 81        | Big straight flush (10-A), diamonds  |
| 82        | Big straight flush (10-A), hearts    |
| 83        | Big straight flush (10-A), spades    |
| 84        | Great straight flush (9-A), clubs    |
| 85        | Great straight flush (9-A), diamonds |
| 86        | Great straight flush (9-A), hearts   |
| 87        | Great straight flush (9-A), spades   |
| 88        | **Check**                            |

For the 32-card deck:

| Action ID | Set description                      |
|-----------|--------------------------------------|
| 0         | High card, 7                         |
| 1         | High card, 8                         |
| 2         | High card, 9                         |
| 3         | High card, 10                        |
| 4         | High card, J                         |
| 5         | High card, Q                         |
| 6         | High card, K                         |
| 7         | High card, A                         |
| 8         | Pair of 7s                           |
| 9         | Pair of 8s                           |
| 10        | Pair of 9s                           |
| 11        | Pair of 10s                          |
| 12        | Pair of Js                           |
| 13        | Pair of Qs                           |
| 14        | Pair of Ks                           |
| 15        | Pair of As                           |
| 16        | Two pair, 8s and 7s                  |
| 17        | Two pair, 9s and 7s                  |
| 18        | Two pair, 9s and 8s                  |
| 19        | Two pair, 10s and 7s                 |
| 20        | Two pair, 10s and 8s                 |
| 21        | Two pair, 10s and 9s                 |
| 22        | Two pair, Js and 7s                  |
| 23        | Two pair, Js and 8s                  |
| 24        | Two pair, Js and 9s                  |
| 25        | Two pair, Js and 10s                 |
| 26        | Two pair, Qs and 7s                  |
| 27        | Two pair, Qs and 8s                  |
| 28        | Two pair, Qs and 9s                  |
| 29        | Two pair, Qs and 10s                 |
| 30        | Two pair, Qs and Js                  |
| 31        | Two pair, Ks and 7s                  |
| 32        | Two pair, Ks and 8s                  |
| 33        | Two pair, Ks and 9s                  |
| 34        | Two pair, Ks and 10s                 |
| 35        | Two pair, Ks and Js                  |
| 36        | Two pair, Ks and Qs                  |
| 37        | Two pair, As and 7s                  |
| 38        | Two pair, As and 8s                  |
| 39        | Two pair, As and 9s                  |
| 40        | Two pair, As and 10s                 |
| 41        | Two pair, As and Js                  |
| 42        | Two pair, As and Qs                  |
| 43        | Two pair, As and Ks                  |
| 44        | Straight (7-J)                       |
| 45        | Straight (8-Q)                       |
| 46        | Straight (9-K)                       |
| 47        | Straight (10-A)                      |
| 48        | Three of a kind, 7s                  |
| 49        | Three of a kind, 8s                  |
| 50        | Three of a kind, 9s                  |
| 51        | Three of a kind, 10s                 |
| 52        | Three of a kind, Js                  |
| 53        | Three of a kind, Qs                  |
| 54        | Three of a kind, Ks                  |
| 55        | Three of a kind, As                  |
| 56        | Full house, 7s over 8s               |
| 57        | Full house, 7s over 9s               |
| 58        | Full house, 7s over 10s              |
| 59        | Full house, 7s over Js               |
| 60        | Full house, 7s over Qs               |
| 61        | Full house, 7s over Ks               |
| 62        | Full house, 7s over As               |
| 63        | Full house, 8s over 7s               |
| 64        | Full house, 8s over 9s               |
| 65        | Full house, 8s over 10s              |
| 66        | Full house, 8s over Js               |
| 67        | Full house, 8s over Qs               |
| 68        | Full house, 8s over Ks               |
| 69        | Full house, 8s over As               |
| 70        | Full house, 9s over 7s               |
| 71        | Full house, 9s over 8s               |
| 72        | Full house, 9s over 10s              |
| 73        | Full house, 9s over Js               |
| 74        | Full house, 9s over Qs               |
| 75        | Full house, 9s over Ks               |
| 76        | Full house, 9s over As               |
| 77        | Full house, 10s over 7s              |
| 78        | Full house, 10s over 8s              |
| 79        | Full house, 10s over 9s              |
| 80        | Full house, 10s over Js              |
| 81        | Full house, 10s over Qs              |
| 82        | Full house, 10s over Ks              |
| 83        | Full house, 10s over As              |
| 84        | Full house, Js over 7s               |
| 85        | Full house, Js over 8s               |
| 86        | Full house, Js over 9s               |
| 87        | Full house, Js over 10s              |
| 88        | Full house, Js over Qs               |
| 89        | Full house, Js over Ks               |
| 90        | Full house, Js over As               |
| 91        | Full house, Qs over 7s               |
| 92        | Full house, Qs over 8s               |
| 93        | Full house, Qs over 9s               |
| 94        | Full house, Qs over 10s              |
| 95        | Full house, Qs over Js               |
| 96        | Full house, Qs over Ks               |
| 97        | Full house, Qs over As               |
| 98        | Full house, Ks over 7s               |
| 99        | Full house, Ks over 8s               |
| 100       | Full house, Ks over 9s               |
| 101       | Full house, Ks over 10s              |
| 102       | Full house, Ks over Js               |
| 103       | Full house, Ks over Qs               |
| 104       | Full house, Ks over As               |
| 105       | Full house, As over 7s               |
| 106       | Full house, As over 8s               |
| 107       | Full house, As over 9s               |
| 108       | Full house, As over 10s              |
| 109       | Full house, As over Js               |
| 110       | Full house, As over Qs               |
| 111       | Full house, As over Ks               |
| 112       | Flush, clubs                         |
| 113       | Flush, diamonds                      |
| 114       | Flush, hearts                        |
| 115       | Flush, spades                        |
| 116       | Four of a kind, 7s                   |
| 117       | Four of a kind, 8s                   |
| 118       | Four of a kind, 9s                   |
| 119       | Four of a kind, 10s                  |
| 120       | Four of a kind, Js                   |
| 121       | Four of a kind, Qs                   |
| 122       | Four of a kind, Ks                   |
| 123       | Four of a kind, As                   |
| 124       | Straight flush (7-J), clubs          |
| 125       | Straight flush (7-J), diamonds       |
| 126       | Straight flush (7-J), hearts         |
| 127       | Straight flush (7-J), spades         |
| 128       | Straight flush (8-Q), clubs          |
| 129       | Straight flush (8-Q), diamonds       |
| 130       | Straight flush (8-Q), hearts         |
| 131       | Straight flush (8-Q), spades         |
| 132       | Straight flush (9-K), clubs          |
| 133       | Straight flush (9-K), diamonds       |
| 134       | Straight flush (9-K), hearts         |
| 135       | Straight flush (9-K), spades         |
| 136       | Straight flush (10-A), clubs         |
| 137       | Straight flush (10-A), diamonds      |
| 138       | Straight flush (10-A), hearts        |
| 139       | Straight flush (10-A), spades        |
| 140       | **Check**                            |
