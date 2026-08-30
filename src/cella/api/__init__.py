"""Online FastAPI backend.

Thin interactive layer over the precomputed artifacts. Runtime work is light:
lookups, cosine similarity, consensus set operations, and subgraph queries.
One router per v1 tool. See docs/CONCEPT.md §4, §7.
"""
