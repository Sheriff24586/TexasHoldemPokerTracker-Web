from flask import Flask, request, redirect, url_for, render_template_string

from poker_tracker.engine import PokerGame, Action, PokerRuleError, GameHistory


app = Flask(__name__)

game = None
history = GameHistory()
error_message = ""


HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Texas Hold'em Poker Tracker</title>

    <style>
        body {
            font-family: Arial, sans-serif;
            background: #111827;
            color: #f9fafb;
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 1000px;
            margin: auto;
        }

        h1 {
            margin-bottom: 5px;
        }

        .card {
            background: #1f2937;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }

        input, select, button {
            font-size: 16px;
            padding: 10px;
            margin: 4px;
            border-radius: 6px;
            border: 1px solid #4b5563;
        }

        input, select {
            background: #111827;
            color: white;
        }

        button {
            cursor: pointer;
            background: #374151;
            color: white;
            border: none;
        }

        button:hover {
            background: #4b5563;
        }

        .primary {
            background: #2563eb;
        }

        .danger {
            background: #dc2626;
        }

        .success {
            background: #16a34a;
        }

        .players {
            width: 100%;
            border-collapse: collapse;
        }

        .players th,
        .players td {
            padding: 10px;
            border-bottom: 1px solid #374151;
            text-align: left;
        }

        .actor {
            font-weight: bold;
            background: #374151;
        }

        .error {
            background: #7f1d1d;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 15px;
        }

        .status {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }

        .status-box {
            background: #111827;
            padding: 12px 18px;
            border-radius: 8px;
        }

        .actions {
            margin-top: 15px;
        }

        @media (max-width: 600px) {
            body {
                padding: 10px;
            }

            .card {
                padding: 12px;
            }

            .players th,
            .players td {
                padding: 6px;
                font-size: 14px;
            }
        }
    </style>
</head>

<body>
<div class="container">

    <h1>♠ Texas Hold'em Poker Tracker</h1>

    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}

    {% if not game or game.hand_status == "NOT_STARTED" %}

        <div class="card">
            <h2>Game Setup</h2>

            <form method="POST" action="/start">

                <p>
                    Small Blind:
                    <input type="number"
                           name="small_blind"
                           value="5"
                           min="1"
                           required>
                </p>

                <p>
                    Big Blind:
                    <input type="number"
                           name="big_blind"
                           value="10"
                           min="1"
                           required>
                </p>

                <p>
                    Dealer Seat:
                    <select name="dealer_seat">
                        {% for seat in range(1, 11) %}
                            <option value="{{ seat }}"
                                {% if seat == 1 %}selected{% endif %}>
                                {{ seat }}
                            </option>
                        {% endfor %}
                    </select>
                </p>

                <h3>Players</h3>

                {% for seat in range(1, 11) %}
                    <div>
                        Seat {{ seat }}

                        <input type="text"
                               name="name_{{ seat }}"
                               placeholder="Player {{ seat }}"
                               value="{% if seat <= 6 %}P{{ seat }}{% endif %}">

                        <input type="number"
                               name="stack_{{ seat }}"
                               value="100"
                               min="1">
                    </div>
                {% endfor %}

                <br>

                <button class="primary" type="submit">
                    START HAND
                </button>

            </form>
        </div>

    {% else %}

        <div class="card">

            <div class="status">

                <div class="status-box">
                    <strong>Hand:</strong>
                    {{ game.hand_number }}
                </div>

                <div class="status-box">
                    <strong>Street:</strong>
                    {{ game.street.value }}
                </div>

                <div class="status-box">
                    <strong>Pot:</strong>
                    {{ game.pot }}
                </div>

                <div class="status-box">
                    <strong>Current Bet:</strong>
                    {{ game.current_bet }}
                </div>

                {% if game.current_actor %}
                    <div class="status-box">
                        <strong>Turn:</strong>
                        {{ game.player(game.current_actor).name }}
                    </div>
                {% endif %}

            </div>

        </div>

        <div class="card">

            <h2>Players</h2>

            <table class="players">

                <tr>
                    <th>Seat</th>
                    <th>Player</th>
                    <th>Role</th>
                    <th>Stack</th>
                    <th>Street</th>
                    <th>Total</th>
                    <th>Status</th>
                </tr>

                {% for p in game.players.values() %}

                    <tr class="{% if p.seat == game.current_actor %}actor{% endif %}">

                        <td>{{ p.seat }}</td>

                        <td>{{ p.name }}</td>

                        <td>{{ game.role(p.seat) }}</td>

                        <td>{{ p.stack }}</td>

                        <td>{{ p.street_contribution }}</td>

                        <td>{{ p.total_contribution }}</td>

                        <td>
                            {% if p.folded %}
                                FOLDED
                            {% elif p.all_in %}
                                ALL IN
                            {% elif p.seat == game.current_actor %}
                                TO ACT
                            {% else %}
                                -
                            {% endif %}
                        </td>

                    </tr>

                {% endfor %}

            </table>

        </div>

        {% if game.current_actor and game.hand_status == "ACTIVE" %}

            <div class="card">

                <h2>
                    Action —
                    {{ game.player(game.current_actor).name }}
                </h2>

                <p>
                    Call amount:
                    <strong>{{ game.call_amount() }}</strong>
                </p>

                <div class="actions">

                    {% for action in game.legal_actions() %}

                        {% if action.value == "RAISE" %}

                            <form method="POST"
                                  action="/action"
                                  style="display:inline-block">

                                <input type="number"
                                       name="amount"
                                       min="{{ game.current_bet + 1 }}"
                                       placeholder="Raise to"
                                       required>

                                <input type="hidden"
                                       name="action"
                                       value="RAISE">

                                <button class="primary" type="submit">
                                    RAISE TO
                                </button>

                            </form>

                        {% else %}

                            <form method="POST"
                                  action="/action"
                                  style="display:inline-block">

                                <input type="hidden"
                                       name="action"
                                       value="{{ action.value }}">

                                <button
                                    {% if action.value == "FOLD" %}
                                        class="danger"
                                    {% elif action.value == "ALL IN" %}
                                        class="success"
                                    {% endif %}
                                    type="submit">

                                    {{ action.value }}

                                </button>

                            </form>

                        {% endif %}

                    {% endfor %}

                </div>

            </div>

            <div class="card">
                <h2>Game Controls</h2>

                <form method="POST" action="{{ url_for('undo') }}" style="display:inline-block;">
                    <button type="submit">UNDO</button>
                </form>

                <form method="POST" action="{{ url_for('redo') }}" style="display:inline-block;">
                    <button type="submit">REDO</button>
                </form>
            </div>

            {% elif game.hand_status == "AWAITING_SETTLEMENT" %}

                <div class="card">
                    <h2>Hand Ready for Settlement</h2>
                    <p>The betting is complete.</p>

                    <form method="POST" action="{{ url_for('settle') }}">

                        {% for pot in game.pots() %}
                                {% set pot_index = loop.index0 %}

                                <div class="card">
                                <h3>{{ pot.label }} — {{ pot.amount }}</h3>

                                <p>Select winner(s):</p>

                                {% for seat in pot.eligible_seats %}
                                    <label style="display:block; margin:8px 0;">
                                        <input
                                            type="checkbox"
                                            name="winners_{{ pot_index }}"
                                            value="{{ seat }}"
                                        >
                                        {{ game.player(seat).name }}
                                    </label>
                                {% endfor %}
                            </div>
                        {% endfor %}

                        <button type="submit" style="margin-top: 10px;">
                            SETTLE HAND
                        </button>

                    </form>
                </div>

            <div class="card">
                <h2>Hand Completed</h2>
                <p>The hand has been settled.</p>
            </div>

        {% endif %}

        <div class="card">

            <h2>Action History</h2>

            {% if game.actions %}

                <table class="players">

                    <tr>
                        <th>#</th>
                        <th>Player</th>
                        <th>Street</th>
                        <th>Action</th>
                        <th>Amount</th>
                    </tr>

                    {% for a in game.actions %}

                        <tr>
                            <td>{{ a.sequence }}</td>
                            <td>{{ a.player }}</td>
                            <td>{{ a.street.value }}</td>
                            <td>{{ a.action.value }}</td>
                            <td>{{ a.amount }}</td>
                        </tr>

                    {% endfor %}

                </table>

            {% else %}

                <p>No actions yet.</p>

            {% endif %}

        </div>

        <div class="card">

            <form method="POST" action="/new-hand">

                <button type="submit">
                    NEW HAND
                </button>

            </form>

            <form method="POST" action="/new-session" style="margin-top: 10px;">
                <button type="submit">
                     NEW SESSION
                </button>
            </form>

        </div>

    {% endif %}

</div>
</body>
</html>
"""


@app.route("/")
def home():
    return render_template_string(
        HTML,
        game=game,
        error=error_message,
    )


@app.route("/start", methods=["POST"])
def start():
    global game, error_message

    try:
        small_blind = int(request.form["small_blind"])
        big_blind = int(request.form["big_blind"])
        dealer_seat = int(request.form["dealer_seat"])

        players = []

        for seat in range(1, 11):
            name = request.form.get(f"name_{seat}", "").strip()
            stack = int(request.form.get(f"stack_{seat}", "0"))

            if name:
                players.append((seat, name, stack))

        game = PokerGame(
            players,
            small_blind,
            big_blind,
            dealer_seat=dealer_seat,
        )

        game.start_hand()
        error_message = ""

    except (ValueError, PokerRuleError) as exc:
        error_message = str(exc)

    return redirect(url_for("home"))


@app.route("/action", methods=["POST"])
def action():
    global error_message

    if game is None:
        return redirect(url_for("home"))

    try:
        action = Action(request.form["action"])

        amount = None

        if action == Action.RAISE:
            amount = int(request.form["amount"])

        history.push(game.snapshot())

        game.apply_action(
            game.current_actor,
            action,
            amount,
        )

        error_message = ""

    except (ValueError, PokerRuleError) as exc:
        error_message = str(exc)

    return redirect(url_for("home"))

@app.route("/undo", methods=["POST"])
def undo():
    global game, error_message

    if game is not None:
        snapshot = history.undo(game.snapshot())

        if snapshot is not None:
            game = PokerGame.from_snapshot(snapshot)
            error_message = ""
        else:
            error_message = "Nothing to undo."

    return redirect(url_for("home"))

@app.route("/redo", methods=["POST"])
def redo():
    global game, error_message

    if game is not None:
        snapshot = history.redo(game.snapshot())

        if snapshot is not None:
            game = PokerGame.from_snapshot(snapshot)
            error_message = ""
        else:
            error_message = "Nothing to redo."

    return redirect(url_for("home"))

@app.route("/settle", methods=["POST"])
def settle():
    global game, error_message

    if game is not None:
        try:
            winners_by_pot = {}

            for idx, pot in enumerate(game.pots()):
                winners = request.form.getlist(f"winners_{idx}")
                winners_by_pot[idx] = [int(seat) for seat in winners]

            history.push(game.snapshot())

            game.settle(winners_by_pot)

            error_message = ""

        except (ValueError, PokerRuleError) as exc:
            error_message = str(exc)

    return redirect(url_for("home"))

@app.route("/new-hand", methods=["POST"])
def new_hand():
    global error_message

    if game is not None:
        try:
            game.start_hand()
            error_message = ""
        except PokerRuleError as exc:
            error_message = str(exc)

    return redirect(url_for("home"))

@app.route("/new-session", methods=["POST"])
def new_session():
    global game, history, error_message

    game = None
    history = GameHistory()
    error_message = ""

    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)