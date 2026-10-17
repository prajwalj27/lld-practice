"""Dry run for the blackjack game. Run: python main.py"""

from implementation import (
    BlackjackError,
    BlackjackGame,
    Card,
    Deck,
    GameState,
    Player,
    Rank,
    RoundResult,
    Suit,
)

SUIT_BY_LETTER = {suit.name[0]: suit for suit in Suit}  # S, H, D, C


def deck_of(*codes: str) -> Deck:
    """Build a stacked deck from codes like "AS", "10H", "KD" (first = top).
    Deal order: player, dealer, player, dealer, then any hits."""
    cards = [Card(Rank(code[:-1]), SUIT_BY_LETTER[code[-1]]) for code in codes]
    return Deck(cards)


def table_view(game: BlackjackGame) -> str:
    player_hand = game.player.hand
    dealer_cards = " ".join(str(card) for card in game.dealer_visible_cards())
    if game.state is GameState.PLAYER_TURN:
        dealer_cards += " ??"
    soft = " soft" if player_hand.is_soft else ""
    return f"Player: {player_hand} ({player_hand.value}{soft}) | Dealer shows: {dealer_cards}"


def show_result(game: BlackjackGame, result: RoundResult) -> None:
    player_hand = game.player.hand
    dealer_hand = game.dealer.hand
    print(f"Final -> Player: {player_hand} ({player_hand.value}) "
          f"| Dealer: {dealer_hand} ({dealer_hand.value})")
    sign = "+" if result.net_chips > 0 else ""
    print(
        f"Result: {result.outcome.name} | net {sign}{result.net_chips} "
        f"| balance {game.player.balance}"
    )


def main() -> None:
    upcoming_decks: list[Deck] = []
    player = Player("Prajwal", balance=1000)
    game = BlackjackGame(player, deck_factory=lambda: upcoming_decks.pop(0))

    def play_round(title: str, codes: list[str], bet: int, actions: list[str]) -> None:
        print(f"\n=== {title} ===")
        print(f"Bet: {bet}")
        upcoming_decks.append(deck_of(*codes))

        result = game.start_round(bet)
        if game.state is GameState.PLAYER_TURN:
            print(table_view(game))

        for action in actions:
            if result is not None:
                break
            print(f"> {action}")
            result = game.hit() if action == "hit" else game.stand()
            if game.state is GameState.PLAYER_TURN:
                print(table_view(game))

        show_result(game, result)

    print(f"{player.name} starts with {player.balance} chips")

    play_round("Round 1: player stands, dealer busts",
               ["10H", "9S", "8C", "7D", "10C"], 100, ["stand"])

    play_round("Round 2: player hits and busts",
               ["10S", "9H", "6D", "8C", "KH"], 50, ["hit"])

    play_round("Round 3: player blackjack pays 3:2",
               ["AS", "9C", "KD", "7H"], 100, [])

    play_round("Round 4: soft hand, the ace drops from 11 to 1",
               ["AH", "10D", "6S", "7C", "9S", "2C"], 100, ["hit", "hit", "stand"])

    play_round("Round 5: equal totals push",
               ["10C", "10S", "9D", "9H"], 100, ["stand"])

    play_round("Round 6: dealer blackjack, player never gets a turn",
               ["10H", "AS", "9C", "KC"], 100, [])

    play_round("Round 7: dealer stands on soft 17",
               ["10D", "6H", "8S", "AC"], 100, ["stand"])

    play_round("Round 8: hitting to exactly 21 stands automatically",
               ["5S", "10H", "6D", "8C", "QH"], 100, ["hit"])

    print("\n=== Invalid actions ===")
    attempts = [
        ("hit before a round starts", lambda: game.hit()),
        ("bet 0", lambda: game.start_round(0)),
        ("bet more than the balance", lambda: game.start_round(10_000)),
    ]
    for label, attempt in attempts:
        try:
            attempt()
        except (BlackjackError, ValueError) as error:
            print(f"{label}: {error}")

    print(f"\nFinal balance: {player.balance}")


if __name__ == "__main__":
    main()
