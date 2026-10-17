# 5. Extensibles

## 1. NOT (Unix `!`)

This is one more class, with no other changes. I tested it with the operators in the next section.

```python
class NotFilter(Filter):
    def __init__(self, inner: Filter) -> None:
        if not isinstance(inner, Filter):
            raise TypeError(f"Not a filter: {inner!r}")
        self._inner = inner

    def matches(self, file: File) -> bool:
        return not self._inner.matches(file)
```

## 2. Nicer syntax with `&`, `|`, and `~`

Add operator methods to the `Filter` base class, and every filter gets them:

```python
class Filter(ABC):
    @abstractmethod
    def matches(self, file: File) -> bool: ...

    def __and__(self, other: "Filter") -> "Filter":
        return AndFilter(self, other)

    def __or__(self, other: "Filter") -> "Filter":
        return OrFilter(self, other)

    def __invert__(self) -> "Filter":
        return NotFilter(self)

# (jpg AND under 100 KB) OR name "resume*"
query = (ExtensionFilter("jpg") & SizeFilter(max_bytes=100 * KB)) | NameFilter("resume*")
```

The usual Python precedence applies: `~` binds tightest, then `&`, then `|`. Use parentheses to be explicit.

## 3. More filter types: modification date, owner, file type

- **Modification date.** Add a `modified_at: int` field to `File`, then write a `ModifiedAfterFilter(timestamp)`. The finder doesn't change.
- **Returning directories too** (Unix `-type d`). Let filters accept either kind of entry, add a `TypeFilter("file" | "dir")`, and have `_walk` test directories as well as files.

**What to say:** "Every new criterion is one new class. That's the payoff of the interface."

## 4. Depth limits (`-maxdepth`, `-mindepth`)

These are traversal settings, so they belong to the finder, not to the filters. Store `max_depth` in the `FileFinder` constructor, pass `depth` through `_walk`, and stop going deeper once `depth == max_depth`.

## 5. Deep trees and streaming results

Swap the recursion for an explicit stack, and `yield` each path instead of building a list. Results then appear as they're found, like Unix `find`, and the caller can stop early.

```python
from collections.abc import Iterator

def iter_find(self, root: Directory, file_filter: Filter | None = None) -> Iterator[str]:
    stack = [(root, root.name)]
    while stack:
        directory, path = stack.pop()
        for entry in directory.children.values():
            entry_path = f"{path}/{entry.name}"
            if isinstance(entry, Directory):
                stack.append((entry, entry_path))
            elif file_filter is None or file_filter.matches(entry):
                yield entry_path
```

The order differs from the recursive version: a directory's own files come before its subdirectories. Mention that if the interviewer cares about order. With a generator, limiting results ("first 10 matches") is just `itertools.islice(finder.iter_find(...), 10)`.

## 6. A regex name filter

Compile the pattern once in `__init__` with `self._regex = re.compile(pattern)`, and use `self._regex.fullmatch(file.name)` in `matches`. Invalid regex raises `re.error`, which you can turn into a `ValueError`.

## 7. Searching the real file system

Replace the in-memory tree with `os.scandir()` or `pathlib.Path.iterdir()`, and build a `File` from each entry's name and `stat().st_size`. The filters don't change. New edge cases appear:

- Permission errors: skip the directory and keep going.
- Symlink loops: track visited directories by `(st_dev, st_ino)`.
- Files that disappear mid-scan.

## 8. Parsing a command-line query

To support something like `-name "*.txt" -o -size +1M`, write a small parser that turns tokens into the filter tree. AND binds tighter than OR, as in Unix `find`. The finder and filters stay the same; the parser just builds composite filters.

## 9. Performance

- **Order filters by cost inside an AND.** Cheap checks like extension and size go before expensive ones like regex, and short-circuiting skips the rest.
- **Index for repeated searches.** If the same tree is searched many times, keep an index such as extension → files, so a pure extension query skips the walk entirely.

## 10. Parallel search

For a huge real file system, search subdirectories in parallel with a thread pool and merge the results. Mention it in one line. At the new grad level, you don't need to build it.

**What to say in the interview:** "Filters follow the Composite pattern. And and Or are filters made of filters, so any nesting works for free. The finder only knows the `Filter` interface, so new criteria are new classes, and the traversal never changes."