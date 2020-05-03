cd /var/gameengineservice/api/
export GAME_DATA_PATH=~/game_data/v2/
mkdir -p $GAME_DATA_PATH
touch ~/api_v2.log
echo $(date -u) >> ~/api_v2.log
Rscript --verbose api/run_api.R >> ~/api_v2.log 2>&1 &
