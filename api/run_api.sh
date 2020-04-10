cd /var/gameengineservice/api/
mkdir -p game_data
Rscript run_api.R > /dev/null 2> /dev/null < /dev/null &
