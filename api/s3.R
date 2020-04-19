library("aws.ec2metadata")
library("aws.s3")

s3_access_key = metadata$iam_role("CodeDeploy-EC2-Instance-Profile")$AccessKeyId
s3_secret_access_key = metadata$iam_role("CodeDeploy-EC2-Instance-Profile")$SecretAccessKey

readRDS <- function(path) {
  s3readRDS(object=path, bucket="game-data", key=s3_access_key, secret=s3_secret_access_key)
}

saveRDS <- function(game, path) {
  s3readRDS(object=path, bucket="game-data", key=s3_access_key, secret=s3_secret_access_key)
}

game_exists <- function(path) {
  return(object_exists(object=path, bucket="game-data", key=s3_access_key, secret=s3_secret_access_key))
}
