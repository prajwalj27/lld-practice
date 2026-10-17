"""Blackjack: one player vs the dealer (requires Python 3.10+)."""

import random
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


# ---------- Enums ----------

class Suit(Enum):
    SPADES = "♠"
    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"


class Rank(Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"

    @property
    def points(self) -> int:
        """Base points: number cards = face value, J/Q/K = 10, ace = 1.
        Hand decides whether one ace is worth 11 instead."""
        if self is Rank.ACE:
            return 1
        if self in (Rank.JACK, Rank.QUEEN, Rank.KING):
            return 10
        return int(self.value)


class GameState(Enum):
    BETTING = "betting"          # waiting for start_round(bet)
    PLAYER_TURN = "player_turn"  # waiting for hit() or stand()


class Outcome(Enum):
    PLAYER_BLACKJACK = "player_blackjack"
    PLAYER_WIN = "player_win"
    DEALER_WIN = "dealer_win"
    PUSH = "push"


# ---------- Exceptions ----------

class BlackjackError(Exception):
    """Base error for the game."""


class InvalidActionError(BlackjackError):
    """Raised when an action isn't allowed in the current game state."""


class InsufficientChipsError(BlackjackError):
    """Raised when a bet is larger than the player's balance."""


class EmptyDeckError(BlackjackError):
    """Raised when drawing from an empty deck."""


# ---------- Cards ----------

@dataclass(frozen=True)
class Card:
    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.value}{self.suit.value}"


class Deck:
    def __init__(self, cards: list[Card] | None = None, rng: random.Random | None = None) -> None:
        """
        Core logic:
        - No cards given: build a standard 52-card deck and shuffle it
        - Cards given: use them in that exact order, first card on top
          (lets the dry run and tests control every deal)

        Edge cases:
        - rng lets a test shuffle the same way every time
        """
        if cards is None:
            cards = [Card(rank, suit) for suit in Suit for rank in Rank]
            (rng or random.Random()).shuffle(cards)
        # Stored reversed so draw() can pop from the end in O(1).
        self._cards = list(reversed(cards))

    def draw(self) -> Card:
        """
        Core logic:
        - Remove and return the top card

        Edge cases:
        - Empty deck -> EmptyDeckError
        """
        if not self._cards:
            raise EmptyDeckError("The deck is empty")
        return self._cards.pop()

    def __len__(self) -> int:
        return len(self._cards)


class Hand:
    def __init__(self) -> None:
        self._cards: list[Card] = []

    def add(self, card: Card) -> None:
        self._cards.append(card)

    @property
    def cards(self) -> tuple[Card, ...]:
        # A tuple, so callers can look but can't change the hand.
        return tuple(self._cards)

    @property
    def value(self) -> int:
        """
        Core logic:
        - Count every ace as 1 and add up all cards
        - If there's an ace and adding 10 doesn't bust, count one ace as 11

        Edge cases:
        - Only one ace can ever be 11 (two would be 22, a bust)
        - A A -> 12, A K -> 21, A 5 K -> 16 (the ace drops back to 1)
        """
        return self._totals()[0]

    @property
    def is_soft(self) -> bool:
        """True if an ace is currently counted as 11."""
        return self._totals()[1]

    @property
    def is_bust(self) -> bool:
        return self.value > 21

    @property
    def is_blackjack(self) -> bool:
        """21 with exactly two cards. A three-card 21 is not a blackjack."""
        return len(self._cards) == 2 and self.value == 21

    def _totals(self) -> tuple[int, bool]:
        hard_total = sum(card.rank.points for card in self._cards)
        has_ace = any(card.rank is Rank.ACE for card in self._cards)
        if has_ace and hard_total + 10 <= 21:
            return hard_total + 10, True
        return hard_total, False

    def __str__(self) -> str:
        return " ".join(str(card) for card in self._cards)


# ---------- Participants ----------

class Participant:
    """Anyone who holds a hand: the player or the dealer."""

    def __init__(self) -> None:
        self._hand = Hand()

    @property
    def hand(self) -> Hand:
        return self._hand

    def reset_hand(self) -> None:
        self._hand = Hand()


class Player(Participant):
    def __init__(self, name: str, balance: int) -> None:
        """
        Edge cases:
        - Empty name -> ValueError
        - Negative balance -> ValueError
        """
        super().__init__()
        if not name:
            raise ValueError("Name cannot be empty")
        if balance < 0:
            raise ValueError("Balance cannot be negative")
        self.name = name
        self._balance = balance

    @property
    def balance(self) -> int:
        return self._balance

    def place_bet(self, amount: int) -> None:
        """
        Core logic:
        - Take the bet out of the balance

        Edge cases:
        - Zero or negative bet -> ValueError
        - Bet larger than the balance -> InsufficientChipsError
        - Both checks happen before the balance changes
        """
        if amount <= 0:
            raise ValueError("Bet must be positive")
        if amount > self._balance:
            raise InsufficientChipsError(
                f"Bet {amount} is more than the balance {self._balance}"
            )
        self._balance -= amount

    def receive(self, amount: int) -> None:
        """
        Edge cases:
        - Negative amount -> ValueError (receiving 0 after a loss is fine)
        """
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        self._balance += amount


class Dealer(Participant):
    STAND_ON = 17

    def should_hit(self) -> bool:
        """
        Core logic:
        - Hit below 17, stand on 17 or more

        Edge cases:
        - Soft 17 (e.g. A 6): the dealer stands, by this table's rule
        """
        return self.hand.value < self.STAND_ON


# ---------- Result ----------

@dataclass(frozen=True)
class RoundResult:
    outcome: Outcome
    player_total: int
    dealer_total: int
    net_chips: int  # positive = player gained, negative = player lost


# ---------- Game (orchestrator) ----------

class BlackjackGame:
    def __init__(self, player: Player, deck_factory: Callable[[], Deck] = Deck) -> None:
        """
        Core logic:
        - Hold the player, a dealer, and a way to get a fresh deck each round
        - deck_factory defaults to a shuffled 52-card Deck; a test or dry run
          can pass one that returns stacked decks instead
        """
        self._player = player
        self._dealer = Dealer()
        self._deck_factory = deck_factory
        self._deck: Deck | None = None
        self._bet = 0
        self._state = GameState.BETTING

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def player(self) -> Player:
        return self._player

    @property
    def dealer(self) -> Dealer:
        return self._dealer

    def dealer_visible_cards(self) -> tuple[Card, ...]:
        """
        Core logic:
        - During the player's turn, only the dealer's first card is face up
        - Otherwise, all of the dealer's cards are visible
        """
        cards = self._dealer.hand.cards
        if self._state is GameState.PLAYER_TURN:
            return cards[:1]
        return cards

    def start_round(self, bet: int) -> RoundResult | None:
        """
        Core logic:
        - Take the bet from the player
        - Get a fresh deck and clear both hands
        - Deal 2 cards each, alternating: player, dealer, player, dealer
        - Check for blackjacks; if there is one, the round ends right away
        - Otherwise it's the player's turn (returns None)

        Edge cases:
        - Called in the middle of a round -> InvalidActionError
        - Bet <= 0 -> ValueError; bet > balance -> InsufficientChipsError
          (both raised before anything changes)
        - Both have blackjack -> PUSH
        - Only the player has blackjack -> pays 3:2
        - Only the dealer has blackjack -> player loses, no chance to hit
        """
        self._require_state(GameState.BETTING, "start a round")
        self._player.place_bet(bet)
        self._bet = bet

        self._deck = self._deck_factory()
        self._player.reset_hand()
        self._dealer.reset_hand()
        for _ in range(2):
            self._deal_to(self._player)
            self._deal_to(self._dealer)

        player_blackjack = self._player.hand.is_blackjack
        dealer_blackjack = self._dealer.hand.is_blackjack
        if player_blackjack and dealer_blackjack:
            return self._settle(Outcome.PUSH)
        if player_blackjack:
            return self._settle(Outcome.PLAYER_BLACKJACK)
        if dealer_blackjack:
            return self._settle(Outcome.DEALER_WIN)

        self._state = GameState.PLAYER_TURN
        return None

    def hit(self) -> RoundResult | None:
        """
        Core logic:
        - Deal one card to the player
        - Bust -> the round ends and the player loses
          (the dealer doesn't need to play)
        - Exactly 21 -> stand automatically, since hitting again can't help
        - Otherwise it's still the player's turn (returns None)

        Edge cases:
        - Not the player's turn -> InvalidActionError
        """
        self._require_state(GameState.PLAYER_TURN, "hit")
        self._deal_to(self._player)

        if self._player.hand.is_bust:
            return self._settle(Outcome.DEALER_WIN)
        if self._player.hand.value == 21:
            return self.stand()
        return None

    def stand(self) -> RoundResult:
        """
        Core logic:
        - End the player's turn
        - The dealer draws until their rule says stop
        - Compare totals and settle the bet

        Edge cases:
        - Not the player's turn -> InvalidActionError
        - Dealer busts -> player wins
        - Equal totals -> PUSH
        """
        self._require_state(GameState.PLAYER_TURN, "stand")
        while self._dealer.should_hit():
            self._deal_to(self._dealer)
        return self._settle(self._compare_hands())

    def _compare_hands(self) -> Outcome:
        player_total = self._player.hand.value
        dealer_total = self._dealer.hand.value
        if self._dealer.hand.is_bust or player_total > dealer_total:
            return Outcome.PLAYER_WIN
        if player_total < dealer_total:
            return Outcome.DEALER_WIN
        return Outcome.PUSH

    def _settle(self, outcome: Outcome) -> RoundResult:
        """
        Core logic:
        - Work out the chips going back to the player:
          blackjack = bet + 1.5x bet, win = 2x bet, push = bet back, loss = 0
        - Pay the player and get ready for the next round

        Edge cases:
        - 3:2 on an odd bet rounds down (bet 5 -> wins 7)
        """
        payout = {
            Outcome.PLAYER_BLACKJACK: self._bet + self._bet * 3 // 2,
            Outcome.PLAYER_WIN: self._bet * 2,
            Outcome.PUSH: self._bet,
            Outcome.DEALER_WIN: 0,
        }[outcome]
        self._player.receive(payout)

        result = RoundResult(
            outcome=outcome,
            player_total=self._player.hand.value,
            dealer_total=self._dealer.hand.value,
            net_chips=payout - self._bet,
        )
        self._bet = 0
        self._state = GameState.BETTING
        return result

    def _deal_to(self, participant: Participant) -> None:
        participant.hand.add(self._deck.draw())

    def _require_state(self, expected: GameState, action: str) -> None:
        if self._state is not expected:
            raise InvalidActionError(
                f"Cannot {action} during {self._state.value}"
            )
