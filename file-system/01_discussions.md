# File System (new grad LLD): discussion

Prompt: design an in-memory file system that supports creating files and folders, navigating paths, and basic file operations.

Everyone uses a file system daily, which makes it tempting to skip the questions and start designing. Don't: your picture of "a file system" may not match the interviewer's scope.

## Clarifying questions

Cover what the system does, what the structure looks like, what goes wrong, and what's out of scope.

1. **One root like Unix, or several like Windows drive letters?**
   Interviewer: One root. Unix-style paths like `/home/user/file.txt`. That keeps path parsing simple.

2. **Which operations?**
   Interviewer: Create, delete, and list, plus move and rename. You should also be able to get whatever is at any path.

3. **Do files hold content, or are they just names?**
   Interviewer: They hold content. A plain string is enough.

4. **How should errors work: a missing parent folder, deleting the root, a name that's already taken?**
   Interviewer: Raise exceptions, with a specific type for each kind of failure, so callers can handle them differently.

5. **What scale? Dozens of entries, or many more?**
   Interviewer: Tens of thousands, and it should stay fast with deep folder trees. This answer drives the data structure choices later.

6. **Can a caller find out where an entry lives?**
   Interviewer: Yes. Given a file or folder, return its full path.

7. **Relative paths like `../docs`?**
   Interviewer: No, absolute paths only.

8. **Can you delete a folder that still has things in it?**
   Interviewer: Yes, like `rm -rf`: the whole subtree goes. (If they'd said no, it's a one-line check.)

9. **What's out of scope?**
   Interviewer: Permissions, ownership, timestamps, symbolic links, search, persistence, and any UI.

## Requirements

```
requirements
1. hierarchical file system with a single root "/"
2. files store string content
3. folders contain files and other folders
4. create and delete files and folders
    - deleting a folder removes everything inside it
5. list the contents of a folder
6. get the entry at any absolute path (e.g. /home/user/docs)
7. rename and move files and folders
8. get the full path of any file or folder
9. raise a specific error for each failure:
    - malformed path or name, or an operation on the root
    - nothing at the path
    - name already taken
    - a folder was needed but the path is a file
10. stay fast with tens of thousands of entries and deep trees

out of scope
- search
- relative paths (../ or ./)
- permissions, ownership, timestamps
- file-type-specific behavior
- persistence / disk storage
- symbolic links
- ui
```

## Entities

Scan the requirements for nouns that have state or behavior.

- **File: an entity.** It has a name, holds content, and sits somewhere in the tree. It's a leaf: it can't contain anything.
- **Folder: an entity.** It has a name and contains other entries, files or folders. It doesn't hold content of its own.
- **Path: not an entity.** `/home/user/docs` is a string that names a location. It's an input to operations, with no state or behavior of its own, so it gets parsed, not modeled.
- **FileSystem: the orchestrator.** Something has to own the root and turn `create_file("/home/user/notes.txt", "hi")` into "find `/home/user`, then add the file there". That's the public API.
- **FileSystemEntry: found during class design, not here.** Once File and Folder are written side by side, they share a name, a parent, and a path. That shared part becomes an abstract base class.

| Entity | Job |
|---|---|
| **FileSystem** | Owns the root, parses paths, and exposes every operation. Callers never touch folders directly to change the tree. |
| **FileSystemEntry** | What every node has: a name, a parent, and a computed full path. Abstract. |
| **Folder** | A node that holds children by name, and keeps each child's parent pointer in sync. Knows nothing about path strings. |
| **File** | A leaf node that holds string content. |

**The tree:**

```
FileSystem
 └── root: Folder("/")
      ├── Folder("home")
      │    └── Folder("user")
      │         ├── File("notes.txt")
      │         └── Folder("docs")
      └── File("readme.txt")
```

FileSystem owns the root. Each folder can hold any mix of files and folders, to any depth. Files are always leaves.
