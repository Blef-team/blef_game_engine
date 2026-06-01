#!/bin/bash

# Run this script from the project root directory (containing api/ and deployment/)
#
# Parallel, throttle-safe Lambda deployment.
# ------------------------------------------
# Each handler in api/ is packaged and deployed independently. The slow part is
# the alias-managed functions (see ALIAS_MANAGED): they publish a new SnapStart
# version and then wait for the snapshot to become Active, which takes a while.
# Doing that for ~17 functions sequentially is painfully slow, so we run the
# functions concurrently through a bounded worker pool.
#
# "Safely" means we do NOT hammer the Lambda control plane (shared ~req/s
# account bucket). Two mechanisms keep us under the limit:
#   1. A capped worker pool (CONCURRENCY, default 8) so only N functions are
#      ever in flight at once.
#   2. AWS_RETRY_MODE=adaptive + AWS_MAX_ATTEMPTS, which does CLIENT-SIDE rate
#      limiting and exponential backoff on TooManyRequestsException. This is the
#      key piece: even with N workers active, adaptive mode throttles the client
#      so we back off instead of getting blocked.
# Because alias-managed workers spend most of their time idle-waiting on the
# snapshot, the real call rate stays well below the account limit.
#
# Each function is fully isolated (its own work dir + zip), so there are no races
# between parallel workers. Results are collected per function; a summary is
# printed at the end and only the FAILED functions need to be re-run.
#
# Usage:
#   ./deployment/deploy.sh                 # deploy all handlers in api/
#   ./deployment/deploy.sh api/play.py ... # deploy only the given handler files
#                                          # (used to re-run just the failures)
#   CONCURRENCY=4 ./deployment/deploy.sh   # override pool size

# --- Configuration ---
API_DIR="api"
SHARED_DIR="shared"
# Max functions deployed concurrently. The shared Lambda control-plane bucket is
# the constraint; 8 is a safe balance for ~22 functions. Override via env.
CONCURRENCY="${CONCURRENCY:-8}"

# Client-side rate limiting + retries. adaptive mode measures throttling and
# slows the client automatically, so the pool can't overrun the account limit.
export AWS_RETRY_MODE="adaptive"
export AWS_MAX_ATTEMPTS="${AWS_MAX_ATTEMPTS:-10}"
export AWS_PAGER=""

# Functions fronted by API Gateway via the "prod" alias of a published,
# SnapStart-optimized version (see deployment/README.md). For these, updating
# $LATEST is NOT enough: API Gateway invokes the immutable "prod" alias, so after
# pushing code we must publish a new version (which builds a fresh SnapStart
# snapshot) and move the "prod" alias to it. Listed by full AWS function name.
ALIAS_MANAGED=" \
blef-create-game blef-get-game blef-join-game blef-play blef-start-game \
blef-set-readiness blef-change-rules blef-change-team blef-make-public blef-make-private \
blef-remove-player blef-remove-ais blef-send-reaction blef-list-public-games blef-invite-aiagent \
blef-watch-game-connect blef-watch-game-disconnect "
# The alias API Gateway integrations point at.
PROD_ALIAS="prod"

# True if the given full function name (blef-...) is fronted by the prod alias.
is_alias_managed() {
  case "$ALIAS_MANAGED" in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

# Package + deploy a single handler. All output goes to the caller-provided log
# (via deploy_one). Returns non-zero on any failure so the function can be
# re-run individually. Runs in its own work dir, so parallel calls never collide.
_deploy_impl() {
  local f="$1" filename="$2" fn="$3"
  local work="$RESULTS_DIR/work-$filename"
  local zip="$RESULTS_DIR/$filename.zip"
  local rc=0 new_version

  echo "=== $fn ($filename) ==="

  rm -rf "$work"; mkdir -p "$work" || { echo "mkdir work dir failed"; return 1; }

  # Stage: handler renamed to lambda_function.py + the shared/ tree.
  cp "$f" "$work/lambda_function.py" || { echo "copy handler failed"; rm -rf "$work"; return 1; }
  if [ -d "$API_DIR/$SHARED_DIR" ]; then
    cp -r "$API_DIR/$SHARED_DIR" "$work/" || { echo "copy shared failed"; rm -rf "$work"; return 1; }
  else
    echo "Warning: shared directory '$API_DIR/$SHARED_DIR' not found."
  fi

  # Zip the contents of the work dir (zip lands outside it to avoid self-inclusion).
  if ! ( cd "$work" && zip -qr "$zip" . -x ".DS_Store" "*__pycache__*" ); then
    echo "Error: failed to create zip for $filename"; rm -rf "$work" "$zip"; return 1
  fi

  # --- Update code on $LATEST ---
  echo "Updating code on \$LATEST ..."
  if ! aws lambda update-function-code --function-name "$fn" --zip-file "fileb://$zip" >/dev/null; then
    echo "❌ update-function-code failed for $fn"; rm -rf "$work" "$zip"; return 1
  fi
  echo "✅ code updated on \$LATEST."

  # --- Alias-managed: publish a new SnapStart version and move the prod alias ---
  if is_alias_managed "$fn"; then
    echo "  ↳ API-Gateway-fronted: publishing new SnapStart version..."
    # Code update must finish before we can publish a version off it.
    if ! aws lambda wait function-updated-v2 --function-name "$fn"; then
      echo "  ↳ ❌ wait function-updated failed; alias left unchanged."; rm -rf "$work" "$zip"; return 1
    fi
    new_version=$(aws lambda publish-version --function-name "$fn" --query 'Version' --output text)
    if [ -n "$new_version" ] && [ "$new_version" != "None" ]; then
      echo "  ↳ published version $new_version; waiting for SnapStart snapshot to become Active..."
      if aws lambda wait published-version-active --function-name "$fn" --qualifier "$new_version"; then
        if aws lambda update-alias --function-name "$fn" --name "$PROD_ALIAS" --function-version "$new_version" >/dev/null; then
          echo "  ↳ ✅ '$PROD_ALIAS' alias now points to version $new_version (API Gateway uses it automatically)."
        else
          echo "  ↳ ❌ Failed to move '$PROD_ALIAS' alias. New code is live on \$LATEST but NOT yet served by API Gateway."; rc=1
        fi
      else
        echo "  ↳ ❌ SnapStart snapshot did not become Active; '$PROD_ALIAS' alias left unchanged."; rc=1
      fi
    else
      echo "  ↳ ❌ Failed to publish a new version; '$PROD_ALIAS' alias left unchanged."; rc=1
    fi
  fi

  rm -rf "$work" "$zip"
  return $rc
}

# Worker entry point invoked once per handler by xargs. Captures the full log to
# a per-function file and records OK/FAIL status, then prints a one-line result.
# Always returns 0 so a single failure never aborts the xargs pool.
deploy_one() {
  local f="$1"
  local filename fn logf rc
  filename=$(basename "$f" .py)
  fn="blef-${filename//_/-}"
  logf="$RESULTS_DIR/$filename.log"

  _deploy_impl "$f" "$filename" "$fn" >"$logf" 2>&1
  rc=$?

  if [ "$rc" -eq 0 ]; then
    printf 'OK\t%s\t%s\n' "$fn" "$f" >"$RESULTS_DIR/$filename.status"
    echo "✅ [$fn] done"
  else
    printf 'FAIL\t%s\t%s\n' "$fn" "$f" >"$RESULTS_DIR/$filename.status"
    echo "❌ [$fn] FAILED (rc=$rc) — see $logf"
  fi
  return 0
}

# Make worker logic + config available to the bash -c children spawned by xargs.
export API_DIR SHARED_DIR PROD_ALIAS ALIAS_MANAGED
export -f is_alias_managed _deploy_impl deploy_one

# --- Main ---
if [ ! -d "$API_DIR" ]; then
  echo "Error: API directory '$API_DIR' not found. Run script from project root."
  exit 1
fi

# Per-run scratch dir holds work dirs, zips, logs and status files.
RESULTS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/blef-deploy-run.XXXXXX") || {
  echo "Error: could not create temp results directory."; exit 1
}
export RESULTS_DIR

# Collect the handlers to deploy: explicit args (e.g. re-running failures) or all.
if [ "$#" -gt 0 ]; then
  candidates=("$@")
else
  candidates=("$API_DIR"/*.py)
fi

# Order non-alias (fast) functions first and alias-managed (slow, publishes +
# flips the prod alias) last, so the alias flips cluster near the end rather than
# interleaving with the noisy fast updates.
fast=(); slow=()
for f in "${candidates[@]}"; do
  [ -f "$f" ] || { echo "Warning: '$f' not found, skipping."; continue; }
  name=$(basename "$f" .py)
  if is_alias_managed "blef-${name//_/-}"; then slow+=("$f"); else fast+=("$f"); fi
done
files=("${fast[@]}" "${slow[@]}")

total="${#files[@]}"
if [ "$total" -eq 0 ]; then
  echo "No handler files to deploy."; rm -rf "$RESULTS_DIR"; exit 0
fi

echo "Deploying $total function(s) with concurrency $CONCURRENCY"
echo "(AWS_RETRY_MODE=$AWS_RETRY_MODE, AWS_MAX_ATTEMPTS=$AWS_MAX_ATTEMPTS)"
echo "Logs: $RESULTS_DIR"
echo "============================="

# Bounded parallel fan-out. -P caps in-flight workers; adaptive retry caps rate.
printf '%s\n' "${files[@]}" | xargs -P "$CONCURRENCY" -I {} bash -c 'deploy_one "$1"' _ {}

# --- Summary ---
echo "============================="
succeeded=0; failed=0; failed_files=""
for sf in "$RESULTS_DIR"/*.status; do
  [ -f "$sf" ] || continue
  IFS=$'\t' read -r status fn fpath < "$sf"
  if [ "$status" = "OK" ]; then
    succeeded=$((succeeded + 1))
  else
    failed=$((failed + 1))
    failed_files="$failed_files $fpath"
  fi
done

echo "Done: $succeeded succeeded, $failed failed (of $total)."
if [ "$failed" -gt 0 ]; then
  echo "Failed functions left to fix. Re-run ONLY the failures with:"
  echo "  CONCURRENCY=$CONCURRENCY ./deployment/deploy.sh$failed_files"
  echo "Per-function logs kept in: $RESULTS_DIR"
  exit 1
fi

# All good: clean up scratch dir.
rm -rf "$RESULTS_DIR"
echo "Deployment process finished."
