# Bolt's Journal

## 2026-09-24 - Memoize character property lookups in unicode_security
**Learning:** Character-by-character `unicodedata` lookups (`unicodedata.category` and `unicodedata.name`) in text normalization and security verification pipeline create significant CPU bottlenecks on large text chunks. Memoizing pure single-character helper functions with `functools.lru_cache(maxsize=1024)` yields ~2.8x execution speedup.
**Action:** Always check for character-by-character C-extension or stdlib lookups in text transformation pipelines and apply bounded `lru_cache`.

## 2026-10-15 - Casefolding prior to regex findall and precalculating query term factors in BM25 search
**Learning:** `re.finditer` tokenization calling `.casefold()` on match objects in Python loops adds significant overhead compared to pre-casefolding text and calling `re.findall`. Furthermore, calculating IDFs inside document iteration loops in BM25 algorithms repeats constant calculations. Precomputing IDFs, querying term counts, set-based term presence, and iterating only over query terms present in documents yields ~1.65x overall speedup.
**Action:** In text search ranking routines, pre-casefold string input before regex extraction and precalculate query-level terms/IDFs outside document iterations.
