"""Dry run for the in-memory file system. Run: python main.py"""

from implementation import File, FileSystem, FileSystemError, Folder


def print_tree(folder: Folder, indent: str = "") -> None:
    """Rendering is out of scope for the file system, so it lives in the runner."""
    for entry in folder.children:
        if isinstance(entry, Folder):
            print(f"{indent}{entry.name}/")
            print_tree(entry, indent + "    ")
        elif isinstance(entry, File):
            print(f"{indent}{entry.name}  ({entry.content!r})")


def show(fs: FileSystem, title: str) -> None:
    print(f"\n--- {title} ---")
    print("/")
    print_tree(fs.root, "    ")


def attempt(label: str, action) -> None:
    try:
        result = action()
        print(f"{label}: ok" + (f" -> {result}" if result is not None else ""))
    except FileSystemError as error:
        print(f"{label}: {type(error).__name__}: {error}")


def main() -> None:
    fs = FileSystem()

    fs.create_folder("/home")
    fs.create_folder("/home/user")
    fs.create_folder("/home/user/docs")
    notes = fs.create_file("/home/user/notes.txt", "hello world")
    report = fs.create_file("/home/user/docs/report.txt", "Q3 numbers")
    fs.create_file("/readme.txt", "start here")
    show(fs, "Initial tree")

    print("\n--- Lookups ---")
    print("notes.path:", notes.path)
    print("get('/home/user/docs/report.txt').content:",
          repr(fs.get("/home/user/docs/report.txt").content))
    print("list_contents('/home/user'):", fs.list_contents("/home/user"))

    print("\n--- Rename a folder: every path below it changes, nothing else is touched ---")
    fs.rename("/home", "house")
    print("notes.path: ", notes.path)
    print("report.path:", report.path)

    print("\n--- Move (and rename) a file ---")
    fs.move("/house/user/notes.txt", "/house/todo.txt")
    print("notes.name:", notes.name, "| notes.path:", notes.path)

    print("\n--- Move a whole folder ---")
    fs.move("/house/user/docs", "/docs")
    print("report.path:", report.path)
    show(fs, "Tree after rename and moves")

    print("\n--- Rejected operations (nothing changes) ---")
    attempt("create duplicate /readme.txt", lambda: fs.create_file("/readme.txt", "again"))
    attempt("create in missing folder", lambda: fs.create_file("/nope/a.txt", ""))
    attempt("create inside a file", lambda: fs.create_file("/readme.txt/a.txt", ""))
    attempt("relative path", lambda: fs.get("house/todo.txt"))
    attempt("double slash", lambda: fs.get("/house//todo.txt"))
    attempt("list a file", lambda: fs.list_contents("/readme.txt"))
    attempt("rename to a name with '/'", lambda: fs.rename("/readme.txt", "a/b"))
    attempt("rename onto a sibling", lambda: fs.rename("/docs", "readme.txt"))
    attempt("move folder into its own child", lambda: fs.move("/house", "/house/user/house"))
    attempt("delete root", lambda: fs.delete("/"))
    attempt("delete missing", lambda: fs.delete("/ghost.txt"))

    print("\n--- Setting a name directly is blocked while the entry is in a folder ---")
    try:
        notes.name = "hacked.txt"
    except RuntimeError as error:
        print("notes.name = 'hacked.txt':", error)

    print("\n--- Delete a folder with everything inside ---")
    fs.delete("/house")
    attempt("get the deleted file", lambda: fs.get("/house/todo.txt"))
    show(fs, "Final tree")


if __name__ == "__main__":
    main()
