"""Short-lived, per-session processed article cache, independent of watchlist order."""
import copy
import time


def process_cached(item, use_ai, model, cache, processor, *, now=None, ttl=900):
    now = time.time() if now is None else now
    for key in list(cache):
        if now - cache[key][0] >= ttl:
            del cache[key]
    key = (item.get('url') or item['title'], item['title'], item.get('summary', ''), use_ai, model, 'concise-summary-v4')
    stored = cache.get(key)
    if stored is not None and len(stored[1].get('article_text', '').split()) < 80:
        cache.pop(key)
        stored = None
    if stored is None:
        result = processor(copy.deepcopy(item), use_ai, model)
        if len(result.get('article_text', '').split()) < 80:
            return result
        cache[key] = (now, {k: copy.deepcopy(result.get(k)) for k in ('article_text', 'ai_detail', 'bond_info')})
    # Watchlist membership is recalculated each scan, never copied from the cache.
    return {**item, **copy.deepcopy(cache[key][1])}
