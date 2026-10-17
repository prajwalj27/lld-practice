# Blackjack (new grad LLD): discussion

## Clarifying questions

1. **How many players?**
   Interviewer: One player against the dealer. Multiple players can be a follow-up.

2. **How many decks, and when is it shuffled?**
   Interviewer: One standard 52-card deck. Use a freshly shuffled deck for every round.

3. **What are the card values?**
   Interviewer: 2 to 10 are worth their number. Jack, queen, and king are worth 10. An ace is worth 1 or 11, whichever is better for the hand without going over 21.

4. **What can the player do on their turn?**
   Interviewer: Hit or stand. Double down, split, insurance, and surrender are out of scope.

5. **What are the dealer's rules?**
   Interviewer: The dealer hits below 17 and stands on 17 or more, including a soft 17 (like ace-6).

6. **How does the deal work? Is a dealer card hidden?**
   Interviewer: Two cards each, alternating: player, dealer, player, dealer. The dealer's second card stays face down until the player's turn is over.

7. **What's a blackjack, and when is it checked?**
   Interviewer: 21 with exactly two cards. Check right after the deal. If either side has one, the round ends immediately.

8. **What if both have blackjack?**
   Interviewer: It's a push, and the bet is returned.

9. **Is there betting? What are the payouts?**
   Interviewer: Yes. The player starts with chips and bets before each round. A win pays 1:1, a blackjack pays 3:2, and a push returns the bet.

10. **How do we handle 3:2 on an odd bet?**
    Interviewer: Whole chips only, so round down. A bet of 5 wins 7.

11. **What happens when the player busts?**
    Interviewer: The player loses straight away, and the dealer doesn't need to play.

12. **Should the player be able to hit after reaching 21?**
    Interviewer: No. Stand for them automatically.

13. **How are rounds compared at the end?**
    Interviewer: If the dealer busts, the player wins. Otherwise the higher total wins, and equal totals are a push.

14. **How does the player choose actions? Is there a UI?**
    Interviewer: Through method calls like `hit()` and `stand()`. Any UI is out of scope.

15. **What's out of scope?**
    Interviewer: Split, double down, insurance, surrender, multiple players, multiple decks, a UI, saving game history, and card counting.

## Requirements

```
requirements
1. one player vs the dealer, one 52-card deck, freshly shuffled each round
2. card values: 2-10 face value, J/Q/K = 10, ace = 1 or 11 (best value without busting)
3. round flow:
    - player bets first: bet must be positive and <= balance
    - deal 2 cards each, alternating player / dealer; dealer's 2nd card hidden
    - check blackjacks right after the deal:
        - both -> push
        - player only -> player wins 3:2
        - dealer only -> player loses
    - player turn: hit or stand
        - bust (> 21) -> player loses immediately
        - exactly 21 -> stand automatically
    - dealer turn: hit below 17, stand on 17+ (including soft 17)
    - compare: dealer bust or higher player total -> win; lower -> loss; equal -> push
4. payouts: win 1:1, blackjack 3:2 (rounded down), push returns the bet, loss returns nothing
5. reject actions at the wrong time (e.g. hit before betting, bet mid-round)

out of scope
- split, double down, insurance, surrender
- multiple players, multiple decks
- ui, persistence, card counting
```

## Entities

The nouns are card, rank, suit, deck, hand, player, dealer, chips, bet, round, game, outcome, and result.

- **Card.** Pure data: a rank and a suit, which never change. A frozen data class.
- **Rank and Suit.** Fixed sets of values, so they're enums. Rank also knows each card's base points.
- **Deck.** Holds the cards still to be dealt. It builds and shuffles a standard deck and deals from the top.
- **Hand.** The cards one participant holds. It has real behavior: working out the total, handling aces, and checking for bust or blackjack.
- **Player.** Holds a hand plus a chip balance. Places bets and receives payouts.
- **Dealer.** Holds a hand plus the fixed hit/stand rule.
- **BlackjackGame.** The orchestrator. It runs the round, enforces whose turn it is, and settles the bet.
- **GameState.** The phase of the round: betting, or the player's turn. It decides which actions are allowed.
- **Outcome and RoundResult.** How the round ended (player blackjack, player win, dealer win, push) and a small frozen summary returned to the caller.

**Nouns that aren't entities:**

- **Chips and bet.** Integers: the balance lives on the player, and the current bet on the game.
- **Round.** A round is a phase the game moves through, not a separate object. A separate Round class only becomes worth it with multiple players or splits.
- **Points.** These are computed from the cards when needed, never stored.
