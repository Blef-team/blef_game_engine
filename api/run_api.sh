cd /var/gameengineservice/api/
touch codedeploy_started_run_api
mkdir -p game_data
nohup Rscript run_api.R &
touch codedeploy_finished_run_api
