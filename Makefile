.PHONY: install test coverage demo agreement run run-limit run-two-part drift clean help

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run the full test suite"
	@echo "  make coverage     - Run the tests with a coverage report"
	@echo "  make demo         - Run the whole pipeline on synthetic data (no Ollama needed)"
	@echo "  make agreement    - Disagreements and Fleiss' kappa for ledger.jsonl"
	@echo "  make run          - Run the full RQ2 pipeline (original prompt, all findings)"
	@echo "  make run-limit    - Run the pipeline on just 3 findings (quick test)"
	@echo "  make run-two-part - Run the pipeline using the two-part explanation prompt"
	@echo "  make drift KPI=<file> - Check a new month's export for clustering drift"
	@echo "  make clean        - Remove generated ledger/metrics files and Python caches"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

coverage:
	pytest tests/ --cov=hitl --cov-report=term-missing

demo:
	python demo/run_demo.py

agreement:
	python scripts/review_agreement.py --ledger ledger.jsonl

run:
	python main.py

run-limit:
	python main.py --limit 3

run-two-part:
	python main.py --prompt-style two_part --limit 3

drift:
	python scripts/check_parameter_drift.py --kpi-file "$(KPI)"

clean:
	rm -f ledger.jsonl quality_metrics.jsonl demo/demo_ledger.jsonl demo/demo_kpi_export.xlsx
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +