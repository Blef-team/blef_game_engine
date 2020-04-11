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