sudo yum install -y amazon-linux-extras
sudo amazon-linux-extras enable R3.4
sudo yum clean metadata
sudo yum install R
export R_LIBS_USER=~/Rlibs
