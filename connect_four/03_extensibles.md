# Connect Four: follow-ups

How much of this you'll get depends on level. Junior candidates often get no extension questions, mid-level one or two, senior more depth. Explaining where the change lives is usually enough; you rarely need to code it.

## 1. Configurable board size (or a different win length)

Make `rows`, `cols`, and `win_length` constructor parameters on Board, with today's values as defaults. All the placement and win logic already uses those values and `_in_bounds`, so nothing else changes. Game just decides what size of board to create.

```python
class Board:
    def __init__(self, rows: int = 6, cols: int = 7, win_length: int = 4) -> None:
        if min(rows, cols) < 1 or win_length < 2:
            raise ValueError("Invalid board size")
        self._rows, self._cols, self._win_length = rows, cols, win_length
        self._grid = [[None] * cols for _ in range(rows)]
```

## 2. Undo and move history

Undo belongs in **Game**, because Game controls when state changes. Every move already goes through `make_move`, so that one place is where moves get recorded.

```python
@dataclass(frozen=True)
class Move:
    player: Player
    row: int
    col: int

# Game.__init__:   self._history: list[Move] = []
# make_move, after a successful place_disc:
#                  self._history.append(Move(player, row, column))

def undo(self) -> bool:
    if not self._history:
        return False
    last = self._history.pop()
    self._board.clear_cell(last.row, last.col)   # only new Board method needed
    self._current_player = last.player           # it's their turn again
    self._state = GameState.IN_PROGRESS          # undoing the winning or filling move reopens the game
    self._winner = None
    return True
```

Undoing the last move always leaves a board that wasn't won or full, since the game would have ended earlier otherwise. So resetting to IN_PROGRESS is correct, not just a shortcut. Add **redo** with a second stack that's cleared on every new move.

## 3. A computer opponent

The rules don't change: Game still enforces turns, and Board still owns the grid. A bot only **chooses a column**, then calls the same `make_move`.

```python
class BotEngine:
    def choose_move(self, game: Game) -> int | None:
        board = game.board
        return next((c for c in range(board.cols) if board.can_place(c)), None)

# game loop
while game.state is GameState.IN_PROGRESS:
    player = game.current_player
    column = read_input() if player == human else bot.choose_move(game)
    game.make_move(player, column)
```

Smarter bots are the **Strategy** pattern: one `BotEngine` interface, with versions like random, "win if I can, else block", or a minimax search. To test a candidate move, the bot works on a copy of the board, or makes the move and undoes it.

An alternative is a `Player` interface with `HumanPlayer` and `BotPlayer`. The separate `BotEngine` is usually the cleaner choice, though. A human player doesn't *do* anything in the code; it's just data. Keeping identity (Player) separate from decision-making (BotEngine) avoids an abstraction that adds nothing.

## 4. Networked play, spectators, multiple games (senior-level)

- **Networked.** Moves arrive tagged with a player, which is exactly why `make_move` takes `player` explicitly. Validating the sender is already built in.
- **Spectators.** Add an observer list on Game. After each successful move, notify every observer with the move and the new state (the **Observer** pattern).
- **Multiple games.** A `GameManager` holds `dict[game_id, Game]`, with one lock per game if requests can run at the same time.

## What interviewers look for, by level

- **Junior.** Sensible pieces: a board, players, and something running the turns. Working placement, and correct horizontal and vertical checks. Needing hints on diagonals is OK. Full columns and out-of-turn moves are rejected, even if just with `False`. A full game can be played to a win or a draw.
- **Mid-level.** Clean separation without being prompted. `make_move` validates before changing anything. All four directions are handled with direction vectors. Can explain where one extension would go.
- **Senior.** Explains the design choices unprompted: why Player is just data, why the state is an enum, why win checking lives on Board. Catches their own edge cases, and compares more than one approach for each extension.
