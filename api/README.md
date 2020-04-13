## Documentation of endpoints

**Create game**
  ----
  Creates an empty game object.

* **URL**
  
  /v1/games/create

* **Method:**
  
  `GET`

*  **URL Params**
  
  None

* **Success Response:**
  
  * **Code:** 200 OK <br />
  **Content:** `{"game_uuid":"f2fdd601-bc82-438b-a4ee-a871dc35561a"}`

* **Error Response:**
  
  * **Code:** 429 TOO MANY REQUESTS <br />
  **Content:** `{"message":"Too many games started"}`

* **Sample Call:**
  
```
curl <IP & PORT>/v1/games/create
```

**Join game**
  ----
  Allows a player to join a specific game under a specific nickname.

* **URL**
  
  /v1/games/{game_uuid}/join

* **Method:**
  
  `GET`

*  **URL Params**
  
   **Required:**
 
   `"game_uuid"=string`
   
*  **Data Params**

   **Required:**
 
   `"nickname"=string`

* **Success Response:**
  
  * **Code:** 200 OK <br />
  **Content:** `{"player_uuid":"f65e08df-d82a-46b1-979b-550cbc04d56d"}`

* **Error Response:**
  
  * **Code:** 409 CONFLICT <br />
  **Content:** `{"error":"Nickname already taken"}`
  
  OR
  
  * **Code:** 405 METHOD NOT ALLOWED <br />
  **Content:** `{"error":"Game already started"}`

* **Sample Call:**
  
```
curl <IP & PORT>/v1/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/join?nickname=coolcat
```

**Start game**
  ----
  Allows the first player who joined the game to start it. After that point, no further players can join the game.

* **URL**
  
  /v1/games/{game_uuid}/start

* **Method:**
  
  `GET`

*  **URL Params**
  
   **Required:**
 
   `"game_uuid"=string`
   
*  **Data Params**

   None

* **Success Response:**
  
  * **Code:** 202 Accepted <br />
  **Content:** `{"message":"Game started"}`

* **Error Response:**
  
  * **Code:** 405 METHOD NOT ALLOWED <br />
  **Content:** `{"message":"Number of players not between 2 and 8"}`
  
  OR
  
  * **Code:** 405 METHOD NOT ALLOWED <br />
  **Content:** `{"message":"Game already started"}`

  OR
  
  * **Code:** 403 FORBIDDEN <br />
  **Content:** `{"error":"Admin UUID does not match"}`

* **Sample Call:**
  
```
curl <IP & PORT>/v1/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/start?admin_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53
```

**Get game state**
  ----
  Allows a user to query the current (or past) state of the game, restricting information about players hands as appropriate.

* **URL**
  
  /v1/games/{game_uuid}

* **Method:**
  
  `GET`

*  **URL Params**
  
   **Required:**
 
   `"game_uuid"=string`
   
*  **Data Params**

   **Optional:**
 
   `"player_uuid"=string`
   
   `"round"=integer`

* **Success Response:**
  
  * **Code:** 200 OK <br />
  **Content:** `{"admin_nickname":"a","public":true,"status":"Not started","round_number":0,"max_cards":0,"players":[{"nickname":"a","n_cards":0}],"hands":[],"cp_nickname":{},"history":[]}`

* **Error Response:**
  
  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"The UUID does not match any player"}`
  
  OR
  
  * **Code:** 400 BAD REQUEST <br />
  **Content:** `{"message":"Round parameter too high"}`

* **Sample Call:**
  
```
curl <IP & PORT>/v1/games/f2fdd601-bc82-438b-a4ee-a871dc35561a
```

**Play**
  ----
  Allows a user to make a move in a game. See below for explanation of the `action_id` parameter.

* **URL**
  
  /v1/games/{game_uuid}/play

* **Method:**
  
  `GET`

*  **URL Params**
  
   **Required:**
 
   `"game_uuid"=string`
   
*  **Data Params**

   **Required:**
 
   `"player_uuid"=string`
   
   `"action_id"=integer`

* **Success Response:**
  
  * **Code:** 200 OK <br/>

* **Error Response:**
  
  * **Code:** 400 BAD REQUEST <br/>
  **Content:** `{"message":"The submitted UUID does not match the UUID of the current player"}`
  
  OR
  
  * **Code:** 400 BAD REQUEST <br/>
  **Content:** `{"message":"Action with this ID is not allowed"}`

* **Sample Call:**
  
```
curl <IP & PORT>/v1/games/f2fdd601-bc82-438b-a4ee-a871dc35561a/play?player_uuid=a6a53849-44e9-4211-8a21-63c4a9a91d53&action_id=88
```

## Action IDs

The table below matches the action IDs used by the API with the relevant sets the players bet on when entering IDs between 0 and 87. An ID of 88 is a check.

| Action ID | Set description       |
|-----------|-----------------------|
| 0         | High card: 9          |
| 1         | High card: 10         |
| 2         | High card: J          |
| 3         | High card: Q          |
| 4         | High card: K          |
| 5         | High card: A          |
| 6         | Pair of 9s            |
| 7         | Pair of 10s           |
| 8         | Pair of Js            |
| 9         | Pair of Qs            |
| 10        | Pair of Ks            |
| 11        | Pair of As            |
| 12        | Two pairs: 10s and 9s |
| 13        | Two pairs: Js and 9s  |
| 14        | Two pairs: Js and 10s |
| 15        | Two pairs: Qs and 9s  |
| 16        | Two pairs: Qs and 10s |
| 17        | Two pairs: Qs and Js  |
| 18        | Two pairs: Ks and 9s  |
| 19        | Two pairs: Ks and 10s |
| 20        | Two pairs: Ks and Js  |
| 21        | Two pairs: Ks and Qs  |
| 22        | Two pairs: As and 9s  |
| 23        | Two pairs: As and 10s |
| 24        | Two pairs: As and Js  |
| 25        | Two pairs: As and Qs  |
| 26        | Two pairs: As and Ks  |
| 27        | Small straight        |
| 28        | Big straight          |
| 29        | Great straight        |
| 30        | Three 9s              |
| 31        | Three 10s             |
| 32        | Three Js              |
| 33        | Three Qs              |
| 34        | Three Ks              |
| 35        | Three As              |
| 36        | Full house: 9s on 10s |
| 37        | Full house: 9s on Js  |
| 38        | Full house: 9s on Qs  |
| 39        | Full house: 9s on Ks  |
| 40        | Full house: 9s on As  |
| 41        | Full house: 10s on 9s |
| 42        | Full house: 10s on Js |
| 43        | Full house: 10s on Qs |
| 44        | Full house: 10s on Ks |
| 45        | Full house: 10s on As |
| 46        | Full house: Js on 9s  |
| 47        | Full house: Js on 10s |
| 48        | Full house: Js on Qs  |
| 49        | Full house: Js on Ks  |
| 50        | Full house: Js on As  |
| 51        | Full house: Qs on 9s  |
| 52        | Full house: Qs on 10s |
| 53        | Full house: Qs on Js  |
| 54        | Full house: Qs on Ks  |
| 55        | Full house: Qs on As  |
| 56        | Full house: Ks on 9s  |
| 57        | Full house: Ks on 10s |
| 58        | Full house: Ks on Js  |
| 59        | Full house: Ks on Qs  |
| 60        | Full house: Ks on As  |
| 61        | Full house: As on 9s  |
| 62        | Full house: As on 10s |
| 63        | Full house: As on Js  |
| 64        | Full house: As on Qs  |
| 65        | Full house: As on Ks  |
| 66        | Colour: clubs         |
| 67        | Colour: diamonds      |
| 68        | Colour: hearts        |
| 69        | Colour: spades        |
| 70        | Four 9s               |
| 71        | Four 10s              |
| 72        | Four Js               |
| 73        | Four Qs               |
| 74        | Four Ks               |
| 75        | Four As               |
| 76        | Small flush: clubs    |
| 77        | Small flush: diamonds |
| 78        | Small flush: hearts   |
| 79        | Small flush: spades   |
| 80        | Big flush: clubs      |
| 81        | Big flush: diamonds   |
| 82        | Big flush: hearts     |
| 83        | Big flush: spades     |
| 84        | Great flush: clubs    |
| 85        | Great flush: diamonds |
| 86        | Great flush: hearts   |
| 87        | Great flush: spades   |
