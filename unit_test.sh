python3 -m venv .venv
source .venv/bin/activate
pip install -e .[test]
pytest tests/ -v

