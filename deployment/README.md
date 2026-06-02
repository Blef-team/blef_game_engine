## Deployment

The service API is serverless. 

It consists of HTTP and websocket endpoints implemented in AWS API Gateway with AWS Lambda integrations for each endpoint.

Game states are currently stored in and retrieved from AWS DynamoDB. Game state updates, through DynamoDB Stream, trigger a streaming handler Lambda. On each game state update, all (relevant) websocket connections get a state update and (if relevant) AI agent actions are scheduled.

AI Agents are implemented with Lambda functions. Scheduling their actions is done using an AWS SQS queue.


### Architecture overview
![Blef architecture](https://user-images.githubusercontent.com/10632991/146104548-3e4693ab-4889-43c2-b7a0-e4d47d52fb36.png)
