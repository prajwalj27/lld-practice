from lru_cache import LRUCache


def main() -> None:
    cache = LRUCache(2)

    print("--- Fill the cache (capacity 2) ---")
    cache.put("a", 1)
    cache.put("b", 2)
    print("Order (most -> least recent):", cache.keys())

    print("\n--- get('a') makes 'a' the most recent ---")
    print("get('a'):", cache.get("a"))
    print("Order:", cache.keys())

    print("\n--- put('c') when full evicts the LRU key ---")
    cache.put("c", 3)
    print("Order:", cache.keys())
    print("get('b'):", cache.get("b"))

    print("\n--- Updating an existing key doesn't evict ---")
    cache.put("a", 10)
    print("get('a'):", cache.get("a"))
    print("Order:", cache.keys(), "| size:", len(cache))

    print("\n--- Capacity 1 ---")
    tiny = LRUCache(1)
    tiny.put("x", 1)
    tiny.put("y", 2)
    print("get('x'):", tiny.get("x"), "| get('y'):", tiny.get("y"))

    print("\n--- Invalid capacity ---")
    try:
        LRUCache(0)
    except ValueError as error:
        print("Error:", error)


if __name__ == "__main__":
    main()


# --- Fill the cache (capacity 2) ---
# Order (most -> least recent): ['b', 'a']

# --- get('a') makes 'a' the most recent ---
# get('a'): 1
# Order: ['a', 'b']

# --- put('c') when full evicts the LRU key ---
# Order: ['c', 'a']
# get('b'): None

# --- Updating an existing key doesn't evict ---
# get('a'): 10
# Order: ['a', 'c'] | size: 2

# --- Capacity 1 ---
# get('x'): None | get('y'): 2

# --- Invalid capacity ---
# Error: Capacity must be positive

# The key moment is the third block. The get('a') call is the reason b, not a, gets evicted. Without it, a would have been the oldest.
