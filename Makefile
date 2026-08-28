.PHONY: download ingest annotate summaries index eval slice app mcp test

download:
	python -m creativesignal.ingest.download

ingest:
	python -m creativesignal.ingest.build_corpus

annotate:
	python -m creativesignal.annotate.bootstrap

summaries:
	python -m creativesignal.retrieval.cards

index:
	python -m creativesignal.retrieval.index

eval:
	python -m creativesignal.eval.run_eval

slice:
	python -m creativesignal.slice $(if $(BRIEF),--brief "$(BRIEF)",)

app:
	streamlit run app/streamlit_app.py

mcp:
	@echo "mcp: not yet implemented"

test:
	pytest
