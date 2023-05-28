from python:3.7.3

workdir /app

run mkdir logs

copy requirements.txt requirements.txt

run pip3 install -r requirements.txt

copy . .

cmd ["python3", "run.py"]