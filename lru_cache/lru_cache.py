from collections.abc import Hashable, Iterator
from typing import Any


# ---------- Node ----------

class Node:
    """One cache entry, linked to its neighbours in recency order."""

    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: Hashable, value: Any) -> None:
        self.key = key          # stored so eviction can delete the dict entry
        self.value = value
        self.prev: Node | None = None
        self.next: Node | None = None


# ---------- Doubly linked list ----------

class DoublyLinkedList:
    """Nodes in recency order: most recent after head, least recent before tail."""

    def __init__(self) -> None:
        # Sentinel nodes: they hold no data and are never removed, so every
        # real node always has a prev and a next. No None checks needed.
        self._head = Node(None, None)
        self._tail = Node(None, None)
        self._head.next = self._tail
        self._tail.prev = self._head

    def add_to_front(self, node: Node) -> None:
        """
        Core logic:
        - Insert the node right after the head sentinel (most recent position)

        Edge cases:
        - Empty list: the sentinels mean there's no special case
        """
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def remove(self, node: Node) -> None:
        """
        Core logic:
        - Link the node's neighbours to each other
        - Clear the node's own links

        Edge cases:
        - Node is the first or last real node: the sentinels mean its
          neighbours always exist
        """
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = None
        node.next = None

    def move_to_front(self, node: Node) -> None:
        """
        Core logic:
        - Remove the node from its current position
        - Add it back at the front

        Edge cases:
        - Node is already at the front: still correct, just a no-op in effect
        """
        self.remove(node)
        self.add_to_front(node)

    def remove_last(self) -> Node | None:
        """
        Core logic:
        - Remove and return the node just before the tail sentinel
          (the least recently used one)

        Edge cases:
        - Empty list -> (only sentinel nodes exist) return None
        """
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


# ---------- Cache ----------

class LRUCache:
    def __init__(self, capacity: int) -> None:
        """
        Core logic:
        - Store the capacity
        - Create the key -> node dict and the recency list

        Edge cases:
        - Capacity zero or negative -> ValueError
        """
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self._capacity = capacity
        self._nodes: dict[Hashable, Node] = {}
        self._order = DoublyLinkedList()

    def get(self, key: Hashable) -> Any | None:
        """
        Core logic:
        - Look up the node by key in the dict
        - Move it to the front, since it was just used
        - Return its value

        Edge cases:
        - Key not present -> return None, order unchanged
        - Unhashable key (e.g. a list) -> TypeError raised by the dict
        """
        node = self._nodes.get(key)
        if node is None:
            return None
        self._order.move_to_front(node)
        return node.value

    def put(self, key: Hashable, value: Any) -> None:
        """
        Core logic:
        - Key exists: update its value and move it to the front
        - New key and cache full: evict the least recently used entry
          (remove it from the list AND the dict)
        - New key: create a node, add it to the front, store it in the dict

        Edge cases:
        - Updating an existing key when full must not evict anything
        - Capacity 1: every new key evicts the previous one
        - Eviction needs the evicted node's key to delete it from the dict,
          which is why Node stores its key
        """
        node = self._nodes.get(key)
        if node is not None:
            node.value = value
            self._order.move_to_front(node)
            return

        if len(self._nodes) == self._capacity:
            lru = self._order.remove_last()
            del self._nodes[lru.key]

        new_node = Node(key, value)
        self._order.add_to_front(new_node)
        self._nodes[key] = new_node

    def keys(self) -> list[Hashable]:
        """Keys from most to least recently used (for debugging and the dry run)."""
        return [node.key for node in self._order]

    def __len__(self) -> int:
        return len(self._nodes)



# Pointer order in add_to_front: set the new node’s own links first, then update its neighbours. 
# If you change self._head.next before reading it, you lose the reference to the old first node. 
# When narrating, say: “I’m wiring the new node in before I break any existing links.”