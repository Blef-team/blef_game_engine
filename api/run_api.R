if(!require(plumber)) install.packages("plumber", repos = "http://cran.us.r-project.org")
if(!require(uuid)) install.packages("uuid", repos = "http://cran.us.r-project.org")
if(!require(magrittr)) install.packages("magrittr", repos = "http://cran.us.r-project.org")
if(!require(readr)) install.packages("readr", repos = "http://cran.us.r-project.org")
if(!require(dplyr)) install.packages("dplyr", repos = "http://cran.us.r-project.org")
if(!require(stringr)) install.packages("stringr", repos = "http://cran.us.r-project.org")

PORT <- strtoi(Sys.getenv("PORT"))
plumber::plumb("endpoints.R")$run(port = PORT, host = "0.0.0.0")
