cd /var/gameengineservice/v2/
cd api/
export GAME_DATA_PATH=~/game_data/v2/
mkdir -p $GAME_DATA_PATH
touch ~/api_v2.2.log
echo $(date -u) >> ~/api_v2.2.log
if [ "$DEPLOYMENT_GROUP_NAME" == "GameEngineService-Production" ]
then
    PORT=8001 Rscript --verbose run_api.R >> ~/api_v2.2.log 2>&1 &
elif [ "$DEPLOYMENT_GROUP_NAME" == "GameEngineService-Staging" ]
then
    PORT=8011 Rscript --verbose run_api.R >> ~/api_v2.2.log 2>&1 &
else
    PORT=8020 Rscript --verbose run_api.R >> ~/api_v2.2.log 2>&1 &
fi
