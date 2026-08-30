"""Offline data pipeline: acquire -> extract -> harmonize -> graph -> emit.

Run once per CellTypist atlas release. Turns raw .h5ad + .pkl resources into
precomputed, query-ready artifacts (PostgreSQL rows + Parquet blobs) that the
online API serves. See docs/CONCEPT.md §5.
"""
