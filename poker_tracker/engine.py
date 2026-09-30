from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence


class Street(str, Enum):
    PREFLOP = "Preflop"
    FLOP = "Flop"
    TURN = "Turn"
    RIVER = "River"


class Action(str, Enum):
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    RAISE = "RAISE"
    ALL_IN = "ALL IN"


STREETS = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]


@dataclass
class PlayerState:
    seat: int
    name: str
    stack: int
    starting_stack: int = 0
    folded: bool = False
    all_in: bool = False
    total_contribution: int = 0
    street_contribution: int = 0

    def __post_init__(self):
        if self.starting_stack == 0:
            self.starting_stack = self.stack

    @property
    def in_hand(self) -> bool:
        return not self.folded and (self.total_contribution > 0 or self.stack > 0)

    @property
    def can_act(self) -> bool:
        return not self.folded and not self.all_in and self.stack > 0


@dataclass
class ActionRecord:
    sequence: int
    hand_number: int
    street: Street
    seat: int
    player: str
    action: Action
    amount: int
    call_amount: int
    street_contribution_after: int
    total_contribution_after: int


@dataclass
class Pot:
    amount: int
    eligible_seats: List[int]
    label: str


class PokerRuleError(ValueError):
    pass
class GameHistory:
    """Snapshot-based undo/redo history for the poker game."""

    def __init__(self):
        self._undo = []
        self._redo = []

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    def reset(self):
        self._undo.clear()
        self._redo.clear()

    def push(self, snapshot):
        """Store the state before a successful new action."""
        self._undo.append(snapshot)
        self._redo.clear()

    def undo(self, current_snapshot):
        if not self._undo:
            return None

        self._redo.append(current_snapshot)
        return self._undo.pop()

    def redo(self, current_snapshot):
        if not self._redo:
            return None

        self._undo.append(current_snapshot)
        return self._redo.pop()


class PokerGame:
    """Pure Python Texas Hold'em betting/stack engine.

    Card evaluation is intentionally outside this tracker iteration: winners are
    selected manually at settlement, while all betting, pots, bankrolls,
    positions, and action legality are handled by the engine.
    """

    def __init__(
        self,
        players: Sequence[tuple[int, str, int]],
        small_blind: int,
        big_blind: int,
        dealer_seat: Optional[int] = None,
    ):
        if not 2 <= len(players) <= 10:
            raise PokerRuleError("Texas Hold'em tracker supports 2-10 players.")
        if small_blind <= 0 or big_blind <= 0 or small_blind > big_blind:
            raise PokerRuleError("Blinds must be positive and SB <= BB.")

        self.small_blind = int(small_blind)
        self.big_blind = int(big_blind)
        self.players: Dict[int, PlayerState] = {
            seat: PlayerState(seat, name, int(stack))
            for seat, name, stack in players
        }
        self.seat_order = sorted(self.players)
        self.configured_dealer_seat = dealer_seat

        self.hand_number = 0
        self.street = Street.PREFLOP
        self.current_bet = 0
        self.min_raise_size = self.big_blind
        self.current_actor: Optional[int] = None
        self.dealer_seat: Optional[int] = None
        self.small_blind_seat: Optional[int] = None
        self.big_blind_seat: Optional[int] = None
        self.hand_status = "NOT_STARTED"
        self.acted: set[int] = set()
        self.actions: List[ActionRecord] = []
        self.last_action: Optional[ActionRecord] = None

    # ---------- Basic state ----------

    @property
    def pot(self) -> int:
        # A completed hand has no live pot: settlement has returned the chips
        # to player stacks. Keep total_contribution for history/audit.
        if self.hand_status == "COMPLETED":
            return 0
        return sum(p.total_contribution for p in self.players.values())

    @property
    def live_players(self) -> List[PlayerState]:
        return [p for p in self.players.values() if not p.folded and (p.total_contribution > 0 or p.stack > 0)]

    @property
    def players_with_chips(self) -> List[PlayerState]:
        return [p for p in self.players.values() if p.stack > 0]

    def player(self, seat: int) -> PlayerState:
        try:
            return self.players[seat]
        except KeyError:
            raise PokerRuleError(f"Unknown seat {seat}.")

    def _next_seat(
        self,
        start_seat: int,
        predicate,
        include_start: bool = False,
    ) -> Optional[int]:
        if not self.seat_order:
            return None
        start_idx = self.seat_order.index(start_seat)
        offset_start = 0 if include_start else 1
        for i in range(offset_start, len(self.seat_order) + offset_start):
            seat = self.seat_order[(start_idx + i) % len(self.seat_order)]
            if predicate(self.players[seat]):
                return seat
        return None

    def _eligible_for_positions(self) -> List[PlayerState]:
        return [p for p in self.players.values() if p.stack > 0]

    def _position_seats(self) -> tuple[int, int, int]:
        eligible = self._eligible_for_positions()
        if len(eligible) < 2:
            raise PokerRuleError("At least two players with chips are required.")
        if self.dealer_seat not in {p.seat for p in eligible}:
            self.dealer_seat = self._next_seat(
                self.dealer_seat if self.dealer_seat is not None else self.seat_order[-1],
                lambda p: p.stack > 0,
            )

        if len(eligible) == 2:
            sb = self.dealer_seat
            bb = self._next_seat(sb, lambda p: p.stack > 0)
        else:
            sb = self._next_seat(self.dealer_seat, lambda p: p.stack > 0)
            bb = self._next_seat(sb, lambda p: p.stack > 0)
        return self.dealer_seat, sb, bb

    # ---------- Hand lifecycle ----------

    def start_hand(self) -> None:
        if len(self.players_with_chips) < 2:
            raise PokerRuleError("Not enough players with chips to start another hand.")

        if self.hand_status == "ACTIVE":
            raise PokerRuleError("Current hand is still active.")

        self.hand_number += 1
        for p in self.players.values():
            p.folded = False
            p.all_in = False
            p.total_contribution = 0
            p.street_contribution = 0
            p.starting_stack = p.stack

        if self.dealer_seat is None:
            self.dealer_seat = self.configured_dealer_seat or self.seat_order[0]
            if self.players[self.dealer_seat].stack <= 0:
                self.dealer_seat = self._next_seat(
                    self.dealer_seat, lambda p: p.stack > 0
                )
        else:
            self.dealer_seat = self._next_seat(
                self.dealer_seat, lambda p: p.stack > 0
            )

        self.dealer_seat, self.small_blind_seat, self.big_blind_seat = self._position_seats()

        self.street = Street.PREFLOP
        self.current_bet = 0
        self.min_raise_size = self.big_blind
        self.acted = set()
        self.actions = []
        self.last_action = None
        self.hand_status = "ACTIVE"

        self._post_blind(self.small_blind_seat, self.small_blind)
        self._post_blind(self.big_blind_seat, self.big_blind)
        self.current_bet = max(
            self.players[self.small_blind_seat].street_contribution,
            self.players[self.big_blind_seat].street_contribution,
        )

        if len(self.players_with_chips) == 2:
            self.current_actor = self.dealer_seat
        else:
            self.current_actor = self._next_seat(
                self.big_blind_seat, lambda p: p.can_act
            )
        self._normalize_all_in_blinds()

    def _post_blind(self, seat: int, requested: int) -> None:
        p = self.player(seat)
        amount = min(requested, p.stack)
        p.stack -= amount
        p.street_contribution += amount
        p.total_contribution += amount
        if p.stack == 0:
            p.all_in = True

    def _normalize_all_in_blinds(self) -> None:
        # If a short blind is all-in, current bet remains the largest posted blind.
        self.current_bet = max(
            (p.street_contribution for p in self.players.values()),
            default=0
        )

    # ---------- Betting ----------

    def call_amount(self, seat: Optional[int] = None) -> int:
        seat = seat if seat is not None else self.current_actor
        if seat is None:
            return 0
        p = self.player(seat)
        return max(0, min(self.current_bet - p.street_contribution, p.stack))

    def legal_actions(self, seat: Optional[int] = None) -> List[Action]:
        seat = seat if seat is not None else self.current_actor
        if seat is None or self.hand_status != "ACTIVE":
            return []
        p = self.player(seat)
        if not p.can_act:
            return []
        to_call = self.call_amount(seat)
        actions = [Action.FOLD]
        if to_call == 0:
            actions.append(Action.CHECK)
        else:
            actions.append(Action.CALL)
        if p.stack > to_call:
            actions.append(Action.RAISE)
        actions.append(Action.ALL_IN)
        return actions

    def _require_turn(self, seat: int) -> PlayerState:
        if self.hand_status != "ACTIVE":
            raise PokerRuleError("No active hand.")
        if self.current_actor != seat:
            raise PokerRuleError(
                f"It is not {self.player(seat).name}'s turn. "
                f"Current actor is {self.player(self.current_actor).name if self.current_actor else 'none'}."
            )
        p = self.player(seat)
        if not p.can_act:
            raise PokerRuleError("This player cannot act.")
        return p

    def apply_action(self, seat: int, action: Action | str, amount: Optional[int] = None) -> ActionRecord:
        p = self._require_turn(seat)
        action = Action(action)
        to_call = self.call_amount(seat)

        if action == Action.FOLD:
            if amount not in (None, 0):
                raise PokerRuleError("FOLD amount must be zero.")
            paid = 0
            p.folded = True

        elif action == Action.CHECK:
            if to_call != 0:
                raise PokerRuleError(f"Cannot CHECK. Call amount is {to_call}.")
            paid = 0

        elif action == Action.CALL:
            expected = to_call
            if amount is not None and int(amount) != expected:
                raise PokerRuleError(f"CALL amount must be {expected}.")
            paid = expected

        elif action == Action.RAISE:
            if amount is None:
                raise PokerRuleError("Enter a raise-to amount.")
            target = int(amount)
            if target <= self.current_bet:
                raise PokerRuleError(
                    f"RAISE TO must be greater than the current bet of {self.current_bet}."
                )
            max_target = p.street_contribution + p.stack
            if target > max_target:
                raise PokerRuleError(f"RAISE TO cannot exceed {max_target}.")
            paid = target - p.street_contribution

        elif action == Action.ALL_IN:
            if amount not in (None, p.stack):
                raise PokerRuleError("ALL IN uses the player's entire remaining stack.")
            paid = p.stack

        else:
            raise PokerRuleError(f"Unsupported action: {action}")

        old_bet = self.current_bet
        old_stack = p.stack
        p.stack -= paid
        p.street_contribution += paid
        p.total_contribution += paid
        if p.stack == 0:
            p.all_in = True

               # Update betting state.
        if action == Action.RAISE:
            new_bet = p.street_contribution
            self.current_bet = max(self.current_bet, new_bet)
            self.acted = {seat}

        elif action == Action.ALL_IN and p.street_contribution > old_bet:
            new_bet = p.street_contribution
            increment = new_bet - old_bet
            self.current_bet = new_bet
            if increment >= self.min_raise_size:
                self.min_raise_size = increment
                self.acted = {seat}
            else:
                # Short all-in does not reopen betting.
                self.acted.add(seat)
        else:
            self.acted.add(seat)

        record = ActionRecord(
            sequence=len(self.actions) + 1,
            hand_number=self.hand_number,
            street=self.street,
            seat=seat,
            player=p.name,
            action=action,
            amount=paid,
            call_amount=to_call,
            street_contribution_after=p.street_contribution,
            total_contribution_after=p.total_contribution,
        )
        self.actions.append(record)
        self.last_action = record

        self._advance_after_action(seat)
        return record

    def _advance_after_action(self, acted_seat: int) -> None:
        remaining = [p for p in self.players.values() if not p.folded and (p.total_contribution > 0 or p.stack > 0)]
        if len(remaining) <= 1:
            self.hand_status = "AWAITING_SETTLEMENT"
            self.current_actor = None
            return

        if self._street_complete():
            self._advance_street()
            return

        self.current_actor = self._find_next_required_actor(acted_seat)
        if self.current_actor is None:
            self._advance_street()

    def _street_complete(self) -> bool:
        can_act = [p for p in self.players.values() if p.can_act and not p.folded]
        if not can_act:
            return True
        return all(
            p.seat in self.acted and p.street_contribution == self.current_bet
            for p in can_act
        )

    def _find_next_required_actor(self, after_seat: int) -> Optional[int]:
        def required(p: PlayerState) -> bool:
            if not p.can_act or p.folded:
                return False
            return p.street_contribution < self.current_bet or p.seat not in self.acted

        return self._next_seat(after_seat, required)

    def _advance_street(self) -> None:
        if self.street == Street.RIVER:
            self.hand_status = "AWAITING_SETTLEMENT"
            self.current_actor = None
            return

        next_index = STREETS.index(self.street) + 1
        self.street = STREETS[next_index]
        for p in self.players.values():
            p.street_contribution = 0
        self.current_bet = 0
        self.min_raise_size = self.big_blind
        self.acted = set()

        # If everyone is all-in, automatically run to settlement.
        if not any(p.can_act for p in self.players.values() if not p.folded):
            self.hand_status = "AWAITING_SETTLEMENT"
            self.current_actor = None
            return

        self.current_actor = self._next_seat(
            self.dealer_seat, lambda p: p.can_act and not p.folded
        )
        if self.current_actor is None:
            self.hand_status = "AWAITING_SETTLEMENT"

    # ---------- Pots / settlement ----------

    def pots(self) -> List[Pot]:
        """Build pots using actual all-in boundaries.

        A lower contribution by itself does not create a side pot. In particular,
        a player who folded after contributing less than everyone else is simply
        dead money in the single pot. Side pots are created when an *all-in*
        player caps the amount that player can contest.

        Each all-in contribution level is a boundary, plus the highest
        contribution level so the final excess forms the last side pot.
        """
        positive = [
            p for p in self.players.values()
            if p.total_contribution > 0
        ]
        if not positive:
            return []

        max_level = max(p.total_contribution for p in positive)
        all_in_levels = {
            p.total_contribution
            for p in positive
            if p.all_in
        }

        # A side-pot boundary only exists at an actual all-in level. The
        # highest contribution is always the final boundary.
        levels = sorted(all_in_levels | {max_level})

        pots: List[Pot] = []
        previous = 0
        for level in levels:
            layer = sum(
                max(0, min(p.total_contribution, level) - previous)
                for p in positive
            )
            if layer <= 0:
                previous = level
                continue

            eligible = [
                p.seat
                for p in positive
                if p.total_contribution >= level and not p.folded
            ]
            if not eligible:
                raise PokerRuleError(
                    f"No eligible players remain for pot at contribution level {level}."
                )

            label = "Main Pot" if not pots else f"Side Pot {len(pots)}"
            pots.append(Pot(layer, eligible, label))
            previous = level

        return pots

    def settle(self, winners_by_pot: Dict[int, Sequence[int]]) -> Dict[int, int]:
        if self.hand_status != "AWAITING_SETTLEMENT":
            raise PokerRuleError("The hand is not ready for settlement.")

        pots = self.pots()
        payouts: Dict[int, int] = {seat: 0 for seat in self.players}
        for idx, pot in enumerate(pots):
            winners = list(dict.fromkeys(int(s) for s in winners_by_pot.get(idx, [])))
            if not winners:
                raise PokerRuleError(f"No winner selected for {pot.label}.")
            invalid = [s for s in winners if s not in pot.eligible_seats]
            if invalid:
                raise PokerRuleError(
                    f"{pot.label}: winner seat(s) {invalid} are not eligible."
                )
            base, remainder = divmod(pot.amount, len(winners))
            ordered_winners = self._clockwise_order_from_dealer(winners)
            for i, seat in enumerate(ordered_winners):
                payouts[seat] += base + (1 if i < remainder else 0)

        for seat, amount in payouts.items():
            self.players[seat].stack += amount

        self.hand_status = "COMPLETED"
        self.current_actor = None
        return payouts

    def _clockwise_order_from_dealer(self, seats: Sequence[int]) -> List[int]:
        idx = self.seat_order.index(self.dealer_seat)
        order = [self.seat_order[(idx + i) % len(self.seat_order)] for i in range(len(self.seat_order))]
        return [s for s in order if s in set(seats)]

    # ---------- Validation / serialization ----------

    def chip_total(self) -> int:
        return sum(p.stack + p.total_contribution for p in self.players.values())

    def validate_chip_conservation(self, expected_total: int) -> None:
        actual = self.chip_total()
        if actual != expected_total:
            raise PokerRuleError(f"Chip conservation failed: expected {expected_total}, got {actual}.")

    def role(self, seat: int) -> str:
        if seat == self.dealer_seat:
            return "DEALER"
        if seat == self.small_blind_seat:
            return "SB"
        if seat == self.big_blind_seat:
            return "BB"
        return ""

    def snapshot(self) -> dict:
        return {
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
            "hand_number": self.hand_number,
            "street": self.street.value,
            "current_bet": self.current_bet,
            "min_raise_size": self.min_raise_size,
            "current_actor": self.current_actor,
            "dealer_seat": self.dealer_seat,
            "small_blind_seat": self.small_blind_seat,
            "big_blind_seat": self.big_blind_seat,
            "hand_status": self.hand_status,
            "acted": sorted(self.acted),
            "configured_dealer_seat": self.configured_dealer_seat,
            "players": {
                str(seat): {
                    "seat": p.seat,
                    "name": p.name,
                    "stack": p.stack,
                    "starting_stack": p.starting_stack,
                    "folded": p.folded,
                    "all_in": p.all_in,
                    "total_contribution": p.total_contribution,
                    "street_contribution": p.street_contribution,
                }
                for seat, p in self.players.items()
            },
            "actions": [
                {
                    "sequence": a.sequence,
                    "hand_number": a.hand_number,
                    "street": a.street.value,
                    "seat": a.seat,
                    "player": a.player,
                    "action": a.action.value,
                    "amount": a.amount,
                    "call_amount": a.call_amount,
                    "street_contribution_after": a.street_contribution_after,
                    "total_contribution_after": a.total_contribution_after,
                }
                for a in self.actions
            ],
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "PokerGame":
        players = [
            (int(v["seat"]), v["name"], int(v["stack"]))
            for v in data["players"].values()
        ]
        game = cls(
            players,
            int(data["small_blind"]),
            int(data["big_blind"]),
            data.get("configured_dealer_seat"),
        )
        game.hand_number = int(data["hand_number"])
        game.street = Street(data["street"])
        game.current_bet = int(data["current_bet"])
        game.min_raise_size = int(data["min_raise_size"])
        game.current_actor = data["current_actor"]
        game.dealer_seat = data["dealer_seat"]
        game.small_blind_seat = data["small_blind_seat"]
        game.big_blind_seat = data["big_blind_seat"]
        game.hand_status = data["hand_status"]
        game.acted = set(data.get("acted", []))
        for seat_str, v in data["players"].items():
            seat = int(seat_str)
            p = game.players[seat]
            p.stack = int(v["stack"])
            p.starting_stack = int(v["starting_stack"])
            p.folded = bool(v["folded"])
            p.all_in = bool(v["all_in"])
            p.total_contribution = int(v["total_contribution"])
            p.street_contribution = int(v["street_contribution"])
        game.actions = [
            ActionRecord(
                sequence=int(a["sequence"]),
                hand_number=int(a["hand_number"]),
                street=Street(a["street"]),
                seat=int(a["seat"]),
                player=a["player"],
                action=Action(a["action"]),
                amount=int(a["amount"]),
                call_amount=int(a["call_amount"]),
                street_contribution_after=int(a["street_contribution_after"]),
                total_contribution_after=int(a["total_contribution_after"]),
            )
            for a in data.get("actions", [])
        ]
        game.last_action = game.actions[-1] if game.actions else None
        return game
