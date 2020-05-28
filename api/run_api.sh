cd /var/gameengineservice/v2/
cd api/
export GAME_DATA_PATH=~/game_data/v2/
mkdir -p $GAME_DATA_PATH
touch ~/api_v2.3.log
echo $(date -u) >> ~/api_v2.3.log
export PORT=8020
if [ "$DEPLOYMENT_GROUP_NAME" == "GameEngineService-Production" ]
then
    export PORT=8001
elif [ "$DEPLOYMENT_GROUP_NAME" == "GameEngineService-Staging" ]
then
    export PORT=8011
fi
lsof -i :$PORT -sTCP:LISTEN |awk 'NR > 1 {print $2}'  |xargs kill -15
Rscript --verbose run_api.R >> ~/api_v2.3.log 2>&1 &
