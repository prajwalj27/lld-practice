"""Connect Four: two players on a 7-column, 6-row board (requires Python 3.10+)."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


# ---------- Enums ----------

class DiscColor(Enum):
    RED = "R"
    YELLOW = "Y"


class GameState(Enum):
    IN_PROGRESS = "in_progress"
    WON = "won"
    DRAW = "draw"


# ---------- Player ----------

@dataclass(frozen=True)
class Player:
    # Pure data: identity + disc color. No game logic lives here.
    name: str
    color: DiscColor

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Player name cannot be empty")


# ---------- Board ----------

class Board:
    """Owns the grid and every grid rule: bounds, falling discs, full, four in a row.
    Row 0 is the top row; row ROWS - 1 is the bottom."""

    ROWS: ClassVar[int] = 6
    COLS: ClassVar[int] = 7
    WIN_LENGTH: ClassVar[int] = 4
    # (row step, col step): horizontal, vertical, diagonal down-right, diagonal up-right.
    # Each is also scanned in the opposite direction, so 4 vectors cover all 8 ways.
    DIRECTIONS: ClassVar[tuple[tuple[int, int], ...]] = ((0, 1), (1, 0), (1, 1), (-1, 1))

    def __init__(self) -> None:
        # One new list per row. [[None] * COLS] * ROWS would make every row the SAME list.
        self._grid: list[list[DiscColor | None]] = [
            [None] * self.COLS for _ in range(self.ROWS)
        ]

    @property
    def rows(self) -> int:
        return self.ROWS

    @property
    def cols(self) -> int:
        return self.COLS

    def cell(self, row: int, col: int) -> DiscColor | None:
        """
        Core logic:
        - Return the disc at (row, col), or None if the cell is empty

        Edge cases:
        - Out of bounds -> IndexError (a caller bug, not a game move)
        """
        if not self._in_bounds(row, col):
            raise IndexError(f"Cell ({row}, {col}) is off the board")
        return self._grid[row][col]

    def can_place(self, column: int) -> bool:
        """
        Core logic:
        - A column has space if its top cell is empty

        Edge cases:
        - Column out of bounds -> False
        """
        return 0 <= column < self.COLS and self._grid[0][column] is None

    def place_disc(self, column: int, color: DiscColor) -> int | None:
        """
        Core logic:
        - Scan from the bottom row upward to the first empty cell
        - Put the disc there and return its row, so Game can pass
          (row, column) straight into check_win without re-scanning

        Edge cases:
        - Column out of bounds -> None
        - Column full -> None
        - All grid validation lives here, so Game only checks for None
        """
        if not self.can_place(column):
            return None
        for row in range(self.ROWS - 1, -1, -1):
            if self._grid[row][column] is None:
                self._grid[row][column] = color
                return row
        return None  # unreachable: can_place guaranteed space

    def is_full(self) -> bool:
        """The board is full when no column can take another disc."""
        return not any(self.can_place(col) for col in range(self.COLS))

    def check_win(self, row: int, col: int, color: DiscColor) -> bool:
        """
        Core logic:
        - Only the last disc placed can create a new win, so scan from it
        - For each direction, count matching discs forward and backward
          from (row, col), plus the disc itself
        - Any direction reaching 4 -> win

        Edge cases:
        - (row, col) out of bounds -> False
        - Cell doesn't hold this color -> False
        - Five or more in a row still counts (>= 4, not == 4)
        """
        if not self._in_bounds(row, col) or self._grid[row][col] is not color:
            return False
        for dr, dc in self.DIRECTIONS:
            count = (
                1
                + self._count_in_direction(row, col, dr, dc, color)
                + self._count_in_direction(row, col, -dr, -dc, color)
            )
            if count >= self.WIN_LENGTH:
                return True
        return False

    def _count_in_direction(self, row: int, col: int, dr: int, dc: int, color: DiscColor) -> int:
        """Count consecutive discs of this color starting one step away from (row, col)."""
        count = 0
        r, c = row + dr, col + dc
        while self._in_bounds(r, c) and self._grid[r][c] is color:
            count += 1
            r += dr
            c += dc
        return count

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.ROWS and 0 <= col < self.COLS


# ---------- Game (orchestrator) ----------

class Game:
    def __init__(self, player1: Player, player2: Player) -> None:
        """
        Core logic:
        - New empty board, player1 moves first, game in progress, no winner

        Edge cases:
        - Both players share a color -> ValueError (discs couldn't be told apart)
        """
        if player1.color is player2.color:
            raise ValueError("Players must use different colors")
        self._board = Board()
        self._player1 = player1
        self._player2 = player2
        self._current_player = player1
        self._state = GameState.IN_PROGRESS
        self._winner: Player | None = None  # None while playing, and in a draw

    @property
    def board(self) -> Board:
        return self._board

    @property
    def current_player(self) -> Player:
        return self._current_player

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def winner(self) -> Player | None:
        return self._winner

    def make_move(self, player: Player, column: int) -> bool:
        """
        The only method that changes game state.

        Core logic:
        - Drop the disc (Board returns the row it landed in)
        - That move wins -> state WON, record the winner
        - Else board full -> state DRAW
        - Else switch turns
        - Return True

        Edge cases (all rejected with False, before anything changes):
        - Game already over (WON or DRAW)
        - Not this player's turn
        - Column out of bounds or full (Board decides; returns None)
        """
        if self._state is not GameState.IN_PROGRESS:
            return False
        if player != self._current_player:
            return False

        row = self._board.place_disc(column, player.color)
        if row is None:
            return False

        if self._board.check_win(row, column, player.color):
            self._state = GameState.WON
            self._winner = player
        elif self._board.is_full():
            self._state = GameState.DRAW
        else:
            self._current_player = self._other(player)
        return True

    def _other(self, player: Player) -> Player:
        return self._player2 if player == self._player1 else self._player1
