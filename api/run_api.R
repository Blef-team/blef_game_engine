if(!require(plumber)) install.packages("plumber")
if(!require(uuid)) install.packages("uuid")
if(!require(magrittr)) install.packages("magrittr")
if(!require(readr)) install.packages("readr")
if(!require(dplyr)) install.packages("dplyr")

plumb("./api/endpoints.R")$run(port = 8000)
