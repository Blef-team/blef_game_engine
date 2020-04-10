# Game engine service for `Blef`
> The API service to create manage and run games of Blef

![CI](https://github.com/maciej-pomykala/blef_game_engine/workflows/CI/badge.svg?branch=master)

This repository contains the code to run the Blef game engine API service.

At the initial stage it consists of a few basic endpoints, to create, join, start and run a game.

Game states are currently stored in and retrieved from `.rds` files. When necessary, this data will be migrated to an appropriate database, which will run alongside the API, or on separate infrastructure.


## Deployment
The service is deployed to EC2 with CodeDeploy integration.

You can see deployment instructions in the [deployment readme](deployment/README.md)
