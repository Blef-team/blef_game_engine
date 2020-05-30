# Validation script to ensure staging deployments are deployed on ports 8010,8011,8012
# and are exclusively major-versioned in the endpoints' URL paths (/v2/, but no /v2.1/)
if grep -q 'export PORT=8010\|export PORT=8011\|export PORT=8012' api/run_api.sh; then
  if grep -Eq '#* @get /v[0-9]+\.[0-9]+' api/endpoints.R; then
    exit 1
  else
    exit 0
  fi
else
  exit 1
fi
