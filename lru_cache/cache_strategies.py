"""Cache with pluggable eviction policies: LRU, FIFO, LFU (requires Python 3.10+)."""

from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict
from collections.abc import Hashable, Iterator
from typing import Any


# ---------- Strategy interface ----------

class EvictionPolicy(ABC):
    """Tracks keys only. The cache stores the values."""

    @abstractmethod
    def record_insert(self, key: Hashable) -> None:
        """A new key was added to the cache."""

    @abstractmethod
    def record_access(self, key: Hashable) -> None:
        """An existing key was read (get) or updated (put)."""

    @abstractmethod
    def remove(self, key: Hashable) -> None:
        """A key was deleted from the cache."""

    @abstractmethod
    def evict_key(self) -> Hashable:
        """Choose a victim, stop tracking it, and return it."""


# ---------- LRU: your original linked list, moved into a policy ----------

class Node:
    __slots__ = ("key", "prev", "next")

    def __init__(self, key: Hashable) -> None:
        self.key = key
        self.prev: Node | None = None
        self.next: Node | None = None


class DoublyLinkedList:
    """Most recent after head, least recent before tail."""

    def __init__(self) -> None:
        self._head = Node(None)
        self._tail = Node(None)
        self._head.next = self._tail
        self._tail.prev = self._head

    def add_to_front(self, node: Node) -> None:
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def remove(self, node: Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None

    def move_to_front(self, node: Node) -> None:
        self.remove(node)
        self.add_to_front(node)

    def remove_last(self) -> Node | None:
        last = self._tail.prev
        if last is self._head:
            return None
        self.remove(last)
        return last

    def __iter__(self) -> Iterator[Node]:
        node = self._head.next
        while node is not self._tail:
            yield node
            node = node.next


class LRUPolicy(EvictionPolicy):
    """Evict the key that was used longest ago."""

    def __init__(self) -> None:
        self._nodes: dict[Hashable, Node] = {}
        self._order = DoublyLinkedList()

    def record_insert(self, key: Hashable) -> None:
        node = Node(key)
        self._order.add_to_front(node)
        self._nodes[key] = node

    def record_access(self, key: Hashable) -> None:
        self._order.move_to_front(self._nodes[key])

    def remove(self, key: Hashable) -> None:
        self._order.remove(self._nodes.pop(key))

    def evict_key(self) -> Hashable:
        node = self._order.remove_last()
        del self._nodes[node.key]
        return node.key


# ---------- FIFO ----------

class FIFOPolicy(EvictionPolicy):
    """Evict the key that was inserted first. Use doesn't matter."""

    def __init__(self) -> None:
        self._order: OrderedDict[Hashable, None] = OrderedDict()

    def record_insert(self, key: Hashable) -> None:
        self._order[key] = None

    def record_access(self, key: Hashable) -> None:
        pass  # FIFO ignores use; only insertion order matters

    def remove(self, key: Hashable) -> None:
        del self._order[key]

    def evict_key(self) -> Hashable:
        key, _ = self._order.popitem(last=False)
        return key


# ---------- LFU ----------

class LFUPolicy(EvictionPolicy):
    """
    Evict the least frequently used key; break ties by least recently used.

    Core idea:
    - _freq: key -> how many times it has been used
    - _buckets: count -> keys with that count, oldest first
    - _min_freq: the lowest count currently in use, so eviction is O(1)

    Edge cases:
    - Ties at the lowest count -> evict the oldest key in that bucket
    - A bucket becomes empty -> delete it, and move _min_freq up if needed
    - A new key always has count 1, so _min_freq resets to 1 on insert
    """

    def __init__(self) -> None:
        self._freq: dict[Hashable, int] = {}
        self._buckets: defaultdict[int, OrderedDict[Hashable, None]] = defaultdict(OrderedDict)
        self._min_freq = 0

    def record_insert(self, key: Hashable) -> None:
        self._freq[key] = 1
        self._buckets[1][key] = None
        self._min_freq = 1

    def record_access(self, key: Hashable) -> None:
        count = self._freq[key]
        self._remove_from_bucket(key, count)
        if count == self._min_freq and count not in self._buckets:
            self._min_freq = count + 1
        self._freq[key] = count + 1
        self._buckets[count + 1][key] = None

    def remove(self, key: Hashable) -> None:
        count = self._freq.pop(key)
        self._remove_from_bucket(key, count)
        if count == self._min_freq and count not in self._buckets and self._buckets:
            # Rare path (explicit delete only): O(number of distinct counts)
            self._min_freq = min(self._buckets)

    def evict_key(self) -> Hashable:
        bucket = self._buckets[self._min_freq]
        key, _ = bucket.popitem(last=False)  # oldest key among the least used
        if not bucket:
            del self._buckets[self._min_freq]
        del self._freq[key]
        return key

    def _remove_from_bucket(self, key: Hashable, count: int) -> None:
        bucket = self._buckets[count]
        del bucket[key]
        if not bucket:
            del self._buckets[count]


# ---------- Cache (the context) ----------

class Cache:
    def __init__(self, capacity: int, policy: EvictionPolicy) -> None:
        """
        Core logic:
        - Store capacity, values, and the eviction policy

        Edge cases:
        - Capacity zero or negative -> ValueError
        - Each cache needs its OWN policy object; sharing one between
          caches would mix their keys together
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self._capacity = capacity
        self._data: dict[Hashable, Any] = {}
        self._policy = policy

    def get(self, key: Hashable) -> Any | None:
        """
        Core logic:
        - Missing key -> None
        - Present key -> tell the policy it was used, return the value

        Edge cases:
        - Missing key does not touch the policy
        """
        if key not in self._data:
            return None
        self._policy.record_access(key)
        return self._data[key]

    def put(self, key: Hashable, value: Any) -> None:
        """
        Core logic:
        - Existing key: update value, tell the policy it was used
        - New key and full: ask the policy for a victim, delete it
        - New key: store the value, tell the policy it was inserted

        Edge cases:
        - Updating an existing key never evicts
        - The cache and the policy must always track the same keys
        """
        if key in self._data:
            self._data[key] = value
            self._policy.record_access(key)
            return

        if len(self._data) == self._capacity:
            victim = self._policy.evict_key()
            del self._data[victim]

        self._data[key] = value
        self._policy.record_insert(key)

    def delete(self, key: Hashable) -> bool:
        """
        Core logic:
        - Remove the key from the values and from the policy

        Edge cases:
        - Missing key -> return False, nothing changes
        """
        if key not in self._data:
            return False
        del self._data[key]
        self._policy.remove(key)
        return True

    def keys(self) -> list[Hashable]:
        return sorted(self._data)

    def __len__(self) -> int:
        return len(self._data)


# ---------- Dry run ----------

def dry_run() -> None:
    policies = {"LRU": LRUPolicy, "FIFO": FIFOPolicy, "LFU": LFUPolicy}

    print("Same steps for every policy (capacity 3):")
    print("put a, put b, get b, put c, get a, then put d (cache is full)\n")

    for name, policy_class in policies.items():
        cache = Cache(3, policy_class())
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("b")
        cache.put("c", 3)
        cache.get("a")
        before = set(cache.keys())
        cache.put("d", 4)
        evicted = (before - set(cache.keys())).pop()
        print(f"{name:<4} evicts {evicted!r} -> keys left: {cache.keys()}")

    print("\n--- delete works with any policy (LFU shown) ---")
    cache = Cache(2, LFUPolicy())
    cache.put("x", 1)
    cache.put("y", 2)
    print("delete('x'):", cache.delete("x"), "| delete('x') again:", cache.delete("x"))
    cache.put("z", 3)
    print("Keys:", cache.keys(), "| size:", len(cache))


if __name__ == "__main__":
    dry_run()