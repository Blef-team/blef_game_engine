# Game engine service for `Blef`
> The API service to create manage and run games of Blef

This repository contains the code to run the Blef game engine API service.
At the initial stage it consists of a few basic endpoints, to create, join, start and run a game.
Game states are currently stored in and retrieved from `.rds` files. When necessary, this data will be migrated to an appropriate database, which will run alongside the API, or on separate infrastructure.
There are (going to be) appropriate GitHub actions with EC2 integration, to execute CI/deployment of the service.
