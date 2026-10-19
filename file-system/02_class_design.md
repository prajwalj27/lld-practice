# File System: class design and relationships

Design top-down: FileSystem first, since it's the entry point, then the nodes. For each class, ask what it must **remember** to meet the requirements (its state), and what it must **do** (its methods).

## Deriving the state

| Requirement | Who tracks what |
|---|---|
| Single root | FileSystem: the root folder (that's all it stores) |
| Files store content | File: `content` |
| Folders contain entries | Folder: its children, looked up by name |
| Get the full path of any entry | Every entry: its `parent`, to walk up the tree |
| Get the entry at a path | Nothing new: walk down from the root by name |

## Class design

```
abstract class FileSystemEntry:
    - _name: str
    - _parent: Folder | None
    + name -> str                    (property; setter only works while detached)
    + parent -> Folder | None        (read-only property)
    + path -> str                    (computed property)
    + is_directory -> bool           (abstract property)

class File(FileSystemEntry):
    + content: str                   (plain public attribute)
    + is_directory -> False

class Folder(FileSystemEntry):
    - _children: dict[str, FileSystemEntry]
    + is_directory -> True
    + children -> list[FileSystemEntry]          (property, returns a copy)
    + get_child(name) -> FileSystemEntry | None
    + has_child(name) -> bool
    + add_child(entry) -> None                   (sets entry's parent)
    + remove_child(name) -> FileSystemEntry | None   (clears entry's parent)
    + rename_child(old_name, new_name) -> None

class FileSystem:
    - _root: Folder
    + root -> Folder                             (read-only property)
    + create_file(path, content="") -> File
    + create_folder(path) -> Folder
    + get(path) -> FileSystemEntry
    + list_contents(path) -> list[FileSystemEntry]
    + delete(path) -> None
    + rename(path, new_name) -> None
    + move(src_path, dest_path) -> None
    - _resolve(path) -> FileSystemEntry
    - _resolve_parent(path) -> (Folder, name)
    - _split(path) -> list[str]
    - _walk(parts) -> FileSystemEntry
    - _validate_name(name), _check_name_free(folder, name), _is_same_or_ancestor(...)

exceptions: FileSystemError
    ├─ InvalidPathError
    ├─ EntryNotFoundError
    ├─ EntryExistsError
    └─ NotAFolderError
```

## Relationships

- **FileSystem owns exactly one root Folder.** Every public operation starts there.
- **File and Folder both inherit from FileSystemEntry.** They share the name, the parent, and the path logic.
- **A Folder holds many FileSystemEntries**, keyed by name. Any child can itself be a Folder, so the tree can be any depth. This is the **Composite pattern**: File is the leaf, Folder is the container, and FileSystemEntry is the common type both are handled through.
- **Every entry points back to its parent.** Parent → child (the dict) and child → parent (the pointer) is a two-way link, and only Folder changes either side.

## Flows

```
create_file(path, content) / create_folder(path)
  ├─ (parent, name) = _resolve_parent(path)    -> errors for "/", bad path, missing / file parent
  ├─ name taken?                               -> EntryExistsError
  └─ build the entry, parent.add_child(entry), return it

rename(path, new_name)
  ├─ validate new_name; (parent, old) = _resolve_parent(path)
  ├─ missing? -> EntryNotFoundError;  same name? -> no-op
  └─ parent.rename_child(old, new)             -> remove, change name, re-add

move(src, dest)
  ├─ find entry; find (dest_parent, dest_name)
  ├─ same path?                                -> no-op
  ├─ folder moving into itself or below?       -> InvalidPathError
  ├─ dest_name taken?                          -> EntryExistsError
  └─ src_parent.remove_child -> entry.name = dest_name -> dest_parent.add_child
```

## Design decisions worth saying out loud

### A FileSystem facade, not a bare root folder

You could hand callers the root Folder and let them walk down themselves. Then every caller would split path strings, step through folders, and handle missing ones on their own: the same logic copied everywhere, and no clear entry point. FileSystem puts all path handling in one place behind a small path-based API. That's the **Facade pattern**.

### A parent pointer, not a stored path

If each entry stored its full path as a string, `path` would be O(1). But renaming `/home` would mean rewriting the stored path of every entry below it, possibly thousands. So each entry stores only its parent, and `path` is computed by walking up.

- **Rename and move are O(1):** change one name or one parent pointer, and every path below updates automatically, because nothing stores it.
- **`path` is O(depth).** Trees are rarely more than 10 to 20 levels deep, so that's cheap. Cache it only if profiling says so, and remember a cache needs invalidating on every rename and move above it.
- **The cost is a two-way link.** Parent and child must always agree. That's why only Folder's `add_child` and `remove_child` touch the link.

### A dict of children, not a list

Resolving `/home/user/docs/report.txt` looks up one name at each level. With a list, each lookup scans every sibling: O(n) per level. With `dict[str, FileSystemEntry]`, it's O(1) whatever the folder size, which matters at tens of thousands of entries. A dict also can't hold two entries with the same key, so duplicate names are impossible by construction.

### An abstract base class, not just an interface

File and Folder share **state** (name, parent) and **behavior** (path), not only a method signature. An interface would make each class repeat the fields and the path logic. An abstract base class holds them once. Inheritance fits here because both really *are* entries, and that shared part will never change: every tree node has a name and a parent.

### Keeping the two-way link correct

- **`add_child` sets the parent; `remove_child` clears it.** Nothing else assigns `_parent`, so the dict and the pointers can't drift apart.
- **`add_child` refuses an entry that still has a parent.** Otherwise two folders could both claim it.
- **A name can only change while the entry is detached.** The folder stores the entry under its name as the dict key. Changing the name in place would leave it under the old key, unreachable by its new name. So `rename_child` and `move` both follow the same order: remove, change the name, add back.

### Other decisions

- **`_resolve_parent` returns `(folder, name)` together.** Every write operation needs both, and splitting the path once avoids parsing it twice.
- **Every check runs before any change.** `move` finds the source, the destination, checks for a cycle, and checks the name, and only then removes anything. A failed operation leaves the tree untouched.
- **Cycle check in `move`.** Moving `/home` into `/home/user/stuff` would make `/home` its own ancestor and cut it off from the root. Walking up from the destination folder and meeting the entry being moved means the move would create that loop.
- **`move` takes the full destination path.** `move("/a/x.txt", "/b/y.txt")` both moves and renames, like Unix `mv`.
- **Moving or renaming to the current name is a no-op**, not an "already exists" error, since nothing would change.
- **Non-empty folders can be deleted.** The subtree is simply no longer reachable. Requiring empty folders (like `rmdir`) would be one check.
- **Strict path parsing.** A path must start with `/`, and `//` or a trailing `/` is rejected, rather than guessing what the caller meant. Names can't be empty, contain `/`, or be `.` or `..`, which would look like relative paths.
- **Separate `create_file` and `create_folder`.** One method with an `is_folder` flag reads worse at the call site.

## Python choices and why

### Classes

- **FileSystemEntry is an `ABC`** with `is_directory` as an abstract property. Python won't let you create a FileSystemEntry directly, and a subclass that forgets `is_directory` fails as soon as it's created.
- **File and Folder are regular classes, not data classes.** Their state has rules: the name can only change while detached, and the parent pointer must match the folder's dict. A data class would make every field publicly assignable and generate an `__eq__` that compares by value, but two files named `a.txt` in different folders are different files. Identity (`is`) is the right comparison here, which is what a regular class gives.
- **FileSystem is a regular class.** It's the facade, holding only the root.

### Properties

- **`name` has a setter with a guard.** Callers read `entry.name` like a field. Assigning it while the entry is inside a folder raises a clear error pointing to the safe route, `FileSystem.rename`.
- **`parent` and `root` are read-only properties.** Nothing outside can rewire the tree.
- **`path` is a computed property.** It reads like a field, but it's calculated on each access from the parent pointers, so it's never out of date.
- **`children` returns a copy.** Callers can loop over it or sort it, but can't add or remove entries without going through `add_child` and `remove_child`.
- **`content` is a plain public attribute.** Any string is valid and nothing depends on it, so a property would add nothing.

### Naming

- **`list_contents`, not `list`.** A method called `list` shadows the built-in `list` inside the class body. Any method defined after it with a `-> list[...]` annotation then fails with `TypeError: 'function' object is not subscriptable` when the class loads.
- **`EntryNotFoundError` and `NotAFolderError`, not `FileNotFoundError` and `NotADirectoryError`.** Those names already exist as Python built-ins, and reusing them would hide the built-ins and confuse anyone reading `except` clauses.

### Exceptions

- **One base class, `FileSystemError`, with four specific subclasses.** Each maps to one failure in the requirements, so a caller can handle "not found" differently from "already exists", or catch `FileSystemError` for all of them.
- **`RuntimeError` for broken internal rules,** like renaming an attached entry directly or adding an entry that's still in another folder. Those can only happen through a bug in the calling code, not through normal use of the API.
- **Raise, don't return `False`.** The requirements ask for specific error types, and an exception can't be silently ignored the way a boolean can.

### Small details

- **`_split` turns a path into parts once.** `"/home/user"` → `["home", "user"]`, and `"/"` → `[]`. An empty part means `//` or a trailing slash.
- **`@staticmethod` for `_validate_name`, `_check_name_free`, and `_is_same_or_ancestor`.** They don't need the file system's state, and marking them static makes that clear.
- **`isinstance(entry, Folder)` inside FileSystem.** It tells type checkers the entry is a Folder, so `entry.children` is known to be valid afterwards. `is_directory` is there for callers that just want to know.
- **The type hint `"Folder | None"` is in quotes,** because Folder is defined below FileSystemEntry. Quoting delays evaluating the name until it exists.
- **Listing order is insertion order** (dicts keep it). A renamed entry is removed and re-added, so it moves to the end. Sort by name when displaying if order matters.

## Complexity

- Resolving a path is O(d), with d = path depth: one dict lookup per level.
- `create_file`, `create_folder`, `get`, `delete`, and `rename` are O(d).
- `move` is O(d) to resolve both paths, plus O(d) for the cycle check.
- `path` is O(d). `list_contents` is O(k) for k children.
