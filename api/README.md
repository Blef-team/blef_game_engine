## Documentation of endpoints

**Create game**
  ----
  Creates an empty game object.

* **URL**

  /v2/games/create

* **Method:**

  `GET`

* **URL Params**

  None

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"game_uuid":"f2fdd601-bc82-438b-a4ee-a871dc35561a"}`

* **Error Response:**

  * **Code:** 429 TOO MANY REQUESTS <br />
  **Content:** `{"message":"Too many games started"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/create
```

**Join game**
  ----
  Allows a player to join a specific game under a specific nickname.

* **URL**

  /v2/games/{game_uuid}/join

* **Method:**

  `GET`

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  **Required:**

  `"nickname"=string`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"player_uuid":"f65e08df-d82a-46b1-979b-550cbc04d56d"}`

* **Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Invalid game UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Game does not exist"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"The game room is full"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"Game already started"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"The game room is full"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Nickname missing - please supply it"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Nickname too long - must be within 32 characters"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Nickname must start with a letter and only contain alphanumeric characters"}`

  OR

  * **Code:** 409 CONFLICT <br />
  **Content:** `{"error":"Nickname already taken"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/join?nickname=coolcat
```

**Start game**
  ----
  Allows the first player who joined the game to start it. After that point, no further players can join the game.

* **URL**

  /v2/games/{game_uuid}/start

* **Method:**

  `GET`

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

   `"admin_uuid"=string`

* **Success Response:**

  * **Code:** 202 Accepted <br />
  **Content:** `{"message":"Game started"}`

* **Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Invalid game UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Game does not exist"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"Game already started"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Admin UUID missing - please supply it"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"error":"Invalid admin UUID"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"Admin UUID does not match"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"At least 2 players needed to start a game"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/start?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**Get game state**
  ----
  Allows a user to query the current (or past) state of the game, restricting information about players hands as appropriate.

* **URL**

  /v2/games/{game_uuid}

* **Method:**

  `GET`

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  **Optional:**

  `"player_uuid"=string`

  `"round"=integer`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"admin_nickname":"funky","public":false,"status":"Running","round_number":12,"max_cards":11,"players":[{"nickname":"chunky","n_cards":8},{"nickname":"funky","n_cards":5}],"hands":[{"Nickname":"chunky","Hand":[{"value":5,"colour":2},{"value":4,"colour":3},{"value":4,"colour":1},{"value":4,"colour":0},{"value":3,"colour":2},{"value":3,"colour":1},{"value":2,"colour":0},{"value":1,"colour":1}]},{"Nickname":"funky","Hand":[{"value":5,"colour":1},{"value":5,"colour":0},{"value":3,"colour":3},{"value":0,"colour":1},{"value":0,"colour":0}]}],"cp_nickname":"funky","history":[{"player":"chunky","action_id":"74"},{"player":"funky","action_id":"88"},{"player":"chunky","action_id":"89"}]}`

* **Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid game UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Game does not exist"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid player UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"The game has not reached this round"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"The round parameter is invalid - must be an integer between 1 and the current round, or -1, or blank"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"The UUID does not match any active player"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/f2fdd601-bc82-438b-a4ee-a871dc35561a
```

**Play**
  ----
  Allows a user to make a move in a game. See below for explanation of the `action_id` parameter.

* **URL**

  /v2/games/{game_uuid}/play

* **Method:**

  `GET`

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  **Required:**

  `"player_uuid"=string`

  `"action_id"=integer`

* **Success Response:**

  * **Code:** 200 OK <br/>

* **Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid game UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Game does not exist"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"This game has not yet started"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"This game has already finished"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Player UUID missing - please supply it"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid player UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"The submitted UUID does not match the UUID of the current player"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Action ID missing - please supply it"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Action ID must be an integer between 0 and 88"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"This action not allowed right now"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/play?player_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53&action_id=88
```

**Make game public**
  ----
  Allows the first player who joined the game to make it public (visible to anyone).

* **URL**

  /v2/games/{game_uuid}/make-public

* **Method:**

  `GET`

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  `"admin_uuid"=string`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"message":"Game made public"}`

  OR

  * **Code:** 200 OK <br />
  **Content:** `{"message":"Request redundant - game already public"}`

* **Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid game UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Game does not exist"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"message":"Cannot make the change - game already started"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Admin UUID missing - please supply it"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid admin UUID"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"message":"Admin UUID does not match"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/make-public?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**Make game private**
  ----
  Allows the first player who joined the game to make it private (visible to only those who know its UUID).

* **URL**

  /v2/games/{game_uuid}/make-private

* **Method:**

  `GET`

* **URL Params**

  **Required:**

  `"game_uuid"=string`

* **Data Params**

  `"admin_uuid"=string`

* **Success Response:**

  * **Code:** 200 OK <br />
  **Content:** `{"message":"Game made private"}`

  OR

  * **Code:** 200 OK <br />
  **Content:** `{"message":"Request redundant - game already private"}`

* **Error Response:**

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid game UUID"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Game does not exist"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"message":"Cannot make the change - game already started"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Admin UUID missing - please supply it"}`

  OR

  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Invalid admin UUID"}`

  OR

  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"message":"Admin UUID does not match"}`

* **Sample Call:**

```
curl <IP & PORT>/v2/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/make-private?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**List public games**
  ----
  Allows users to see all public games.

* **URL**

  /v2/games

* **Method:**

  `GET`

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
curl <IP & PORT>/v2/games
```

**Get the service version**
  ----
  Returns the version of the game engine API.

* **URL**
  
  /v2/version

* **Method:**
  
  `GET`

* **URL Params**
  
  None

* **Success Response:**
  
  * **Code:** 200 OK <br />
  **Content:** `{"version":"2.3.0"}`

* **Sample Call:**
  
```
curl <IP & PORT>/v2/version
```

**Get the number of active games**
  ----
  Returns the number of games which have been modified in the last 30 minutes.

* **URL**
  
  /v2/games/active

* **Method:**
  
  `GET`

* **URL Params**
  
  None

* **Success Response:**
  
  * **Code:** 200 OK <br />
  **Content:** `{"active_games":20}`

* **Sample Call:**
  
```
curl <IP & PORT>/v2/games/active
```

## Action IDs

The table below details what action ID a player should use to make a specific move. Action IDs between 0 and 87 cover bets, while 88 is a check. The way the actions are arranged, a set with a higher action ID is more senior than one with a lower action ID. Therefore, an action with ID `k` can only be followed by an action with an ID higher than `k`.

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
