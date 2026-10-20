"""Source-document ingestion for the Ayurvedic knowledge corpus.

This package turns local source files (PDF, DOCX, EPUB, TXT, Markdown)
into extracted passages with explicit source locations, extraction
status and provenance. Extraction only reproduces what is in a file; it
does not establish that any statement in the file is correct. Curated
evidence is still loaded through app.retrieval.ingestion.
"""
