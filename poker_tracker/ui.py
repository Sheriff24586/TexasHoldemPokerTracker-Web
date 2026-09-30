from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget, QHeaderView
)

from .database import TrackerDB
from .engine import Action, GameHistory, PokerGame, PokerRuleError, Street


APP_STYLE = """
QWidget {
    background: #111318;
    color: #E9EDF3;
    font-family: "Segoe UI";
    font-size: 13px;
}
QMainWindow { background: #0B0D10; }
QGroupBox {
    border: 1px solid #2A303A;
    border-radius: 12px;
    margin-top: 12px;
    padding: 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #9EA8B7;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTableWidget, QListWidget {
    background: #191D24;
    border: 1px solid #303744;
    border-radius: 8px;
    padding: 7px;
    color: #F4F6F8;
}
QPushButton {
    background: #202631;
    border: 1px solid #394250;
    border-radius: 9px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton:hover { background: #2A3240; }
QPushButton:disabled { color: #606A78; background: #171A20; }
QPushButton[action="check"] { background: #176B52; }
QPushButton[action="call"] { background: #205D8F; }
QPushButton[action="raise"] { background: #9A6B14; }
QPushButton[action="allin"] { background: #8C3030; }
QPushButton[action="fold"] { background: #4B2024; }
QHeaderView::section {
    background: #20252E;
    color: #AEB7C5;
    padding: 8px;
    border: 0;
}
QTableWidget {
    gridline-color: #2A3038;
    selection-background-color: #263444;
}
QLabel#title {
    font-size: 25px;
    font-weight: 800;
}
QLabel#pot {
    font-size: 28px;
    font-weight: 800;
    color: #F1C75B;
}
QLabel#actor {
    font-size: 18px;
    font-weight: 800;
    color: #72D6AE;
}
QLabel#badge {
    background: #252B35;
    border-radius: 8px;
    padding: 6px 10px;
    color: #CDD5E0;
}
"""


class SetupPage(QWidget):
    def __init__(self, on_start):
        super().__init__()
        self.on_start = on_start

        layout = QVBoxLayout(self)
        title = QLabel("♠  TEXAS HOLD'EM TRACKER")
        title.setObjectName("title")
        subtitle = QLabel("Iteration 3  •  Python engine  •  SQLite persistence")
        subtitle.setStyleSheet("color:#8E98A8;")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        box = QGroupBox("Game Setup")
        form = QFormLayout(box)

        self.sb = QSpinBox()
        self.sb.setRange(1, 1_000_000)
        self.sb.setValue(5)
        self.bb = QSpinBox()
        self.bb.setRange(1, 1_000_000)
        self.bb.setValue(10)
        self.dealer = QSpinBox()
        self.dealer.setRange(1, 10)
        self.dealer.setValue(1)

        form.addRow("Small blind", self.sb)
        form.addRow("Big blind", self.bb)
        form.addRow("Starting dealer seat", self.dealer)
        layout.addWidget(box)

        players_box = QGroupBox("Players — configure 2 to 10")
        pv = QVBoxLayout(players_box)
        self.table = QTableWidget(10, 3)
        self.table.setHorizontalHeaderLabels(["Seat", "Player name", "Starting stack"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        for row in range(10):
            self.table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            name = QLineEdit()
            stack = QSpinBox()
            stack.setRange(1, 100_000_000)
            stack.setValue(100)
            self.table.setCellWidget(row, 1, name)
            self.table.setCellWidget(row, 2, stack)

        pv.addWidget(self.table)
        layout.addWidget(players_box, 1)

        btn = QPushButton("START SESSION")
        btn.clicked.connect(self.start_clicked)
        btn.setMinimumHeight(48)
        layout.addWidget(btn)

    def start_clicked(self):
        players = []
        for row in range(10):
            name_widget = self.table.cellWidget(row, 1)
            stack_widget = self.table.cellWidget(row, 2)
            name = name_widget.text().strip()
            if name:
                players.append((row + 1, name, stack_widget.value()))

        if not 2 <= len(players) <= 10:
            QMessageBox.warning(self, "Players", "Enter names for 2 to 10 players.")
            return
        if self.sb.value() > self.bb.value():
            QMessageBox.warning(self, "Blinds", "Small blind cannot exceed big blind.")
            return
        if self.dealer.value() not in [p[0] for p in players]:
            QMessageBox.warning(self, "Dealer", "Starting dealer seat must have a player.")
            return

        self.on_start(players, self.sb.value(), self.bb.value(), self.dealer.value())


class SettlementDialog(QDialog):
    def __init__(self, game: PokerGame, parent=None):
        super().__init__(parent)
        self.game = game
        self.setWindowTitle("Settle Hand")
        self.resize(520, 420)
        self.combos: List[QComboBox] = []
        layout = QVBoxLayout(self)

        info = QLabel(
            "Select the winner(s) for each pot. For a split pot, choose the same "
            "number of winners using the text field below."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        for idx, pot in enumerate(game.pots()):
            box = QGroupBox(f"{pot.label}  •  {pot.amount:,}")
            form = QFormLayout(box)
            eligible = [game.player(s) for s in pot.eligible_seats]
            combo = QComboBox()
            for p in eligible:
                combo.addItem(f"{p.name} (Seat {p.seat})", p.seat)
            form.addRow("Winner", combo)
            self.combos.append(combo)

            split = QLineEdit()
            split.setPlaceholderText("Optional split seats, e.g. 1,4")
            split.setObjectName(f"split_{idx}")
            form.addRow("Split seats", split)
            layout.addWidget(box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def winners(self) -> Dict[int, List[int]]:
        result = {}
        for idx, combo in enumerate(self.combos):
            box = self.findChild(QLineEdit, f"split_{idx}")
            text = box.text().strip() if box else ""
            if text:
                seats = [int(x.strip()) for x in text.split(",") if x.strip()]
            else:
                seats = [int(combo.currentData())]
            result[idx] = seats
        return result


class GamePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        root = QVBoxLayout(self)

        top = QHBoxLayout()

        self.title = QLabel("♠  Poker Table")
        self.title.setObjectName("title")

        self.hand_label = QLabel("Hand #0")
        self.hand_label.setObjectName("badge")

        self.street_label = QLabel("Preflop")
        self.street_label.setObjectName("badge")

        self.pot_label = QLabel("POT  ₹0")
        self.pot_label.setObjectName("pot")

        self.undo_btn = QPushButton("↶")
        self.undo_btn.setToolTip("Undo last action")
        self.undo_btn.setFixedSize(44, 40)
        self.undo_btn.clicked.connect(self.undo)

        self.redo_btn = QPushButton("↷")
        self.redo_btn.setToolTip("Redo last action")
        self.redo_btn.setFixedSize(44, 40)
        self.redo_btn.clicked.connect(self.redo)

        top.addWidget(self.title)
        top.addStretch()
        top.addWidget(self.undo_btn)
        top.addWidget(self.redo_btn)
        top.addWidget(self.hand_label)
        top.addWidget(self.street_label)
        top.addWidget(self.pot_label)

        root.addLayout(top)

        meta = QHBoxLayout()
        self.dealer_label = QLabel("DEALER —")
        self.sb_label = QLabel("SB —")
        self.bb_label = QLabel("BB —")

        for label in (self.dealer_label, self.sb_label, self.bb_label):
            label.setObjectName("badge")
            meta.addWidget(label)

        self.actor_label = QLabel("Waiting...")
        self.actor_label.setObjectName("actor")
        meta.addStretch()
        meta.addWidget(self.actor_label)

        root.addLayout(meta)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Seat", "Player", "Stack", "Status", "Role", "Street", "Total"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in [0, 2, 3, 4, 5, 6]:
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        root.addWidget(self.table, 1)

        action_box = QGroupBox("ACTION")
        av = QVBoxLayout(action_box)
        self.amount = QSpinBox()
        self.amount.setRange(0, 100_000_000)
        self.amount.setPrefix("₹ ")
        self.amount.setValue(0)
        self.amount.setMinimumHeight(38)
        av.addWidget(QLabel("Amount / Raise To"))
        av.addWidget(self.amount)

        buttons = QHBoxLayout()
        self.buttons = {}
        definitions = [
            (Action.CHECK, "CHECK", "check"),
            (Action.CALL, "CALL", "call"),
            (Action.RAISE, "RAISE", "raise"),
            (Action.ALL_IN, "ALL IN", "allin"),
            (Action.FOLD, "FOLD", "fold"),
        ]
        for action, text, prop in definitions:
            btn = QPushButton(text)
            btn.setProperty("action", prop)
            btn.setMinimumHeight(52)
            btn.clicked.connect(lambda checked=False, a=action: self.do_action(a))
            buttons.addWidget(btn)
            self.buttons[action] = btn
        av.addLayout(buttons)
        root.addWidget(action_box)

        bottom = QHBoxLayout()

        self.undo_btn = QPushButton("UNDO")
        self.undo_btn.clicked.connect(self.undo)

        self.redo_btn = QPushButton("REDO")
        self.redo_btn.clicked.connect(self.redo)

        self.next_hand_btn = QPushButton("NEXT HAND")
        self.next_hand_btn.clicked.connect(self.next_hand)

        self.settle_btn = QPushButton("SETTLE HAND")
        self.settle_btn.clicked.connect(self.settle_hand)
        self.history_btn = QPushButton("SESSION HISTORY")
        self.history_btn.clicked.connect(self.show_history)
        self.new_session_btn = QPushButton("NEW SESSION")
        self.new_session_btn.clicked.connect(self.main.new_session)
        bottom.addWidget(self.next_hand_btn)
        bottom.addWidget(self.settle_btn)
        bottom.addWidget(self.history_btn)
        bottom.addStretch()
        bottom.addWidget(self.new_session_btn)
        root.addLayout(bottom)

    def refresh(self):
        game = self.main.game
        if not game:
            return

        self.hand_label.setText(f"Hand #{game.hand_number}")
        self.street_label.setText(game.street.value.upper())
        self.pot_label.setText(f"POT  ₹{game.pot:,}")

        def pname(seat):
            return game.player(seat).name if seat else "—"

        self.dealer_label.setText(f"DEALER  {pname(game.dealer_seat)}")
        self.sb_label.setText(f"SB  {pname(game.small_blind_seat)}")
        self.bb_label.setText(f"BB  {pname(game.big_blind_seat)}")

        actor = game.player(game.current_actor).name if game.current_actor else "Hand ready for settlement"
        self.actor_label.setText(f"▶  {actor}")

        self.table.setRowCount(len(game.seat_order))
        for row, seat in enumerate(game.seat_order):
            p = game.player(seat)
            values = [
                str(seat),
                p.name,
                f"₹{p.stack:,}",
                "FOLDED" if p.folded else ("ALL IN" if p.all_in else "ACTIVE"),
                game.role(seat),
                f"₹{p.street_contribution:,}",
                f"₹{p.total_contribution:,}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter if col != 1 else Qt.AlignmentFlag.AlignVCenter)
                if seat == game.current_actor:
                    item.setBackground(Qt.GlobalColor.darkGreen)
                self.table.setItem(row, col, item)

            for action, btn in self.buttons.items():
                btn.setEnabled(action in game.legal_actions())
            self.undo_btn.setEnabled(self.main.history.can_undo)
            self.redo_btn.setEnabled(self.main.history.can_redo)
            self.settle_btn.setEnabled(game.hand_status == "AWAITING_SETTLEMENT")
            self.next_hand_btn.setEnabled(game.hand_status == "COMPLETED")
            self.amount.setValue(game.call_amount() if game.current_actor else 0)

    def do_action(self, action: Action):
            game = self.main.game
            if not game or game.current_actor is None:
                return

            # Auto-fill UX:
            # CHECK/FOLD => 0, CALL => exact amount needed to match current bet,
            # ALL IN => remaining stack, RAISE => user-entered Raise To.
            if action in (Action.CHECK, Action.FOLD):
                amount = 0
            elif action == Action.CALL:
                amount = game.call_amount()
                self.amount.setValue(amount)
            elif action == Action.ALL_IN:
                amount = game.player(game.current_actor).stack
                self.amount.setValue(amount)
            else:
                amount = self.amount.value()

            try:
                actor_id = game.current_actor
                actor_player = game.player(actor_id)

                before = game.snapshot()

                pot_before = game.pot
                sequence_number = len(
                    self.main.db.action_history(self.main.session_id)
                ) + 1

                game.apply_action(actor_id, action, amount)

                self.main.db.record_action(
                    session_id=self.main.session_id,
                    hand_number=game.hand_number,
                    sequence_number=sequence_number,
                    player_id=actor_id,
                    player_name=actor_player.name,
                    street=getattr(game.street, "value", str(game.street)),
                    action=getattr(action, "value", str(action)),
                    amount=amount,
                    pot_before=pot_before,
                    pot_after=game.pot,
                )

                self.main.history.push(before)
                self.main.persist()
                self.refresh()
            except PokerRuleError as exc:
                QMessageBox.warning(self, "Action not allowed", str(exc))

    def settle_hand(self):
        dialog = SettlementDialog(self.main.game, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            before = self.main.game.snapshot()
            self.main.game.settle(dialog.winners())
            self.main.history.push(before)
            self.main.persist()
            self.refresh()
        except (PokerRuleError, ValueError) as exc:
            QMessageBox.warning(self, "Settlement", str(exc))

    def next_hand(self):
        try:
            before = self.main.game.snapshot()
            self.main.game.start_hand()
            self.main.history.push(before)
            self.main.persist()
            self.refresh()
        except PokerRuleError as exc:
            QMessageBox.information(self, "Next hand", str(exc))
    def undo(self):
        game = self.main.game
        current = game.snapshot()
        previous = self.main.history.undo(current)

        if previous is None:
            return

        pot_before = game.pot

        self.main.game = PokerGame.from_snapshot(previous)

        pot_after = self.main.game.pot
        sequence_number = len(
            self.main.db.action_history(self.main.session_id)
        ) + 1

        self.main.db.record_action(
            session_id=self.main.session_id,
            hand_number=self.main.game.hand_number,
            sequence_number=sequence_number,
            player_id=0,
            player_name="SYSTEM",
            street=self.main.game.street.value,
            action="UNDO",
            amount=0,
            pot_before=pot_before,
            pot_after=pot_after,
        )

        self.main.persist()
        self.refresh()

    def redo(self):
        game = self.main.game
        current = game.snapshot()
        next_state = self.main.history.redo(current)

        if next_state is None:
            return

        pot_before = game.pot

        self.main.game = PokerGame.from_snapshot(next_state)

        pot_after = self.main.game.pot
        sequence_number = len(
            self.main.db.action_history(self.main.session_id)
        ) + 1

        self.main.db.record_action(
            session_id=self.main.session_id,
            hand_number=self.main.game.hand_number,
            sequence_number=sequence_number,
            player_id=0,
            player_name="SYSTEM",
            street=self.main.game.street.value,
            action="REDO",
            amount=0,
            pot_before=pot_before,
            pot_after=pot_after,
        )

        self.main.persist()
        self.refresh()
    def show_history(self):
        if self.main.session_id is None:
            QMessageBox.information(
                self,
                "Session History",
                "There is no active session yet."
            )
            return

        rows = self.main.db.action_history(self.main.session_id)

        dlg = QDialog(self)
        dlg.setWindowTitle("Session History — Action History")
        dlg.resize(950, 600)

        layout = QVBoxLayout(dlg)

        table = QTableWidget()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "Hand",
            "#",
            "Player",
            "Street",
            "Action",
            "Amount",
            "Pot Before",
            "Pot After",
            "Time",
        ])

        table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                table.setItem(
                    row_index,
                    col_index,
                    QTableWidgetItem(str(value))
                )

        table.resizeColumnsToContents()
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        layout.addWidget(table)

        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        layout.addWidget(close)

        dlg.exec()


class MainWindow(QMainWindow):
    def __init__(self, db_path: str | Path = "poker_tracker.db"):
        super().__init__()
        self.setWindowTitle("Texas Hold'em Poker Tracker — Iteration 3")
        self.resize(1200, 820)
        self.db = TrackerDB(db_path)
        self.session_id = None
        self.game = None
        self.history = GameHistory()

        self.stack = QStackedWidget()
        self.setup = SetupPage(self.start_game)
        self.game_page = GamePage(self)
        self.stack.addWidget(self.setup)
        self.stack.addWidget(self.game_page)
        self.setCentralWidget(self.stack)

    def start_game(self, players, sb, bb, dealer):
        try:
            self.game = PokerGame(players, sb, bb, dealer)
            self.session_id = self.db.new_session("Poker Session")
            self.game.start_hand()
            self.persist()
            self.stack.setCurrentWidget(self.game_page)
            self.game_page.refresh()
        except PokerRuleError as exc:
            QMessageBox.critical(self, "Cannot start", str(exc))

    def persist(self):
        if self.session_id and self.game:
            self.db.save_snapshot(self.session_id, self.game.snapshot())

    def new_session(self):
        answer = QMessageBox.question(
            self,
            "New session",
            "Start a completely new poker session?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.game = None
            self.session_id = None
            self.stack.setCurrentWidget(self.setup)


def run_app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(APP_STYLE)
    app.setApplicationName("Texas Hold'em Poker Tracker")
    window = MainWindow()
    window.show()
    return app.exec()
