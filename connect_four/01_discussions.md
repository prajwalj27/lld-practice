# Connect Four (new grad LLD): discussion

Prompt: two players take turns dropping discs into a 7-column, 6-row board. The first to line up four of their own discs vertically, horizontally, or diagonally wins.

## Clarifying questions

Cover four areas: the core action, error handling, scope, and future features.

1. **How does a player move?**
   Interviewer: They pick a column from 0 to 6, and the disc falls to the lowest empty spot.

2. **How can the game end?**
   Interviewer: Four in a row, in any direction, wins. A full board with no winner is a draw.

3. **What happens on a move into a full column?**
   Interviewer: Return false or raise an error. An invalid move must never corrupt the game state.

4. **What if a player moves out of turn?**
   Interviewer: Reject it the same way.

5. **One game at a time, or many at once?**
   Interviewer: One game.

6. **Backend only, or UI support too?**
   Interviewer: Backend only. This matters: with a UI you'd add methods for reading the board, but without one the API can stay small.

7. **Do we need move history or undo?**
   Interviewer: No.

8. **Is the board size configurable?**
   Interviewer: No, always 7 × 6.

## Requirements

```
requirements
1. two players take turns dropping discs into a 7-column, 6-row board
2. a disc falls to the lowest empty row in the chosen column
3. the game ends when:
    - a player has four in a row (vertical, horizontal, or diagonal) -> they win
    - the board is full -> draw
4. reject invalid moves clearly, without changing state:
    - column full (or out of bounds)
    - moving out of turn
    - moving after the game is over

out of scope
- ui
- concurrent games
- move history / undo
- configurable board size
```

## Entities

Look for nouns: game, board, player, disc, column, row. Give each class one clear job, and avoid both one giant class and needless splitting.

| Entity | Job |
|---|---|
| **Game** | The orchestrator. Holds the board and both players, tracks whose turn it is and the game state, enforces turn rules, and asks the board whether a move won. |
| **Board** | The 7 × 6 grid. Owns placement (where a disc lands, whether a column is full) and win detection. Knows nothing about turns or players. |
| **Player** | Pure data: a name and a disc color. No game logic. |
| **DiscColor, GameState** | Enums for RED / YELLOW and IN_PROGRESS / WON / DRAW. |

**Nouns that aren't entities:**

- **Disc.** A cell just holds a `DiscColor`; a disc has no behavior of its own.
- **Column and row.** Integers.
