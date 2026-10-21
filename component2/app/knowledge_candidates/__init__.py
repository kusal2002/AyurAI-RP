"""Candidate Ayurvedic knowledge extracted from source chunks, and its review.

Candidates are machine-extracted statements of what a source text says.
They are not medical facts and are never used by the reasoning pipeline.
Only candidates a named reviewer has approved can be read through
trusted_candidates(), and turning them into graph claims is a separate,
later step (Stage E).
"""
