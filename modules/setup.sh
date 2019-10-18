sudo apt-get upgrade
sudo apt-get update


sudo apt-get install redis python3.7 python3-venv python3.7-dev libopus0 git gcc ffmpeg postgresql
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.6 1
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.7 2

git clone https://github.com/lxmcneill/astutus
cd astutus
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
