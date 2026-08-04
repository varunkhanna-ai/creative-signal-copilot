.PHONY: ingest annotate index eval slice app mcp test

ingest:
	python -m creativesignal.ingest.build_corpus

annotate:
	@echo "annotate: not yet implemented"

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
