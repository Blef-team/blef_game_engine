## Deployment

The service API is serverless. 

It consists of HTTP and websocket endpoints implemented in AWS API Gateway with AWS Lambda integrations for each endpoint.

Game states are currently stored in and retrieved from AWS DynamoDB. Game state updates, through DynamoDB Stream, trigger a streaming handler Lambda. On each game state update, all (relevant) websocket connections get a state update and (if relevant) AI agent actions are scheduled.

AI Agents are implemented with Lambda functions. Scheduling their actions is done using an AWS SQS queue.

### API Gateway is wired to Lambda via the `prod` alias of a published, SnapStart version

> **Important for anyone deploying or editing these functions.**

The Lambda functions that sit directly behind API Gateway are **not** invoked on their
`$LATEST` (unpublished) code. To reduce cold starts, each of these functions has
[Lambda SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html) enabled
(`SnapStart.ApplyOn = PublishedVersions`). SnapStart only applies to **published, numbered
versions** — never `$LATEST` — so for each function we:

1. Enable SnapStart on the function.
2. **Publish a version**, which builds the SnapStart snapshot for that immutable code.
3. Point a **`prod` alias** at that version.
4. Configure the **API Gateway integration to invoke the `prod` alias ARN**
   (e.g. `…:function:blef-get-game:prod`), not the bare function ARN.

Because API Gateway targets the stable `prod` alias, deploys never need to re-touch the
integration: publishing a new version and moving the alias is enough, and API Gateway
serves the new SnapStart-optimized version automatically.

**Functions wired this way** (API Gateway integration → `:prod` alias → published version):

| API | Functions |
|-----|-----------|
| HTTP API (`blef-game-engine-http-api`) | `blef-create-game`, `blef-get-game`, `blef-join-game`, `blef-play`, `blef-start-game`, `blef-set-readiness`, `blef-change-rules`, `blef-change-team`, `blef-make-public`, `blef-make-private`, `blef-remove-player`, `blef-remove-ais`, `blef-send-reaction`, `blef-list-public-games`, `blef-invite-aiagent` |
| WebSocket API (`blef-watch-game-websocket-api`) | `blef-watch-game-connect`, `blef-watch-game-disconnect` |

All other Lambdas (DynamoDB-stream, SQS, and cron-triggered handlers such as
`blef-watch-game-stream`, `blef-aiagent-*`, `blef-clean-public-games`,
`blef-timeout-player`) are invoked on `$LATEST` and are **not** alias-managed.

#### What `deploy.sh` does for these functions

`deploy.sh` keeps a list of the alias-managed function names (`ALIAS_MANAGED`). For those,
after `update-function-code` it additionally:

- waits for the code update to settle,
- **publishes a new version** (a fresh SnapStart snapshot is built — this can take a
  minute or two while the version is in `Pending`),
- waits for that version to become `Active`,
- **moves the `prod` alias** to the new version.

Functions not in `ALIAS_MANAGED` continue to deploy straight to `$LATEST` as before.

#### Rolling back

Because every deploy leaves the previous numbered version intact, a rollback is just
re-pointing the alias — no code redeploy required:

```bash
aws lambda update-alias --function-name blef-get-game --name prod --function-version <previous_version>
```

> Note: the HTTP API stage (`$default`) has auto-deploy enabled, so integration changes
> take effect immediately. The WebSocket API stage (`production`) does **not** auto-deploy
> — if you ever change a WebSocket integration or route, run
> `aws apigatewayv2 create-deployment --api-id <ws-api-id> --stage-name production`.


### Architecture overview
![Blef architecture](https://user-images.githubusercontent.com/10632991/146104548-3e4693ab-4889-43c2-b7a0-e4d47d52fb36.png)
