cd /var/gameengineservice/v2/
cd api/
export GAME_DATA_PATH=~/game_data/v2/
mkdir -p $GAME_DATA_PATH
touch ~/api_v2.3.log
echo $(date -u) >> ~/api_v2.3.log
export PORT=8020
if [ "$DEPLOYMENT_GROUP_NAME" == "GameEngineService-Production" ]
then
    PORT=8001 Rscript --verbose run_api.R >> ~/api_v2.3.log 2>&1 &
elif [ "$DEPLOYMENT_GROUP_NAME" == "GameEngineService-Staging" ]
then
    PORT=8011 Rscript --verbose run_api.R >> ~/api_v2.3.log 2>&1 &
fi
lsof -i :$PORT -sTCP:LISTEN |awk 'NR > 1 {print $2}'  |xargs kill -15
Rscript --verbose run_api.R >> ~/api_v2.3.log 2>&1 &
