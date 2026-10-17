
# Extensibles

## 1. "Could you do this more simply?" Use `OrderedDict`

This is the most common follow-up. `OrderedDict` is a dict plus a linked list built in, so the whole cache shrinks to a few lines:

```python
from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._data: OrderedDict = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        self._data.move_to_end(key)          # end = most recent
        return self._data[key]

    def put(self, key, value) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        elif len(self._data) == self._capacity:
            self._data.popitem(last=False)   # front = least recent
        self._data[key] = value
```

Note that its direction is the opposite of yours: the end is the most recent. **What to say:** "In production I'd use `OrderedDict`. I built the linked list by hand to show how it works."

## 2. Delete a key, or clear the cache

- **`delete(key)`:** look up the node, then `self._order.remove(node)` and `del self._nodes[key]`. Raise `KeyError` or return False if the key is missing, depending on what the interviewer prefers.
- **`clear()`:** create a fresh dict and a fresh `DoublyLinkedList`.

## 3. `peek` and `contains` that don't change recency

- `peek(key)` returns `self._nodes[key].value` without calling `move_to_front`.
- `__contains__(key)` returns `key in self._nodes`.

**What to say:** "These are read-only views, so they don't count as using the key." That shows you understand that `get` has a side effect.

## 4. Expiry (TTL)

- Add `expires_at: int` to Node, and give the cache a clock that can be injected, the same idea as the timestamp parameter in the parking lot.
- In `put`, set `expires_at = now + ttl`.
- In `get`, if `now >= node.expires_at`, remove the node from both structures and return None. This is **lazy expiry**: expired entries are cleaned up when someone touches them.
- If memory matters, mention a background sweep, or using a heap ordered by expiry time.

## 5. Hit, miss, and eviction stats, or an eviction callback

- Add `self._hits`, `self._misses`, and `self._evictions` counters, increase them in `get` and `put`, and expose a `stats()` method.
- To notify callers when something is evicted, take an optional `on_evict: Callable[[key, value], None]` in the constructor and call it right after removing the LRU node.

## 6. A different eviction policy (LFU, FIFO)

This is the **Strategy pattern** again: the cache keeps its storage and asks a policy object which key to evict.

```python
from abc import ABC, abstractmethod

class EvictionPolicy(ABC):
    @abstractmethod
    def record_access(self, key) -> None: ...
    @abstractmethod
    def record_insert(self, key) -> None: ...
    @abstractmethod
    def remove(self, key) -> None: ...
    @abstractmethod
    def evict_key(self): ...
```

- **LRU:** your linked list.
- **FIFO:** a queue where `record_access` does nothing.
- **LFU:** count uses per key and evict the least used, breaking ties by least recent. An O(1) version needs a dict from count to an ordered set of keys. At the new grad level, describe the idea; you don't need to code it.

## 7. Capacity by size instead of count

- Store a `size` on each node, track `self._total_size`, and evict in a loop: `while self._total_size + new_size > capacity`.
- Edge case: an item bigger than the whole capacity should be rejected, not allowed to evict everything.

## 8. Thread safety

Add `self._lock = threading.Lock()` and wrap the bodies of both `get` and `put` in `with self._lock:`.

The insight to state: **`get` needs the lock too, because it changes the order.** In an LRU cache, every read is a write to the recency list.

## 9. Typed keys and values (generics)

Make the cache `Generic[K, V]` using `TypeVar`, so `LRUCache[str, int]` type-checks correctly. The behavior doesn't change. Mention it as polish, not something to build first.

## 10. Distributed cache

This is beyond the new grad level, but have a one-line answer ready: "I'd split keys across several servers by hashing them, with consistent hashing so adding a server only moves a few keys. Each server runs its own LRU cache."