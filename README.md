python -m venv venv

##Linux
source venv/scripts/activate

##Windows
venv\Scripts\activate.bat

pip install -r requirements.txt
python main.py > tmp/report.md