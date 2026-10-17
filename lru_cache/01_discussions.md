# Discussions

## Clarifying Questions

1. **What operations does the cache need?**
   Interviewer: `get(key)` and `put(key, value)`. A size check is fine to add.
2. **What types are the keys and values?**
   Interviewer: Any hashable key and any value.
3. **How is the capacity set?**
   Interviewer: Once, when the cache is created. It's the maximum number of entries, and it must be a positive integer.
4. **What should `get` return for a missing key?**
   Interviewer: `None`. Assume `None` is never stored as a value.
5. **Does `get` count as using a key?**
   Interviewer: Yes. A successful `get` makes that key the most recently used.
6. **What happens if `put` is called with a key that already exists?**
   Interviewer: Update its value and make it the most recently used. Nothing is evicted.
7. **What happens if the cache is full and a new key is added?**
   Interviewer: Evict the least recently used key first, then add the new one.
8. **Are there performance requirements?**
   Interviewer: Both `get` and `put` should be O(1).
9. **Can I use `OrderedDict`?**
   Interviewer: Build the underlying structure yourself. You can mention `OrderedDict` afterwards.
10. **What's out of scope?**
    Interviewer: Thread safety, expiry times (TTL), persistence, and distributed caching.

## Requirements

**Requirements** -

1. cache is created with a fixed positive capacity (max number of entries)
    - capacity <= 0 -> reject
2. get(key):
    - key present -> return value, mark key as most recently used
    - key missing -> return None, order unchanged
3. put(key, value):
    - key present -> update value, mark as most recently used, no eviction
    - key new and cache full -> evict the least recently used key, then insert
    - key new and space available -> insert as most recently used
4. get and put both run in O(1)

**Out of scope** -

- thread safety
- expiry / TTL
- persistence
- distributed caching

## Entities

The core problem: you need O(1) lookup **and** O(1) reordering.

- A dict gives O(1) lookup, but it can't tell you which key is the least recent.
- A list keeps order, but moving or removing an item from the middle is O(n).
- A **dict plus a doubly linked list** gives both. The dict maps each key to its node in the list, so you can jump straight to the node. Because each node knows both its neighbours, you can unlink it in O(1).

So the entities are:

- **Node.** One cache entry: a key, a value, and links to the previous and next nodes. It stores its key so that eviction can delete the matching dict entry.
- **DoublyLinkedList.** Keeps the nodes in recency order. The most recent node sits at the front and the least recent at the back.
- **LRUCache.** The orchestrator. It owns the dict and the list and applies the rules.

**Why Node isn't a data class:** it holds data, but equality by value makes no sense here. Two nodes with the same key and value are still two different positions in the list. The links between nodes also form cycles, so a generated `__eq__` could recurse forever. A regular class with `__slots__` is the better fit, which applies the "when to use `@dataclass`" rule from earlier.


```

**Output:**

```
--- Fill the cache (capacity 2) ---
Order (most -> least recent): ['b', 'a']

--- get('a') makes 'a' the most recent ---
get('a'): 1
Order: ['a', 'b']

--- put('c') when full evicts the LRU key ---
Order: ['c', 'a']
get('b'): None

--- Updating an existing key doesn't evict ---
get('a'): 10
Order: ['a', 'c'] | size: 2

--- Capacity 1 ---
get('x'): None | get('y'): 2

--- Invalid capacity ---
Error: Capacity must be positive
```

The key moment is the third block. The `get('a')` call is the reason `b`, not `a`, gets evicted. Without it, `a` would have been the oldest.

I ran this on Python 3.12, and the full file is lru_cache.py.
