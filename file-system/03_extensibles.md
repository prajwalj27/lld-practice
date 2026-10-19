# File System: follow-ups

Juniors often get none of these, mid-level one or two, seniors several. Explaining where the change lives is usually enough. I tested the code for 1, 2, 3, and 4.

## 1. Thread safety

**The race.** Two threads run `create_file("/home/notes.txt", ...)` at the same time. Both resolve `/home`, both call `has_child("notes.txt")` and see `False`, and both add. The second overwrites the first, or `add_child` raises halfway through. The gap between *check* and *act* is the problem.

**Coarse lock: the right default.** One lock for the whole file system. Every public method runs while holding it, so only one operation happens at a time.

```python
import functools
import threading

def synchronized(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper

class FileSystem:
    def __init__(self) -> None:
        self._root = Folder(self.ROOT_NAME)
        self._lock = threading.RLock()

    @synchronized
    def create_file(self, path: str, content: str = "") -> File: ...
    # same decorator on create_folder, get, list_contents, delete, rename, move
```

- **`RLock`, not `Lock`:** a locked method can call another locked method (say `move` calling `get`) without deadlocking itself.
- **The GIL doesn't help.** A thread can be switched out between `has_child` and `add_child`, so you still need the lock.
- In a test with 50 threads creating the same file, exactly one succeeded and 49 got `EntryExistsError`.

**Finer-grained: one lock per folder.** Threads working in different folders no longer block each other. Lock only the parent folder around check-then-add.

- **`move` touches two folders.** Thread A moves `/alice → /bob` while thread B moves `/bob → /alice`. Each holds one lock and waits for the other: a **deadlock**.
- **The fix is lock ordering.** Always take the two locks in a fixed order, for example by `id(folder)`. Every thread then reaches for the same lock first, so no one waits in a circle.
- **The honest catch:** `move`'s cycle check reads the whole chain of ancestors, which another thread could be changing. Per-folder locks are much harder to get right, which is why the coarse lock is the interview answer. Mention fine-grained locks and lock ordering, but don't build them.

**Read-write lock.** `get` and `list_contents` only read. A read-write lock lets many readers in at once and gives writers exclusive access, which helps when reads far outnumber writes. Python's standard library has no read-write lock, so you'd write a small one or use a library.

## 2. Search by name

**Simple first: walk the tree.** O(n) per search, and no extra state to keep in sync.

```python
from collections.abc import Iterator

def iter_entries(folder: Folder) -> Iterator[FileSystemEntry]:
    """Every entry below folder, using an explicit stack (no recursion limit)."""
    stack = [folder]
    while stack:
        current = stack.pop()
        for entry in current.children:
            yield entry
            if isinstance(entry, Folder):
                stack.append(entry)

# on FileSystem
def search(self, name: str, start: str = "/") -> list[str]:
    root = self.get(start)
    if not isinstance(root, Folder):
        raise NotAFolderError(f"Not a folder: {start}")
    return sorted(e.path for e in iter_entries(root) if e.name == name)
```

It's a generator, so a caller who wants only the first match can stop early.

## 3. Search index: O(1) lookups

If search is frequent, keep a map from name to every entry with that name, and update it on every change.

```python
from collections import defaultdict

# FileSystem.__init__
self._by_name: defaultdict[str, set[FileSystemEntry]] = defaultdict(set)

# after a successful create:  self._by_name[entry.name].add(entry)
# rename / move:              remove from the old name's set, add under the new name
# delete:                     remove the entry AND everything below it

def delete(self, path: str) -> None:
    entry = self.get(path)
    ...  # existing delete
    gone = [entry, *iter_entries(entry)] if isinstance(entry, Folder) else [entry]
    for removed in gone:
        self._unindex(removed, removed.name)

def search(self, name: str) -> list[str]:
    return sorted(e.path for e in self._by_name.get(name, ()))
```

Points worth saying:

- **Deleting a folder must un-index its whole subtree.** If it doesn't, `search` keeps returning files that no longer exist. This is the bug that's easiest to miss.
- **Update the index only after the operation succeeds.** A failed rename must leave the index unchanged.
- **Sets, not lists.** Removing one entry from a set is O(1).
- **Empty sets are deleted,** so the index doesn't fill up with names that no longer exist.
- **More search features:**
  - **Prefix search** (`config*`): use a trie keyed by name.
  - **`*.txt`:** a second index by extension, like the Unix find problem.
  - **Searching file contents:** an inverted index from words to files. Only build this if asked.

## 4. Create missing parent folders (`mkdir -p`)

Add a `parents` flag. Walk down, creating any folder that's missing. A part that exists as a file is an error.

```python
def create_folder(self, path: str, parents: bool = False) -> Folder:
    if not parents:
        ...  # existing behavior
    current = self._root
    for part in self._split(path):
        child = current.get_child(part)
        if child is None:
            self._validate_name(part)
            child = Folder(part)
            current.add_child(child)
        elif not isinstance(child, Folder):
            raise NotAFolderError(f"Not a folder: {child.path}")
        current = child
    return current
```

With `parents=True`, a folder that already exists isn't an error, which matches `mkdir -p`.

## 5. Delete only empty folders (`rmdir`)

One check in `delete`, before removing anything:

```python
entry = parent.get_child(name)
if isinstance(entry, Folder) and entry.children:
    raise FolderNotEmptyError(f"Folder not empty: {path}")
```

Add `recursive: bool = False` if both behaviors are needed.

## 6. Relative paths and a current folder (`cd`, `..`)

- Keep `self._cwd: Folder` on FileSystem, starting at the root, and add `cd(path)`.
- `_split` is the only place paths are parsed. A path that doesn't start with `/` starts from `_cwd` instead of the root.
- `.` means "stay here" and `..` means "go to the parent", where the root's parent is the root.
- Edge case: deleting or moving the folder that `_cwd` points to. Either block it, or reset `_cwd` to the root.

## 7. File operations and folder size

- **Write and append:** `write(path, content)` and `append(path, text)` on FileSystem resolve the path, check it's a File, and set `content`.
- **Size:** a `size` property on each entry. A file's size is `len(content)`. A folder's size is the sum of its children's, computed by walking down. If that becomes slow, cache it on each folder and update every ancestor's cached size on each change. That's the same trade-off as caching the path: faster reads, more work keeping the cache correct.

## 8. Permissions, timestamps, symbolic links

- **Timestamps:** `created_at` and `modified_at` on FileSystemEntry. Inject a clock, the same idea as in the parking lot and the locker.
- **Permissions:** an owner and a permission mode on each entry. Every FileSystem method checks the caller's rights before acting, so the check lives in one place, the facade.
- **Symbolic links:** a third subclass, `Symlink(FileSystemEntry)`, that stores a target path. `_walk` follows it when resolving. New edge case: links that point in a loop, so cap how many links one resolution can follow, as real file systems do.

Each one is a new field or subclass, and none of them changes how the tree itself works. That's the payoff of the shared base class.

## What interviewers look for, by level

- **Junior.** Models the tree correctly: a FileSystem entry point, plus File and Folder nodes. Create and delete work with proper path parsing, and missing paths and duplicate names are rejected. A list of children instead of a dict is acceptable. You may not spot the shared base class unprompted, but should find it when asked what File and Folder have in common.
- **Mid-level.** Extracts FileSystemEntry without being asked. Explains why a parent pointer beats a stored path, at least once asked "what happens when you rename a folder with thousands of entries below it?" `move` updates the parent pointers correctly. Might need a hint about the cycle check, but implements it cleanly once prompted.
- **Senior.** Raises the parent-pointer trade-off and the cycle check unprompted. Discusses thread safety: the check-then-act race, locking two folders in `move`, and lock ordering against deadlock, plus coarse vs fine-grained locking. Has a plan for search indexing (name maps, tries) and for adding symlinks or permissions without restructuring.
