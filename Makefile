.PHONY: download ingest annotate index eval slice app mcp test

download:
	python -m creativesignal.ingest.download

ingest:
	python -m creativesignal.ingest.build_corpus

annotate:
	python -m creativesignal.annotate.bootstrap

index:
	@echo "index: not yet implemented"

eval:
	@echo "eval: not yet implemented"

slice:
	@echo "slice: not yet implemented"

app:
	@echo "app: not yet implemented"

mcp:
	@echo "mcp: not yet implemented"

test:
	pytest
