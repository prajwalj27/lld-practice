# Blackjack: class design and relationships

## Class design

```
enum Suit:       SPADES, HEARTS, DIAMONDS, CLUBS
enum Rank:       TWO ... TEN, JACK, QUEEN, KING, ACE
                 + points -> int            (ace = 1; Hand decides when it's 11)
enum GameState:  BETTING, PLAYER_TURN
enum Outcome:    PLAYER_BLACKJACK, PLAYER_WIN, DEALER_WIN, PUSH

class Card:                  (frozen dataclass)
    - rank: Rank
    - suit: Suit

class Deck:
    - _cards: list[Card]
    + Deck(cards=None, rng=None)
    + draw() -> Card
    + __len__() -> int

class Hand:
    - _cards: list[Card]
    + add(card) -> None
    + cards -> tuple[Card, ...]        (property, read-only)
    + value -> int                     (property)
    + is_soft -> bool                  (property)
    + is_bust -> bool                  (property)
    + is_blackjack -> bool             (property)

class Participant:
    - _hand: Hand
    + hand -> Hand                     (property)
    + reset_hand() -> None

class Player(Participant):
    - name: str
    - _balance: int
    + balance -> int                   (property)
    + place_bet(amount) -> None
    + receive(amount) -> None

class Dealer(Participant):
    - STAND_ON = 17
    + should_hit() -> bool

class RoundResult:           (frozen dataclass)
    - outcome: Outcome
    - player_total: int
    - dealer_total: int
    - net_chips: int

class BlackjackGame:
    - _player: Player
    - _dealer: Dealer
    - _deck_factory: Callable[[], Deck]
    - _deck: Deck | None
    - _bet: int
    - _state: GameState
    + state, player, dealer            (properties)
    + dealer_visible_cards() -> tuple[Card, ...]
    + start_round(bet) -> RoundResult | None
    + hit() -> RoundResult | None
    + stand() -> RoundResult
    - _compare_hands() -> Outcome
    - _settle(outcome) -> RoundResult
    - _deal_to(participant) -> None
    - _require_state(expected, action) -> None
```

## Relationships

- **BlackjackGame has one Player, one Dealer, and one Deck per round.** It's the only class that moves cards between them.
- **Player and Dealer are both Participants (inheritance), and each has a Hand (composition).** The shared part, holding and resetting a hand, lives in the base class. Each subclass adds only what's different: chips for the player, the hit rule for the dealer.
- **A Deck and a Hand each hold many Cards.** Cards move from the deck into a hand through `_deal_to`.
- **The game returns a RoundResult** whenever a round ends. That can happen inside `start_round` (a blackjack), `hit` (a bust or 21), or `stand`.

## Flow of one round

```
start_round(bet)
  ├─ check state is BETTING, take the bet
  ├─ new deck, clear hands, deal P D P D
  ├─ any blackjack?  ── yes ──> _settle(...) ──> RoundResult, back to BETTING
  └─ no ──> state = PLAYER_TURN, return None

hit()                                   stand()
  ├─ check state is PLAYER_TURN           ├─ check state is PLAYER_TURN
  ├─ deal one card to the player          ├─ dealer draws while should_hit()
  ├─ bust?  ──> _settle(DEALER_WIN)       └─ _settle(_compare_hands())
  ├─ 21?    ──> stand()
  └─ else return None (still player's turn)
```

## Design decisions worth saying out loud

- **The ace rule lives in one place.** Count every ace as 1, then if the hand has an ace and adding 10 doesn't bust, count one ace as 11. Only one ace can ever be 11, since two would make 22. A hand that's using an ace as 11 is "soft".

- **The hand's value is computed, never stored.** A stored total could get out of sync with the cards. This is the same single-source-of-truth idea as the parking lot's occupied set.

- **An explicit state enum is justified here, unlike in the vending machine.** In the vending machine, the balance alone told you everything. Here the allowed actions depend on the phase: you can't hit before betting, or bet in the middle of a hand. One `_state` field plus `_require_state()` makes every illegal action fail with a clear error.

- **The dealer's card is hidden through the game, not the hand.** `dealer_visible_cards()` shows only the first card during the player's turn. Hand stays a plain container, and the game decides what each side can see.

- **The deck can be injected.** The game takes a `deck_factory` that defaults to a shuffled deck. The dry run passes stacked decks, so every round is reproducible. This is the same idea as passing the timestamp in the parking lot.

- **Every check runs before any change.** `place_bet` validates the amount before touching the balance, and every action checks the state first.

- **Chips are integers.** The 3:2 blackjack payout rounds down (`bet * 3 // 2`), so there are no floating-point chips.

- **Inheritance is used for what's shared, composition for what's held.** Player and Dealer *are* participants, and they *have* a hand. Making Hand a subclass of anything would be wrong.

- **Data class choices.** Card and RoundResult are frozen data classes, because they're fixed records. Hand, Deck, Player, and Dealer are regular classes, since they hold changing state behind methods.

## Complexity

- `Deck.draw()` is O(1). The list is stored reversed, so drawing pops from the end.
- `Hand.value` is O(cards in hand), which is at most about 11 for a single deck, so effectively constant.
- A whole round is O(cards dealt).
