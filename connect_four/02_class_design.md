# Connect Four: class design and relationships

Design top-down: start with Game, the entry point, then Board, then Player. For each class, go back to the requirements and ask, "What must this class remember to enforce this?" That gives the state. Then add one method per outside need.

## Deriving the state

| Requirement | Game must track |
|---|---|
| Two players take turns on a board | both players, whose turn it is, the board |
| Game ends with a win or a draw | the game state |
| A player wins | who won (if anyone) |

| Requirement | Board must track |
|---|---|
| 7 × 6 board | fixed rows and columns |
| Disc falls to the lowest empty row | what's in each cell (the grid) |
| Full board is a draw | whether any cell is still empty |
| Four in a row wins | enough grid detail to count connected discs |

## Class design

```
enum DiscColor:  RED, YELLOW
enum GameState:  IN_PROGRESS, WON, DRAW

class Player:                     (frozen dataclass)
    - name: str
    - color: DiscColor

class Board:
    - ROWS = 6, COLS = 7, WIN_LENGTH = 4         (class constants)
    - DIRECTIONS = ((0,1), (1,0), (1,1), (-1,1))
    - _grid: list[list[DiscColor | None]]
    + rows, cols -> int                          (properties)
    + cell(row, col) -> DiscColor | None
    + can_place(column) -> bool
    + place_disc(column, color) -> int | None    (row it landed in; None = invalid)
    + is_full() -> bool
    + check_win(row, col, color) -> bool
    - _count_in_direction(row, col, dr, dc, color) -> int
    - _in_bounds(row, col) -> bool

class Game:
    - _board: Board
    - _player1, _player2: Player
    - _current_player: Player
    - _state: GameState
    - _winner: Player | None
    + Game(player1, player2)
    + make_move(player, column) -> bool
    + board, current_player, state, winner       (read-only properties)
    - _other(player) -> Player
```

## Relationships

- **Game owns one Board and holds two Players.** Callers talk only to Game.
- **Board stores `DiscColor`, not `Player`.** That keeps Board independent, so you can test it with plain enum values and never create a Player.
- **Player is referenced by Game, never by Board.** Board only ever sees a color.

## Flow of `make_move`

```
make_move(player, column)
  ├─ game over?              -> False
  ├─ not player's turn?      -> False
  ├─ row = board.place_disc(column, color)
  │     └─ out of bounds / full -> None -> False
  ├─ board.check_win(row, column, color)? -> WON, winner = player
  ├─ else board.is_full()?               -> DRAW
  ├─ else switch turns
  └─ True
```

## Design decisions worth saying out loud

- **`make_move` is the only method that changes state.** Everything else is read-only. A UI can show "Bob's turn" from `current_player` without repeating any turn logic.

- **Grid rules live in Board, game rules in Game.** Game never checks column bounds or fullness. It calls `place_disc` and treats `None` as "invalid move". Board owns bounds, placement, and win detection; Game owns turns and state.

- **`place_disc` returns the row.** Game can pass `(row, column)` straight to `check_win` without scanning again.

- **Only the last disc can create a new win.** So `check_win` scans out from that one cell, not the whole board.

- **Four direction vectors and one helper.** Rather than separate methods for horizontal, vertical, and the two diagonals, each `(dr, dc)` pair is counted forward and backward with `_count_in_direction`. That's four vectors covering all eight directions, and interviewers like seeing the pattern.

- **`winner` is optional, not a special "NONE" value.** In a draw there's no winner, so `None` says exactly that.

- **The state is an enum, not boolean flags.** `IN_PROGRESS / WON / DRAW` can't contradict itself. Two flags like `is_over` and `is_draw` could both be set in a nonsensical combination.

- **Invalid moves return `False` before anything changes.** Raising a custom exception is a fine alternative; ask the interviewer which they prefer.

- **`make_move` takes the player explicitly.** It could just use `current_player`, but passing the player in matches a networked setup where moves arrive tagged with who sent them. Either choice is fine if you explain it.

## Python choices and why

### Classes

- **Player is `@dataclass(frozen=True)`.** It's pure data that never changes after creation. Freezing it turns an accidental change into an error. The generated `__eq__` compares name and color, so `player != self._current_player` still works when a move arrives with a separate but identical `Player` object, as it would over a network. `__post_init__` rejects an empty name.
- **Board and Game are regular classes.** They hold state that changes (the grid, the turn, the game state) behind methods, and they're defined by what they do. Their fields shouldn't be constructor arguments or public, so a data class would be the wrong fit.
- **DiscColor and GameState are `Enum`s.** Each is a fixed set of values, so a typo like `"REDD"` is impossible, and the game can't be "won" and "draw" at once. Enum members are compared with `is`.

### Decorators and attributes

- **`@property` for `rows`, `cols`, `board`, `current_player`, `state`, `winner`.** Callers read them like fields (`game.winner`), but there's no setter, so they're read-only. The values themselves live in private fields like `_state`. Together, that guarantees `make_move` is the only thing that changes the game.
- **`ClassVar` for `ROWS`, `COLS`, `WIN_LENGTH`, `DIRECTIONS`.** These are the same for every board, so they belong to the class, not each instance. `ClassVar` makes that explicit to readers and type checkers. `DIRECTIONS` is a tuple so it can't be modified.
- **Leading underscores on `_grid`, `_count_in_direction`, `_in_bounds`, `_other`.** These are internal details. Callers use the public methods only.

### Return values vs exceptions

The rule: **expected outcomes return a value; misuse raises an exception.**

- **`make_move` returns `False` for an invalid move.** A full column or an out-of-turn move is a normal thing to happen during play, and the requirement says to reject it. A bool keeps the caller simple, and the state is left untouched.
- **`place_disc` returns `int | None`.** `None` means "no row", which can't be confused with a real row number. The type hint tells the caller they have to handle it.
- **Setup and caller bugs raise.**
  - `ValueError` when both players share a color or a name is empty. A game in that state can't be valid, so it shouldn't be created at all.
  - `IndexError` when `cell()` is asked for a square off the board. That's a bug in the calling code, not a game move.

### Small details

- **The grid is built with `[[None] * COLS for _ in range(ROWS)]`.** Writing `[[None] * COLS] * ROWS` repeats the *same* row list six times, so one disc would appear in every row.
- **`is` for enums, `==` / `!=` for players.** Enum members are single objects, so identity is the right check. Players are compared by value.
- **`any()` in `is_full`.** It stops at the first column with space.

## Complexity

- `place_disc` and `can_place` are O(rows).
- `check_win` is O(1) in practice: at most 4 directions × 3 cells each way.
- `is_full` is O(cols).

Optimization to mention but not build: keep a `heights[col]` array for O(1) placement. For a 7 × 6 board, the simple loop is fine.
