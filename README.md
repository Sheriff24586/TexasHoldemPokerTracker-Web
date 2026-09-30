# Texas Hold'em Poker Tracker — Iteration 3

A desktop poker-session tracker rebuilt from the Excel prototype.

## Stack

- Python 3.11+
- PySide6 desktop UI
- SQLite persistence
- pytest automated tests

## Key UX behavior

The action buttons automatically manage amounts:

- **CHECK** → amount automatically becomes `0`
- **FOLD** → amount automatically becomes `0`
- **CALL** → amount automatically becomes exactly the amount needed to match the current bet
- **ALL IN** → amount automatically becomes the player's remaining stack
- **RAISE** → amount box is the **Raise To** target; the engine validates minimum raises

The engine supports repeated actions within a street, unlike the original spreadsheet iteration.

## Engine features

- 2–10 players
- Dealer/SB/BB rotation
- Heads-up blind rules
- Repeated betting rounds
- Fold/check/call/raise/all-in
- Minimum raise validation
- Short all-in handling
- Side-pot calculation
- Split-pot settlement
- Odd-chip distribution
- Player elimination
- Chip-conservation validation
- SQLite session snapshots
- Hand history/session history

This iteration uses **manual winner selection** at settlement. A future card-evaluation iteration can add hole/community cards and automatic showdown winner calculation without changing the betting engine.

## Run in VS Code

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
pytest -q
```

Launch:

```bash
python main.py
```

The app creates `poker_tracker.db` beside `main.py`.

## Suggested next iterations

1. Card/deck UI and automatic hand evaluation.
2. Visual poker-table layout with cards/chips.
3. Undo/redo action history.
4. Session reports and CSV/PDF export.
5. Packaged Windows `.exe`.
