# Bolt's Journal

## 2026-09-24 - Memoize character property lookups in unicode_security
**Learning:** Character-by-character `unicodedata` lookups (`unicodedata.category` and `unicodedata.name`) in text normalization and security verification pipeline create significant CPU bottlenecks on large text chunks. Memoizing pure single-character helper functions with `functools.lru_cache(maxsize=1024)` yields ~2.8x execution speedup.
**Action:** Always check for character-by-character C-extension or stdlib lookups in text transformation pipelines and apply bounded `lru_cache`.

## 2026-10-15 - Optimize BM25 lexical ranking and regex tokenization in retrieval
**Learning:** `tokenize` used regex `finditer` with `group(0)` without memoization, generating Match object overhead for every step across retrieval passes. Replacing `finditer` with `findall`, memoizing `tokenize` with `@lru_cache(maxsize=4096)`, pre-computing Inverse Document Frequency (IDF) over term sets, and hoisting loop invariants (`doc_b`, `k1_plus_1`) reduced `bm25_scores` execution time from ~12.1 ms to ~3.4 ms per call (~3.5x speedup).
**Action:** In text search / ranking pipelines, combine `findall` with `lru_cache` for pure tokenizers and hoist document-level math invariants outside token iteration loops.
