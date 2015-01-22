sudo vim /etc/apt/sources.list # Enable repositories on lines 33-36 and 59-60
sudo apt-get update
sudo apt-get install git
git clone https://github.com/mithro/chrome-buildbot-sprint.git
cd chrome-buildbot-sprint
sudo apt-get -y install g++-arm-linux-gnueabihf
sudo ./install-build-deps.sh # Accept the mstruetypefonts eula
