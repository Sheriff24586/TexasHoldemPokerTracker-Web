import pytest

from poker_tracker.engine import Action, PokerGame, PokerRuleError, Street


def make_game(n=6, stack=100, sb=5, bb=10):
    players = [(i, f"P{i}", stack) for i in range(1, n + 1)]
    return PokerGame(players, sb, bb, dealer_seat=1)


def test_six_player_positions_and_blinds():
    g = make_game()
    g.start_hand()
    assert g.dealer_seat == 1
    assert g.small_blind_seat == 2
    assert g.big_blind_seat == 3
    assert g.pot == 15
    assert g.current_actor == 4


def test_heads_up_dealer_is_small_blind():
    g = PokerGame([(1, "A", 100), (2, "B", 100)], 5, 10, dealer_seat=1)
    g.start_hand()
    assert g.dealer_seat == 1
    assert g.small_blind_seat == 1
    assert g.big_blind_seat == 2
    assert g.current_actor == 1


def test_call_auto_amount_and_zero_actions():
    g = make_game()
    g.start_hand()
    assert g.call_amount(4) == 10
    rec = g.apply_action(4, Action.CALL, 10)
    assert rec.amount == 10
    assert g.player(4).stack == 90

    g.apply_action(5, Action.FOLD, 0)
    assert g.player(5).folded
    assert g.actions[-1].amount == 0


def test_check_amount_is_zero():
    g = PokerGame([(1, "A", 100), (2, "B", 100)], 5, 10, dealer_seat=1)
    g.start_hand()
    # Heads-up preflop: dealer/SB acts first and must call to match BB.
    g.apply_action(1, Action.CALL, 5)
    g.apply_action(2, Action.CHECK, 0)
    # Flop: BB is first postflop.
    assert g.street == Street.FLOP
    assert g.current_actor == 2
    g.apply_action(2, Action.CHECK, 0)
    assert g.actions[-1].amount == 0


def test_raise_to_updates_minimum_raise():
    g = make_game()
    g.start_hand()
    g.apply_action(4, Action.RAISE, 30)
    assert g.current_bet == 30
    assert g.min_raise_size == 10
    assert g.call_amount(5) == 30
    g.apply_action(5, Action.CALL, 30)


def test_all_in_is_entire_remaining_stack():
    g = PokerGame([(1, "A", 100), (2, "B", 25)], 5, 10, dealer_seat=1)
    g.start_hand()
    # Heads-up: A is SB and has 95 left; B is BB and has 15 left.
    assert g.player(2).stack == 15
    g.apply_action(1, Action.CALL, 5)
    g.apply_action(2, Action.ALL_IN, 15)
    assert g.player(2).stack == 0
    assert g.player(2).all_in


def test_pot_and_chip_conservation_before_settlement():
    g = make_game()
    initial = g.chip_total()
    g.start_hand()
    g.apply_action(4, Action.RAISE, 30)
    g.apply_action(5, Action.CALL, 30)
    g.apply_action(6, Action.CALL, 30)
    g.apply_action(1, Action.CALL, 30)
    g.apply_action(2, Action.CALL, 25)
    g.apply_action(3, Action.CALL, 20)
    assert g.pot == 180
    assert g.chip_total() == initial


def test_folded_short_contributor_does_not_create_side_pot():
    g = PokerGame(
        [(1, "A", 100), (2, "B", 100), (3, "C", 100),
         (4, "D", 100), (5, "E", 100), (6, "F", 100)],
        5, 10, dealer_seat=1
    )
    g.start_hand()

    # Exact structure from the discovered bug:
    # five live players contributed 80 each; one player folded after 30.
    contributions = {1: 80, 2: 80, 3: 80, 4: 80, 5: 30, 6: 80}
    for seat, amount in contributions.items():
        p = g.player(seat)
        p.total_contribution = amount
        p.stack = 100 - amount
    g.player(5).folded = True

    pots = g.pots()

    assert len(pots) == 1
    assert pots[0].label == "Main Pot"
    assert pots[0].amount == 430
    assert pots[0].eligible_seats == [1, 2, 3, 4, 6]


def test_side_pots_and_split_settlement():
    g = PokerGame(
        [(1, "A", 100), (2, "B", 200), (3, "C", 300), (4, "D", 300)],
        5, 10, dealer_seat=1
    )
    g.start_hand()
    # Construct contributions directly to test the pure pot algorithm.
    g.player(1).total_contribution = 100
    g.player(2).total_contribution = 200
    g.player(3).total_contribution = 300
    g.player(4).total_contribution = 300
    g.player(1).all_in = True
    g.player(2).all_in = True
    g.player(3).folded = True
    pots = g.pots()
    assert [p.amount for p in pots] == [400, 300, 200]
    assert pots[0].eligible_seats == [1, 2, 4]
    assert pots[1].eligible_seats == [2, 4]
    assert pots[2].eligible_seats == [4]


def test_dealer_skips_busted_player():
    g = make_game(4)
    g.start_hand()
    # Simulate completed hand where seat 2 is busted.
    g.hand_status = "COMPLETED"
    g.player(2).stack = 0
    g.player(3).stack = 100
    g.player(4).stack = 100
    g.dealer_seat = 1
    g.start_hand()
    assert g.dealer_seat == 3


def test_cannot_check_when_facing_bet():
    g = make_game()
    g.start_hand()
    with pytest.raises(PokerRuleError):
        g.apply_action(4, Action.CHECK, 0)


def test_settlement_awards_pot_and_preserves_chips():
    g = PokerGame([(1, "A", 100), (2, "B", 100)], 5, 10, dealer_seat=1)
    initial = g.chip_total()
    g.start_hand()
    g.apply_action(1, Action.CALL, 5)
    g.apply_action(2, Action.CHECK, 0)
    for seat in (2, 1):
        g.apply_action(seat, Action.CHECK, 0)
    for seat in (2, 1):
        g.apply_action(seat, Action.CHECK, 0)
    for seat in (2, 1):
        g.apply_action(seat, Action.CHECK, 0)
    assert g.hand_status == "AWAITING_SETTLEMENT"
    pot = g.pot
    payouts = g.settle({0: [1]})
    assert payouts[1] == pot
    assert g.player(1).stack + g.player(2).stack == initial
    assert g.hand_status == "COMPLETED"
    assert g.pot == 0


def test_folded_player_cannot_win_pot():
    g = PokerGame([(1, "A", 100), (2, "B", 100)], 5, 10, dealer_seat=1)
    g.start_hand()
    g.apply_action(1, Action.FOLD, 0)
    assert g.hand_status == "AWAITING_SETTLEMENT"
    with pytest.raises(PokerRuleError):
        g.settle({0: [1]})


def test_full_six_player_preflop_sequence_matches_original_tracker():
    g = PokerGame([(i, f"P{i}", 100) for i in range(1, 7)], 5, 10, dealer_seat=1)
    initial = g.chip_total()
    g.start_hand()
    assert (g.dealer_seat, g.small_blind_seat, g.big_blind_seat) == (1, 2, 3)

    g.apply_action(4, Action.RAISE, 30)
    g.apply_action(5, Action.CALL, 30)
    g.apply_action(6, Action.CALL, 30)
    g.apply_action(1, Action.CALL, 30)
    g.apply_action(2, Action.CALL, 25)
    g.apply_action(3, Action.CALL, 20)

    assert g.pot == 180
    assert all(g.player(i).total_contribution == 30 for i in range(1, 7))
    assert all(g.player(i).stack == 70 for i in range(1, 7))
    assert g.chip_total() == initial
    assert g.street == Street.FLOP
    assert g.current_actor == 2


def test_next_hand_rotates_dealer_and_skips_zero_stack():
    g = PokerGame([(1, "A", 100), (2, "B", 100), (3, "C", 100), (4, "D", 100)], 5, 10, dealer_seat=1)
    g.start_hand()
    # Force a completed hand state and make seat 2 bust.
    g.hand_status = "COMPLETED"
    g.player(2).stack = 0
    g.dealer_seat = 1
    g.start_hand()
    assert g.dealer_seat == 3
    assert g.small_blind_seat == 4
    assert g.big_blind_seat == 1
