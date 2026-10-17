from unix_find import Directory, FileFinder, ExtensionFilter, SizeFilter, NameFilter, AndFilter, OrFilter


KB = 1_000
MB = 1_000_000


def build_sample_tree() -> Directory:
    home = Directory("home")

    docs = home.add_directory("docs")
    docs.add_file("resume.pdf", 120 * KB)
    docs.add_file("notes.txt", 2 * KB)
    docs.add_file("Report_2026.TXT", 50 * KB)

    photos = home.add_directory("photos")
    photos.add_file("beach.jpg", 3_500 * KB)
    photos.add_file("sunset.JPG", 4_200 * KB)
    thumbs = photos.add_directory("thumbs")
    thumbs.add_file("beach_small.jpg", 40 * KB)

    code = home.add_directory("code")
    code.add_file("main.py", 8 * KB)
    code.add_file("utils.py", 3 * KB)

    home.add_directory("empty")
    home.add_file("archive.tar.gz", 9 * MB)
    home.add_file(".bashrc", 500)
    return home


def show(label: str, paths: list[str]) -> None:
    print(f"\n--- {label} ---")
    if not paths:
        print("(no matches)")
    for path in paths:
        print(path)


def main() -> None:
    home = build_sample_tree()
    finder = FileFinder()

    show("No filter: every file", finder.find(home))

    show("Extension 'txt' (case-insensitive)",
         finder.find(home, ExtensionFilter("txt")))

    show("Size at least 1 MB",
         finder.find(home, SizeFilter(min_bytes=1 * MB)))

    show("Name matches 'beach*'",
         finder.find(home, NameFilter("beach*")))

    show("AND: jpg files of at least 1 MB",
         finder.find(home, AndFilter(ExtensionFilter("jpg"),
                                     SizeFilter(min_bytes=1 * MB))))

    show("OR: py files or txt files",
         finder.find(home, OrFilter(ExtensionFilter("py"),
                                    ExtensionFilter("txt"))))

    show("Nested: (jpg AND under 100 KB) OR name 'resume*'",
         finder.find(home, OrFilter(
             AndFilter(ExtensionFilter("jpg"), SizeFilter(max_bytes=100 * KB)),
             NameFilter("resume*"),
         )))

    show("Extension 'gz' (only the last part counts)",
         finder.find(home, ExtensionFilter("gz")))

    show("Extension 'bashrc' (a dotfile has no extension)",
         finder.find(home, ExtensionFilter("bashrc")))

    print("\n--- Invalid input ---")
    for label, make in [
        ("SizeFilter()", lambda: SizeFilter()),
        ("SizeFilter(min_bytes=10, max_bytes=5)", lambda: SizeFilter(10, 5)),
        ("AndFilter()", lambda: AndFilter()),
        ("add duplicate 'docs'", lambda: home.add_directory("docs")),
    ]:
        try:
            make()
        except (ValueError, TypeError) as error:
            print(f"{label}: {error}")


if __name__ == "__main__":
    main()

# --- No filter: every file ---
# home/docs/resume.pdf
# home/docs/notes.txt
# home/docs/Report_2026.TXT
# home/photos/beach.jpg
# home/photos/sunset.JPG
# home/photos/thumbs/beach_small.jpg
# home/code/main.py
# home/code/utils.py
# home/archive.tar.gz
# home/.bashrc

# --- Extension 'txt' (case-insensitive) ---
# home/docs/notes.txt
# home/docs/Report_2026.TXT

# --- Size at least 1 MB ---
# home/photos/beach.jpg
# home/photos/sunset.JPG
# home/archive.tar.gz

# --- Name matches 'beach*' ---
# home/photos/beach.jpg
# home/photos/thumbs/beach_small.jpg

# --- AND: jpg files of at least 1 MB ---
# home/photos/beach.jpg
# home/photos/sunset.JPG

# --- OR: py files or txt files ---
# home/docs/notes.txt
# home/docs/Report_2026.TXT
# home/code/main.py
# home/code/utils.py

# --- Nested: (jpg AND under 100 KB) OR name 'resume*' ---
# home/docs/resume.pdf
# home/photos/thumbs/beach_small.jpg

# --- Extension 'gz' (only the last part counts) ---
# home/archive.tar.gz

# --- Extension 'bashrc' (a dotfile has no extension) ---
# (no matches)

# --- Invalid input ---
# SizeFilter(): Give at least one of min_bytes or max_bytes
# SizeFilter(min_bytes=10, max_bytes=5): min_bytes cannot be greater than max_bytes
# AndFilter(): AndFilter needs at least one filter
# add duplicate 'docs': 'docs' already exists in 'home'

# The empty `empty/` directory gets searched, produces nothing, and causes no error. I ran this on Python 3.12, and the full file is file_finder.py.

