"""In-memory, Unix-style file system with a single root (requires Python 3.10+)."""

from abc import ABC, abstractmethod


# ---------- Exceptions ----------

class FileSystemError(Exception):
    """Base error for file system operations."""


class InvalidPathError(FileSystemError):
    """Raised for a malformed path or name, or an operation the root doesn't allow."""


class EntryNotFoundError(FileSystemError):
    """Raised when nothing exists at a path."""


class EntryExistsError(FileSystemError):
    """Raised when a name is already taken in the target folder."""


class NotAFolderError(FileSystemError):
    """Raised when a folder is required but the path points to a file."""


# ---------- Tree nodes ----------

class FileSystemEntry(ABC):
    """Shared base for File and Folder: a name, a parent, and a computed path."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._parent: "Folder | None" = None

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, new_name: str) -> None:
        """
        Core logic:
        - Change the name, but only while the entry is detached (no parent)

        Edge cases:
        - Entry is inside a folder -> RuntimeError. The folder stores it in a
          dict keyed by name, so a direct rename would leave the old key
          behind. Folder.rename_child (or FileSystem.rename) does it safely.
        """
        if self._parent is not None:
            raise RuntimeError("Rename through the parent folder, not the entry")
        self._name = new_name

    @property
    def parent(self) -> "Folder | None":
        # Read-only: only Folder.add_child / remove_child change it,
        # so parent and children can never disagree.
        return self._parent

    @property
    def path(self) -> str:
        """
        Core logic:
        - Walk up the parent pointers to the top, collecting names
        - Join them with "/"; the root's own name is "/"

        Edge cases:
        - The root -> "/"
        - A detached entry (e.g. after delete) -> path relative to its own
          top, like "notes.txt", since it's no longer under the root
        - O(depth), not O(1): the price of rename/move being O(1)
        """
        names: list[str] = []
        node: FileSystemEntry = self
        while node._parent is not None:
            names.append(node._name)
            node = node._parent
        if not names:
            return node._name
        prefix = "" if node._name == "/" else node._name
        return prefix + "/" + "/".join(reversed(names))

    @property
    @abstractmethod
    def is_directory(self) -> bool:
        """True for folders, False for files."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.path!r})"


class File(FileSystemEntry):
    def __init__(self, name: str, content: str = "") -> None:
        super().__init__(name)
        self.content = content  # plain attribute: any string is valid, nothing to protect

    @property
    def is_directory(self) -> bool:
        return False


class Folder(FileSystemEntry):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self._children: dict[str, FileSystemEntry] = {}

    @property
    def is_directory(self) -> bool:
        return True

    @property
    def children(self) -> list[FileSystemEntry]:
        # A copy, so callers can't add or remove entries behind the folder's back.
        return list(self._children.values())

    def get_child(self, name: str) -> FileSystemEntry | None:
        return self._children.get(name)

    def has_child(self, name: str) -> bool:
        return name in self._children

    def add_child(self, entry: FileSystemEntry) -> None:
        """
        Core logic:
        - Store the entry under its name
        - Set its parent pointer to this folder (the other half of the link)

        Edge cases (both are caller bugs, so they raise):
        - Name already taken here -> EntryExistsError
        - Entry already has a parent -> RuntimeError (remove it from there first;
          otherwise two folders would both claim it)
        """
        if entry._parent is not None:
            raise RuntimeError(f"{entry.name!r} is still inside another folder")
        if entry.name in self._children:
            raise EntryExistsError(f"{entry.name!r} already exists in {self.path}")
        self._children[entry.name] = entry
        entry._parent = self

    def remove_child(self, name: str) -> FileSystemEntry | None:
        """
        Core logic:
        - Remove the entry and clear its parent pointer
        - Return it, or None if there was nothing by that name
        """
        entry = self._children.pop(name, None)
        if entry is not None:
            entry._parent = None
        return entry

    def rename_child(self, old_name: str, new_name: str) -> None:
        """
        Core logic:
        - Remove under the old key, change the name, add under the new key
          (the dict key and the entry's name must always match)

        Edge cases:
        - old_name missing -> EntryNotFoundError
        - new_name taken -> EntryExistsError, checked before anything changes
        """
        if old_name not in self._children:
            raise EntryNotFoundError(f"{old_name!r} not found in {self.path}")
        if new_name in self._children:
            raise EntryExistsError(f"{new_name!r} already exists in {self.path}")
        entry = self.remove_child(old_name)
        entry.name = new_name
        self.add_child(entry)


# ---------- Facade ----------

class FileSystem:
    """The only public entry point. Every method takes an absolute path."""

    ROOT_NAME = "/"

    def __init__(self) -> None:
        self._root = Folder(self.ROOT_NAME)

    @property
    def root(self) -> Folder:
        return self._root

    def create_file(self, path: str, content: str = "") -> File:
        """
        Core logic:
        - Resolve the parent folder and the new name
        - Check the name is free, create the file, add it

        Edge cases:
        - Path is "/" -> InvalidPathError (the root has no parent)
        - Parent missing -> EntryNotFoundError; parent is a file -> NotAFolderError
        - Name taken -> EntryExistsError
        - Bad name ("", ".", "..") -> InvalidPathError
        """
        parent, name = self._resolve_parent(path)
        self._check_name_free(parent, name)
        file = File(name, content)
        parent.add_child(file)
        return file

    def create_folder(self, path: str) -> Folder:
        """Same flow and edge cases as create_file, creating a Folder."""
        parent, name = self._resolve_parent(path)
        self._check_name_free(parent, name)
        folder = Folder(name)
        parent.add_child(folder)
        return folder

    def get(self, path: str) -> FileSystemEntry:
        """Return the file or folder at path (all errors come from _resolve)."""
        return self._resolve(path)

    def list_contents(self, path: str) -> list[FileSystemEntry]:
        """
        Core logic:
        - Resolve the path and return the folder's children

        Edge cases:
        - Path is a file -> NotAFolderError
        """
        entry = self._resolve(path)
        if not isinstance(entry, Folder):
            raise NotAFolderError(f"Cannot list a file: {path}")
        return entry.children

    def delete(self, path: str) -> None:
        """
        Core logic:
        - Remove the entry from its parent; a folder takes its whole subtree with it

        Edge cases:
        - Path is "/" -> InvalidPathError
        - Nothing there -> EntryNotFoundError
        """
        parent, name = self._resolve_parent(path)
        if parent.remove_child(name) is None:
            raise EntryNotFoundError(f"Entry not found: {path}")

    def rename(self, path: str, new_name: str) -> None:
        """
        Core logic:
        - Keep the entry in the same folder, change its name

        Edge cases:
        - Path is "/" -> InvalidPathError
        - Bad new name (empty, contains "/", "." or "..") -> InvalidPathError
        - Entry missing -> EntryNotFoundError
        - Same name as now -> no-op
        - New name taken by a sibling -> EntryExistsError
        """
        self._validate_name(new_name)
        parent, old_name = self._resolve_parent(path)
        if not parent.has_child(old_name):
            raise EntryNotFoundError(f"Entry not found: {path}")
        if new_name == old_name:
            return
        parent.rename_child(old_name, new_name)

    def move(self, src_path: str, dest_path: str) -> None:
        """
        Core logic:
        - dest_path is the entry's full new path (it can also rename)
        - Remove from the source folder, set the name, add to the destination

        Edge cases (all checked before anything changes):
        - Source is "/" -> InvalidPathError
        - Source missing -> EntryNotFoundError
        - Destination folder missing or a file -> EntryNotFoundError / NotAFolderError
        - Moving a folder into itself or a descendant -> InvalidPathError (cycle)
        - Destination name taken -> EntryExistsError
        - Moving to the same path -> no-op
        """
        src_parent, src_name = self._resolve_parent(src_path)
        entry = src_parent.get_child(src_name)
        if entry is None:
            raise EntryNotFoundError(f"Source not found: {src_path}")

        dest_parent, dest_name = self._resolve_parent(dest_path)
        if dest_parent is src_parent and dest_name == src_name:
            return

        if isinstance(entry, Folder) and self._is_same_or_ancestor(entry, dest_parent):
            raise InvalidPathError(f"Cannot move {src_path} into itself")
        self._check_name_free(dest_parent, dest_name)

        src_parent.remove_child(src_name)
        entry.name = dest_name   # allowed: the entry is detached right now
        dest_parent.add_child(entry)

    # ---------- Path helpers ----------

    def _resolve(self, path: str) -> FileSystemEntry:
        return self._walk(self._split(path))

    def _resolve_parent(self, path: str) -> tuple[Folder, str]:
        """
        Core logic:
        - Return (the folder that holds the last part, the last part's name)

        Edge cases:
        - "/" has no parent -> InvalidPathError
        - The parent is a file -> NotAFolderError
        """
        parts = self._split(path)
        if not parts:
            raise InvalidPathError("This operation isn't allowed on the root")
        parent = self._walk(parts[:-1])
        if not isinstance(parent, Folder):
            raise NotAFolderError(f"Not a folder: {parent.path}")
        name = parts[-1]
        self._validate_name(name)
        return parent, name

    def _split(self, path: str) -> list[str]:
        """
        "/home/user" -> ["home", "user"]; "/" -> []

        Edge cases:
        - Not a string, empty, or relative -> InvalidPathError
        - Double or trailing slash ("/a//b", "/a/") -> InvalidPathError
        """
        if not isinstance(path, str) or not path.startswith("/"):
            raise InvalidPathError(f"Path must be absolute: {path!r}")
        if path == "/":
            return []
        parts = path[1:].split("/")
        if "" in parts:
            raise InvalidPathError(f"Empty path component in {path!r}")
        return parts

    def _walk(self, parts: list[str]) -> FileSystemEntry:
        """Start at the root and step down one name at a time."""
        current: FileSystemEntry = self._root
        for part in parts:
            if not isinstance(current, Folder):
                raise NotAFolderError(f"Not a folder: {current.path}")
            child = current.get_child(part)
            if child is None:
                raise EntryNotFoundError(f"Not found: {part!r} in {current.path}")
            current = child
        return current

    @staticmethod
    def _validate_name(name: str) -> None:
        # "." and ".." would look like relative paths, which are out of scope.
        if not isinstance(name, str) or not name or "/" in name or name in (".", ".."):
            raise InvalidPathError(f"Invalid name: {name!r}")

    @staticmethod
    def _check_name_free(folder: Folder, name: str) -> None:
        if folder.has_child(name):
            raise EntryExistsError(f"Already exists: {name!r} in {folder.path}")

    @staticmethod
    def _is_same_or_ancestor(candidate: Folder, start: Folder) -> bool:
        """Walk up from start; True if candidate is start or any folder above it."""
        node: Folder | None = start
        while node is not None:
            if node is candidate:
                return True
            node = node.parent
        return False
