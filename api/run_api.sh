cd /var/gameengineservice/api/v2.2/
export GAME_DATA_PATH=~/game_data/v2.2/
mkdir -p $GAME_DATA_PATH
touch ~/api_v2.2.log
echo $(date -u) >> ~/api_v2.2.log
Rscript --verbose run_api.R >> ~/api_v2.2.log 2>&1 &
