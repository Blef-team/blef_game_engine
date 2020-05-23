# Validation script to ensure production deployments are deployed on ports 8000,8001,8002
# and are exclusively major-versioned in the endpoints' URL paths (v2, but no v2.1)
if grep -q 'plumber::plumb("endpoints.R")$run(port = 8000\|plumber::plumb("endpoints.R")$run(port = 8001\|plumber::plumb("endpoints.R")$run(port = 8002' api/run_api.R; then
  if grep -Eq '#* @get /v[0-9]+\.[0-9]+' api/endpoints.R; then
    exit 1
  else
    exit 0
  fi
else
  exit 1
fi
