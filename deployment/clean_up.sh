if [ -z "$DEPLOYMENT_GROUP_NAME" ]
then
      return 0
else
      echo "Cleaning up deployment directory"
      cd /
      rm -r /var/gameengineservice
fi
