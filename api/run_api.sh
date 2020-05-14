cd /var/gameengineservice/api/v3/
export GAME_DATA_PATH=~/game_data/v3/
mkdir -p $GAME_DATA_PATH
touch ~/api_v3.log
echo $(date -u) >> ~/api_v3.log
Rscript --verbose run_api.R >> ~/api_v3.log 2>&1 &
