# Class design and relationships

**Class Design:**

```python
class Node:
    - key: Hashable
    - value: Any
    - prev: Node | None
    - next: Node | None

class DoublyLinkedList:
    - _head: Node              (sentinel)
    - _tail: Node              (sentinel)
    + add_to_front(node) -> None
    + remove(node) -> None
    + move_to_front(node) -> None
    + remove_last() -> Node | None
    + __iter__() -> Iterator[Node]

class LRUCache:
    - _capacity: int
    - _nodes: dict[Hashable, Node]
    - _order: DoublyLinkedList
    + LRUCache(capacity)
    + get(key) -> Any | None
    + put(key, value) -> None
    + keys() -> list[Hashable]     (most -> least recent; for debugging)
    + __len__() -> int
```

**Relationships:**

- LRUCache owns one DoublyLinkedList and one dict.
- The dict's values are the same Node objects that live in the list, so both structures point at shared nodes.
- The list owns two sentinel nodes, and every real node sits between them.

**Design decisions worth saying out loud:**

- **Sentinel nodes.** `_head` and `_tail` are dummy nodes that are never removed, so every real node always has a neighbour on each side. That removes all the "is this the first node?" and "is the list empty?" special cases from `add_to_front` and `remove`.
- **A fixed direction.** The front (just after head) is the most recent, and the back (just before tail) is the least recent. Eviction always takes from the back.
- **Two structures, kept in sync.** Every change updates both. Eviction removes the node from the list *and* deletes its key from the dict. Forgetting the dict side is the most common bug in this problem.
- **The list is its own class.** Pointer manipulation stays inside DoublyLinkedList, and LRUCache reads as plain rules: look up, move to front, evict.

**Complexity:** `get` and `put` are O(1) time, and the cache uses O(capacity) space.