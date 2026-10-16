# Bolt's Journal

## 2026-09-24 - Memoize character property lookups in unicode_security
**Learning:** Character-by-character `unicodedata` lookups (`unicodedata.category` and `unicodedata.name`) in text normalization and security verification pipeline create significant CPU bottlenecks on large text chunks. Memoizing pure single-character helper functions with `functools.lru_cache(maxsize=1024)` yields ~2.8x execution speedup.
**Action:** Always check for character-by-character C-extension or stdlib lookups in text transformation pipelines and apply bounded `lru_cache`.

## 2026-09-24 - Optimize BM25 score calculations with Counter and precomputed IDF
**Learning:** In retrieval BM25 score calculation, checking term containment in raw list documents (`term in doc`) and calculating `math.log` inside nested document-term loops creates redundant overhead for repeated query terms across steps. Using `collections.Counter` for $O(1)$ term frequency lookups and precomputing term IDF values outside the document loop yields ~1.4x execution speedup.
**Action:** Precompute document token counts using `Counter` and calculate query-term IDFs prior to iterating over document collections in ranking loops.
