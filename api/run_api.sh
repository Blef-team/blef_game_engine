export GAME_DATA_PATH=~/game_data/v2/
mkdir -p $GAME_DATA_PATH
touch ~/api.log
echo $(date -u) >> ~/api.log
Rscript --verbose api/run_api.R >> ~/api.log 2>&1 &
