cd /var/gameengineservice/api/
mkdir -p ~/game_data/v2
touch ~/api.log
echo $(date -u) >> ~/api.log
Rscript --verbose run_api.R >> ~/api.log 2>&1 &
