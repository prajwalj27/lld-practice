# Class design and relationships

**Class design:**
```
class File:                    (frozen dataclass)
    - name: str
    - size_bytes: int
    + extension -> str         (property)

class Directory:               (mutable dataclass)
    - name: str
    - children: dict[str, File | Directory]
    + add_file(name, size_bytes) -> File
    + add_directory(name) -> Directory

abstract class Filter:
    + matches(file) -> bool

class SizeFilter(Filter):        - _min_bytes, _max_bytes: int | None
class ExtensionFilter(Filter):   - _extension: str          (normalized)
class NameFilter(Filter):        - _pattern: str

abstract class CompositeFilter(Filter):
    - _filters: tuple[Filter, ...]
class AndFilter(CompositeFilter):   matches = all(...)
class OrFilter(CompositeFilter):    matches = any(...)

class FileFinder:
    + find(root, file_filter=None) -> list[str]
    - _walk(directory, path, file_filter, results) -> None
```

**Relationships:**

- A Directory contains many Files and Directories. That makes a recursive tree, and it's the Composite pattern again, this time for the file system.
- FileFinder walks the Directory tree and calls `filter.matches(file)` on each File. It only knows about the `Filter` interface.
- AndFilter and OrFilter each contain many Filters, any of which can be another composite, so the filter expression is also a tree.
- The leaf filters read File's attributes.

**Design decisions worth saying out loud:**

- **The finder depends only on `Filter`.** A new filter type means adding one class, with no change to `FileFinder`. That's the open/closed principle, the same move as the eviction policies in the cache.
- **`CompositeFilter` holds the shared setup.** AND and OR both need "store at least one filter, and make sure each is a filter." Putting that in one base class means each subclass is a single line.
- **Short-circuiting.** `all()` and `any()` with a generator stop early, so `AND` stops at the first failing filter. Putting cheap filters first in an AND makes it faster.
- **Filters are normalized and validated once, in the constructor.** For example, `".TXT"` becomes `"txt"` up front, so `matches` stays simple and fast.
- **File is frozen, Directory isn't.** That follows the data class rule: a file never changes, but a directory gains children.
- **Filters are regular classes, not data classes.** They're defined by what they do, not by their fields.
- **Directory children are a dict keyed by name.** That gives an O(1) check for duplicate names and keeps insertion order for stable output.

**Complexity:** O(N × F), where N is the number of files and F is the number of leaf filters in the expression, in the worst case. Every directory is visited once.