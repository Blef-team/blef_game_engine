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