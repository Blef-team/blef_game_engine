# Validation script to ensure develop deployments are NOT deployed on ports 8000,8001,8002
# and are exclusively minor-versioned in the endpoints' URL paths (v2.0, but no v2)
if grep -q 'plumber::plumb("endpoints.R")$run(port = 8000\|plumber::plumb("endpoints.R")$run(port = 8001\|plumber::plumb("endpoints.R")$run(port = 8002' api/run_api.R; then
  exit 1
else
  if grep -Eq '#* @get /v[0-9]+\.[0-9]+' api/endpoints.R; then
    exit 0
  else
    exit 1
  fi
fi
