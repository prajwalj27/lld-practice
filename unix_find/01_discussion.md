# Unix `find` with combinable filters (new grad LLD)

## 1. Discussion

### Clarifying questions

1. **Are we searching a real file system or an in-memory model?**
   Interviewer: An in-memory tree that you build. Using the real OS is out of scope.
2. **What's in the tree?**
   Interviewer: Directories contain files and other directories. A file has a name and a size in bytes.
3. **What does `find` return?**
   Interviewer: The full paths of matching files. Directories are always searched into but never returned.
4. **Which filters are needed?**
   Interviewer: Size, extension, and name.
5. **How does the size filter work?**
   Interviewer: A minimum, a maximum, or both, in bytes and inclusive.
6. **Is the extension match case-sensitive? What about multi-dot names?**
   Interviewer: Ignore case, so "TXT" matches "txt". Only the last part counts, so `archive.tar.gz` has the extension "gz". Dotfiles like `.bashrc` have no extension.
7. **Is the name match exact, or does it support wildcards?**
   Interviewer: Unix-style wildcards, where `*` is any characters and `?` is one character. It's case-sensitive, like `find -name`, and it matches the file name only, not the full path.
8. **How do filters combine?**
   Interviewer: With AND and OR, nested to any depth, such as `(jpg AND small) OR name "resume*"`.
9. **What if no filter is given?**
   Interviewer: Return every file.
10. **Does the order of results matter?**
    Interviewer: Any consistent order is fine.
11. **Should it be easy to add new filter types later?**
    Interviewer: Yes. This question is worth asking, because the answer drives the whole design.
12. **What's out of scope?**
    Interviewer: The real file system, symlinks, permissions, modification dates, regex, parsing command-line input, and concurrency.

### Requirements

```
requirements
1. in-memory tree: directories contain files and directories; file = name + size in bytes
    - names in one directory are unique; names can't be empty or contain "/"
2. find(root, filter) returns full paths of matching files
    - directories are searched into, never returned
    - no filter -> every file
3. filters:
    - size: min and/or max bytes, inclusive
    - extension: last part after the dot, case-insensitive; dotfiles have none
    - name: Unix wildcards (* and ?), case-sensitive, name only
4. filters combine with AND / OR, nested to any depth
5. adding a new filter type must not require changing the finder
6. reject invalid filters (no size bounds, min > max, empty extension/pattern, empty AND/OR)

out of scope
- real file system, symlinks, permissions, dates
- regex, CLI parsing
- concurrency
```

### Entities

The nouns are file, directory, path, filter, size, extension, name, and results.

- **File.** Pure data: a name and a size, and neither changes, so it's a frozen data class. It also exposes `extension` as a read-only property.
- **Directory.** It holds children that are added after creation, so it's a mutable data class.
- **Filter.** The interface, with one method: `matches(file) -> bool`.
- **SizeFilter, ExtensionFilter, NameFilter.** The leaf filters. Each one checks a single attribute.
- **AndFilter, OrFilter.** Filters that are built from other filters. This is what makes nesting work.
- **FileFinder.** Walks the tree and applies a filter to each file.

**Nouns that aren't entities:**

- **Path.** It's a string built during the walk.
- **Size, extension, and name.** These are attributes of File.
- **Results.** Just a list of paths.

**The key idea:** AND and OR are filters made of filters. Because `AndFilter` *is* a `Filter`, it can go anywhere a filter can, including inside another `OrFilter`. This is the **Composite pattern**, and it gives you nesting to any depth with no extra code.