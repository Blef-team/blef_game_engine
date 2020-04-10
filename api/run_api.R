if(!require(plumber)) install.packages("plumber",repos = "http://cran.us.r-project.org")
if(!require(uuid)) install.packages("uuid",repos = "http://cran.us.r-project.org")
if(!require(magrittr)) install.packages("magrittr",repos = "http://cran.us.r-project.org")
if(!require(readr)) install.packages("readr",repos = "http://cran.us.r-project.org")
if(!require(dplyr)) install.packages("dplyr",repos = "http://cran.us.r-project.org")

plumber::plumb("./api/endpoints.R")$run(port = 8000)
