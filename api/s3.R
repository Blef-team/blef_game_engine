library("aws.ec2metadata")
library("aws.s3")

get_instance_role <- function() {
  metadata$iam_role("CodeDeploy-EC2-Instance-Profile")
}

list[] <- tryCatch(
  {
    s3_access_key <- metadata$iam_role("CodeDeploy-EC2-Instance-Profile")$AccessKeyId
    s3_secret_access_key <- metadata$iam_role("CodeDeploy-EC2-Instance-Profile")$SecretAccessKey
    keys <- c(s3_access_key, s3_secret_access_key)
    return(keys)
  },
  error = function(e){
    message("Instance metadata not accessible - getting AWS credentials from environment")
    s3_access_key <- Sys.getenv("AWS_ACCESS_KEY_ID")
    s3_secret_access_key <- Sys.getenv("AWS_SECRET_ACCESS_KEY")
    keys <- c(s3_access_key, s3_secret_access_key)
    return(keys)
  }
)
if (s3_access_key == "" | s3_secret_access_key == ""){
  stop("Can't get AWS credentials for S3. Aborting.")
}


readRDS <- function(path) {
  s3readRDS(object=path, bucket="game-data", key=s3_access_key, secret=s3_secret_access_key)
}

saveRDS <- function(game, path) {
  s3readRDS(object=path, bucket="game-data", key=s3_access_key, secret=s3_secret_access_key)
}

game_exists <- function(path) {
  return(object_exists(object=path, bucket="game-data", key=s3_access_key, secret=s3_secret_access_key))
}
