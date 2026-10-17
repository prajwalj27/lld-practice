import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from fnmatch import fnmatchcase


# ---------- File system model ----------

def _validate_name(name: str) -> None:
    if not name or "/" in name:
        raise ValueError(f"Invalid name: {name!r}")


@dataclass(frozen=True)
class File:
    name: str
    size_bytes: int

    def __post_init__(self) -> None:
        _validate_name(self.name)
        if self.size_bytes < 0:
            raise ValueError("Size cannot be negative")

    @property
    def extension(self) -> str:
        """
        Text after the last dot, without the dot; "" if there is none.
        - "a.tar.gz" -> "gz"
        - ".bashrc" -> "" (a dotfile, not an extension)
        - "notes" -> ""
        """
        return os.path.splitext(self.name)[1].removeprefix(".")


@dataclass
class Directory:
    # Not frozen: children are added after creation.
    name: str
    children: dict[str, "File | Directory"] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_name(self.name)

    def add_file(self, name: str, size_bytes: int) -> File:
        """
        Core logic:
        - Create a file and store it as a child, keyed by name
        - Return it

        Edge cases:
        - Name already used in this directory -> ValueError
        - Empty name, "/" in name, or negative size -> ValueError (from File)
        """
        self._check_unique(name)
        file = File(name, size_bytes)
        self.children[name] = file
        return file

    def add_directory(self, name: str) -> "Directory":
        """
        Core logic:
        - Create a subdirectory, store it as a child, and return it
          so the caller can keep building inside it

        Edge cases:
        - Name already used in this directory -> ValueError
        """
        self._check_unique(name)
        directory = Directory(name)
        self.children[name] = directory
        return directory

    def _check_unique(self, name: str) -> None:
        if name in self.children:
            raise ValueError(f"{name!r} already exists in {self.name!r}")


# ---------- Filter interface ----------

class Filter(ABC):
    @abstractmethod
    def matches(self, file: File) -> bool:
        """Return True if the file passes this filter."""


# ---------- Leaf filters ----------

class SizeFilter(Filter):
    def __init__(self, min_bytes: int | None = None, max_bytes: int | None = None) -> None:
        """
        Core logic:
        - Keep files whose size is within [min_bytes, max_bytes], inclusive
        - Either bound can be left out

        Edge cases:
        - Both bounds missing -> ValueError (the filter would mean nothing)
        - Negative bound -> ValueError
        - min_bytes > max_bytes -> ValueError (nothing could ever match)
        """
        if min_bytes is None and max_bytes is None:
            raise ValueError("Give at least one of min_bytes or max_bytes")
        if any(b is not None and b < 0 for b in (min_bytes, max_bytes)):
            raise ValueError("Size bounds cannot be negative")
        if min_bytes is not None and max_bytes is not None and min_bytes > max_bytes:
            raise ValueError("min_bytes cannot be greater than max_bytes")
        self._min_bytes = min_bytes
        self._max_bytes = max_bytes

    def matches(self, file: File) -> bool:
        if self._min_bytes is not None and file.size_bytes < self._min_bytes:
            return False
        if self._max_bytes is not None and file.size_bytes > self._max_bytes:
            return False
        return True


class ExtensionFilter(Filter):
    def __init__(self, extension: str) -> None:
        """
        Core logic:
        - Normalize once: drop a leading dot and lowercase
          ("TXT" and ".txt" both become "txt")

        Edge cases:
        - Empty extension, or just "." -> ValueError
        """
        normalized = extension.removeprefix(".").lower()
        if not normalized:
            raise ValueError("Extension cannot be empty")
        self._extension = normalized

    def matches(self, file: File) -> bool:
        """
        Core logic:
        - Compare the file's extension to the target, ignoring case

        Edge cases:
        - Multi-dot names: only the last part counts ("a.tar.gz" -> "gz")
        - Dotfiles (".bashrc") and names with no dot have no extension
        """
        return file.extension.lower() == self._extension


class NameFilter(Filter):
    def __init__(self, pattern: str) -> None:
        """
        Core logic:
        - Store a Unix-style pattern: * = any characters, ? = one character,
          no wildcard = exact name

        Edge cases:
        - Empty pattern -> ValueError
        """
        if not pattern:
            raise ValueError("Pattern cannot be empty")
        self._pattern = pattern

    def matches(self, file: File) -> bool:
        """
        Core logic:
        - Match the file's name (not its full path) against the pattern

        Edge cases:
        - Case-sensitive, like Unix find -name ("Report*" won't match "report.txt")
        """
        return fnmatchcase(file.name, self._pattern)


# ---------- Composite filters ----------

class CompositeFilter(Filter, ABC):
    """A filter built from other filters. Shared setup for AND and OR."""

    def __init__(self, *filters: Filter) -> None:
        """
        Core logic:
        - Store any number of filters; they can be leaves or other composites,
          which is what makes nesting like (A AND B) OR C work

        Edge cases:
        - No filters -> ValueError (an empty AND/OR has no clear meaning)
        - Something that isn't a Filter -> TypeError
        """
        if not filters:
            raise ValueError(f"{type(self).__name__} needs at least one filter")
        for f in filters:
            if not isinstance(f, Filter):
                raise TypeError(f"Not a filter: {f!r}")
        self._filters = filters


class AndFilter(CompositeFilter):
    def matches(self, file: File) -> bool:
        # True only if every filter matches; all() stops at the first False.
        return all(f.matches(file) for f in self._filters)


class OrFilter(CompositeFilter):
    def matches(self, file: File) -> bool:
        # True if any filter matches; any() stops at the first True.
        return any(f.matches(file) for f in self._filters)


# ---------- Finder ----------

class FileFinder:
    def find(self, root: Directory, file_filter: Filter | None = None) -> list[str]:
        """
        Core logic:
        - Walk the tree depth-first, starting at root
        - Directories are always searched into, never returned
        - Return the path of every file that passes the filter

        Edge cases:
        - No filter -> return every file
        - Empty directory or no matches -> empty list
        - Very deep trees can hit Python's recursion limit (~1000 levels);
          an explicit stack avoids that
        """
        results: list[str] = []
        self._walk(root, root.name, file_filter, results)
        return results

    def _walk(
        self,
        directory: Directory,
        path: str,
        file_filter: Filter | None,
        results: list[str],
    ) -> None:
        for entry in directory.children.values():
            entry_path = f"{path}/{entry.name}"
            if isinstance(entry, Directory):
                self._walk(entry, entry_path, file_filter, results)
            elif file_filter is None or file_filter.matches(entry):
                results.append(entry_path)


# **Why `FileFinder` is its own class:** traversal could have been a method on `Directory`. Keeping it separate leaves `Directory` as a plain model, and gives traversal options like a maximum depth or BFS a natural home in the finder.