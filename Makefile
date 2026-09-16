.PHONY: install test run run-two-part clean help

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run the full test suite"
	@echo "  make run          - Run the full RQ2 pipeline (original prompt, all findings)"
	@echo "  make run-limit    - Run the pipeline on just 3 findings (quick test)"
	@echo "  make run-two-part - Run the pipeline using the two-part explanation prompt"
	@echo "  make clean        - Remove generated ledger/metrics files and Python caches"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

run:
	python main.py

run-limit:
	python main.py --limit 3

run-two-part:
	python main.py --prompt-style two_part --limit 3

clean:
	rm -f ledger.jsonl quality_metrics.jsonl
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +