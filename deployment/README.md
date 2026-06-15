## Deployment

The service API is serverless. 

It consists of HTTP and websocket endpoints implemented in AWS API Gateway with AWS Lambda integrations for each endpoint.

Game states are currently stored in and retrieved from AWS DynamoDB. Game state updates, through DynamoDB Stream, trigger a streaming handler Lambda. On each game state update, all (relevant) websocket connections get a state update and (if relevant) AI agent actions are scheduled.

AI Agents are implemented with Lambda functions. Scheduling their actions is done using an AWS SQS queue.

### API Gateway invokes Lambda on `$LATEST`

The Lambda functions behind API Gateway are invoked directly on their `$LATEST`
(unpublished) code: each API Gateway integration targets the bare function ARN
(e.g. `…:function:blef-get-game`), with no versions or aliases involved. A deploy is
therefore just an `update-function-code` on `$LATEST` — API Gateway serves the new code
immediately, with no integration changes required.

> **Note:** these functions previously used [Lambda SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html)
> via a published version + `prod` alias to reduce cold starts. That was rolled back
> because, for Python runtimes, SnapStart bills a recurring per-version snapshot charge
> for as long as the version exists. Just keeping the live prod version of each function
> snapshotted came to dozens of dollars **per month** across the fleet — a standing monthly
> cost, not a one-off — and every deploy published another billed version on top of that.
> The functions now run plain on `$LATEST` (`SnapStart.ApplyOn = None`).

**Functions behind API Gateway:**

| API | Functions |
|-----|-----------|
| HTTP API (`blef-game-engine-http-api`) | `blef-create-game`, `blef-get-game`, `blef-join-game`, `blef-play`, `blef-start-game`, `blef-set-readiness`, `blef-change-rules`, `blef-change-team`, `blef-make-public`, `blef-make-private`, `blef-remove-player`, `blef-remove-ais`, `blef-send-reaction`, `blef-list-public-games`, `blef-invite-aiagent` |
| WebSocket API (`blef-watch-game-websocket-api`) | `blef-watch-game-connect`, `blef-watch-game-disconnect` |

All other Lambdas (DynamoDB-stream, SQS, and cron-triggered handlers such as
`blef-watch-game-stream`, `blef-aiagent-*`, `blef-clean-public-games`,
`blef-timeout-player`) are likewise invoked on `$LATEST`.

#### What `deploy.sh` does

For every handler in `api/`, `deploy.sh` packages the code and runs
`update-function-code` against the function's `$LATEST`. Functions are deployed
concurrently through a bounded, throttle-safe worker pool (see the script header).

> Note: the HTTP API stage (`$default`) has auto-deploy enabled. The WebSocket API stage
> (`production`) does **not** auto-deploy — if you ever change a WebSocket integration or
> route, run `aws apigatewayv2 create-deployment --api-id <ws-api-id> --stage-name production`.


### Architecture overview
![Blef architecture](https://user-images.githubusercontent.com/10632991/146104548-3e4693ab-4889-43c2-b7a0-e4d47d52fb36.png)
