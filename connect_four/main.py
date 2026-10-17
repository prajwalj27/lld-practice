"""Dry run for Connect Four. Run: python main.py"""

from implementation import Board, DiscColor, Game, GameState, Player


def render(board: Board) -> str:
    """Rendering is out of scope for the game itself, so it lives in the runner."""
    lines = []
    for row in range(board.rows):
        cells = [board.cell(row, col) for col in range(board.cols)]
        lines.append(" ".join(cell.value if cell else "." for cell in cells))
    lines.append(" ".join(str(col) for col in range(board.cols)))
    return "\n".join(lines)


def status(game: Game) -> str:
    if game.state is GameState.WON:
        return f"WON by {game.winner.name}"
    if game.state is GameState.DRAW:
        return "DRAW"
    return f"in progress, {game.current_player.name} to move"


def new_game() -> tuple[Game, Player, Player]:
    alice = Player("Alice", DiscColor.RED)
    bob = Player("Bob", DiscColor.YELLOW)
    return Game(alice, bob), alice, bob


def play(title: str, columns: list[int]) -> Game:
    """Each column is played by whoever's turn it is."""
    print(f"\n=== {title} ===")
    game, _, _ = new_game()
    for col in columns:
        game.make_move(game.current_player, col)
    print(render(game.board))
    print("State:", status(game))
    return game


def main() -> None:
    play("Vertical win (Alice stacks column 0)", [0, 1, 0, 1, 0, 1, 0])
    play("Horizontal win (Alice fills the bottom row)", [0, 0, 1, 1, 2, 2, 3])
    play("Diagonal win (Alice, bottom-left up to the right)",
         [0, 1, 1, 2, 2, 3, 2, 3, 3, 5, 3])
    play("Draw (board full, no four in a row)",
         [int(c) for c in "330254564223355224331121550404466660106011"])

    print("\n=== Rejected moves (nothing changes) ===")
    game, alice, bob = new_game()
    print("Bob moves first (out of turn):", game.make_move(bob, 3))
    print("Column -1:", game.make_move(alice, -1))
    print("Column 7:", game.make_move(alice, 7))

    for _ in range(6):  # fill column 0, alternating colors, so nobody wins
        game.make_move(game.current_player, 0)
    print("Column 0 after it's full:", game.make_move(game.current_player, 0))
    print("Still", status(game))

    finished = play("Move after the game is over", [0, 1, 0, 1, 0, 1, 0])
    # A new Player object with the same fields equals the game's Bob (frozen
    # dataclass equality), but the move is still rejected: the game is over.
    print("Bob tries column 1:", finished.make_move(Player("Bob", DiscColor.YELLOW), 1))


if __name__ == "__main__":
    main()
