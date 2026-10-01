from flask import Flask, request, redirect, url_for, render_template_string

from poker_tracker.engine import PokerGame, Action, PokerRuleError, GameHistory


app = Flask(__name__)

game = None
winner_seats = set()
history = GameHistory()
error_message = ""


HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <meta name="theme-color" content="#071713">
    <title>Felt — Poker Tracker</title>
    <style>
        :root{color-scheme:dark;--felt:#103e32;--felt2:#0b2d25;--gold:#e7c27a;--ink:#f6f1e7;--muted:#a7b7ad;--line:rgba(236,218,177,.14);--panel:#101c18;--panel2:#16251f;--red:#b94949;--blue:#3279a9;--green:#1c7559}
        *{box-sizing:border-box} body{margin:0;min-height:100vh;padding:22px 14px 40px;color:var(--ink);font:15px/1.45 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(ellipse at 50% -10%,rgba(36,117,85,.34),transparent 48%),radial-gradient(circle at 8% 40%,rgba(231,194,122,.05),transparent 24%),#080f0c}
        body:before{content:"";position:fixed;inset:0;pointer-events:none;opacity:.13;background-image:repeating-linear-gradient(118deg,transparent 0 27px,rgba(255,255,255,.025) 28px,transparent 29px 55px);mask-image:linear-gradient(to bottom,#000,transparent 70%)}
        .container{position:relative;width:min(100%,520px);margin:auto}.app-header{display:flex;align-items:center;gap:13px;padding:3px 4px 20px}.app-logo{display:grid;place-items:center;width:48px;height:48px;border:1px solid rgba(231,194,122,.64);border-radius:50%;color:var(--gold);font-size:29px;background:radial-gradient(circle at 35% 30%,#214638,#0b1c15);box-shadow:0 0 28px rgba(231,194,122,.11)}.app-title{font:700 22px/1 Georgia,"Times New Roman",serif;letter-spacing:.12em;color:var(--gold)}.app-subtitle{margin-top:6px;color:#d6d5c8;font-size:10px;letter-spacing:.29em}.eyebrow{color:var(--gold);font-size:10px;font-weight:800;letter-spacing:.17em;text-transform:uppercase}
        h2{margin:0;color:var(--ink);font-size:17px;line-height:1.25}h3{margin:0 0 12px;color:var(--gold);font:600 17px Georgia,serif}p{color:var(--muted)}.card{margin:0 0 13px;padding:17px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(145deg,rgba(23,37,31,.97),rgba(13,24,19,.98));box-shadow:0 14px 36px rgba(0,0,0,.22)}
        .table-felt{position:relative;overflow:hidden;margin-bottom:13px;padding:19px 16px 16px;border:1px solid rgba(231,194,122,.48);border-radius:42% / 18%;background:radial-gradient(ellipse at center,#1a674d 0%,#15523f 48%,#0b3429 100%);box-shadow:inset 0 0 0 5px rgba(4,20,15,.38),inset 0 0 30px rgba(0,0,0,.3),0 15px 32px rgba(0,0,0,.3)}.table-felt:before{content:"♠  ♦  ♣  ♥";position:absolute;inset:12px 0 auto;text-align:center;color:rgba(255,255,255,.10);font:16px Georgia;letter-spacing:.75em}.status{position:relative;display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}.status-box{padding:8px 5px;text-align:center;border:1px solid rgba(255,255,255,.13);border-radius:12px;background:rgba(3,23,16,.32)}.status-box strong{display:block;margin-bottom:3px;color:#d4d7c9;font-size:9px;letter-spacing:.12em;text-transform:uppercase}.status-box span{display:block;color:white;font-size:16px;font-weight:750;font-variant-numeric:tabular-nums}.status-box.pot{border-color:rgba(231,194,122,.5)}.status-box.pot span{color:#ffe1a0;font-size:20px}.turn-pill{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid rgba(231,194,122,.42);border-radius:999px;background:rgba(3,20,14,.36);color:#ffe1a0;font-size:11px;font-weight:700}.turn-pill:before{content:"";width:7px;height:7px;border-radius:50%;background:#7be0a4;box-shadow:0 0 10px #7be0a4}.players-heading,.section-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:12px}.players-heading{padding:0 2px}.players-heading span:first-child{font-size:11px;font-weight:800;letter-spacing:.15em}.players-count{color:var(--muted);font-size:10px}
        .player-list{display:grid;gap:7px}.player-seat{display:grid;grid-template-columns:34px minmax(0,1fr) auto;align-items:center;gap:10px;padding:10px 11px;border:1px solid rgba(255,255,255,.07);border-radius:14px;background:rgba(255,255,255,.025)}.player-seat.actor{border-color:rgba(231,194,122,.66);background:linear-gradient(90deg,rgba(231,194,122,.13),rgba(255,255,255,.025))}.seat-no{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#263a30;color:var(--gold);font-size:11px;font-weight:800}.player-name{font-weight:750}.player-meta{margin-top:2px;color:var(--muted);font-size:11px}.stack-value{text-align:right;font-size:14px;font-weight:750;font-variant-numeric:tabular-nums}.stack-label{display:block;color:var(--muted);font-size:9px;font-weight:500;letter-spacing:.08em;text-transform:uppercase}.seat-state{grid-column:2/4;color:#ffcf80;font-size:9px;font-weight:800;letter-spacing:.1em}.seat-state.folded{color:#dd7777}.seat-state.all-in{color:#8bc8ec}.turn-card{border-color:rgba(231,194,122,.42);background:linear-gradient(145deg,#1d3026,#101b16)}.turn-top{display:flex;justify-content:space-between;align-items:center;gap:8px}.turn-name{margin:8px 0 2px;font:600 23px Georgia,serif}.call-line{margin:0 0 14px;font-size:12px}.call-line strong{color:var(--gold);font-size:17px}.actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.actions form{min-width:0}.actions button{width:100%;min-height:55px;font-size:13px;letter-spacing:.08em}.raise-form{grid-column:1/-1;display:grid;grid-template-columns:minmax(0,1fr) 120px;gap:8px}.raise-form input{min-width:0}.button,button{display:inline-flex;justify-content:center;align-items:center;cursor:pointer;min-height:43px;padding:11px 15px;border:1px solid transparent;border-radius:13px;color:white;font-weight:800;letter-spacing:.04em;background:linear-gradient(135deg,#267a5d,#16523f);box-shadow:0 6px 15px rgba(0,0,0,.2);transition:filter .15s,transform .15s}.button:hover,button:hover{filter:brightness(1.13)}button:active{transform:translateY(1px)}button[value="FOLD"],.danger{background:linear-gradient(135deg,#a54141,#722d31)}button[value="CALL"]{background:linear-gradient(135deg,#347da8,#245878)}button[value="RAISE"]{background:linear-gradient(135deg,#21805c,#15553f)}button[value="ALL_IN"],button[value="ALL IN"]{color:#21190c;background:linear-gradient(135deg,#f1ce85,#c89842)}
        input,select{width:100%;min-height:44px;padding:10px 12px;border:1px solid rgba(255,255,255,.13);border-radius:12px;outline:none;background:#0b1511;color:var(--ink);font:inherit}input:focus,select:focus{border-color:var(--gold);box-shadow:0 0 0 3px rgba(231,194,122,.11)}input[type=checkbox]{width:19px;min-height:19px;accent-color:#caa85c}.setup-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.field{display:grid;gap:6px;color:#c8d1c9;font-size:11px;font-weight:700}.field.full{grid-column:1/-1}.setup-players{display:grid;gap:7px}.setup-player{display:grid;grid-template-columns:48px minmax(0,1fr) 92px;align-items:center;gap:7px}.setup-player .seat-tag{color:var(--gold);font-size:11px;font-weight:800}.setup-player input{min-width:0}.primary-wide{width:100%;margin-top:15px;min-height:52px;color:#241b0c;background:linear-gradient(135deg,#efd08e,#c99d4d);font-size:13px;letter-spacing:.11em}
        .control-row{display:grid;grid-template-columns:1fr 1fr;gap:9px}.control-row form,.control-row button{width:100%}.secondary{border-color:var(--line);background:#202c26;box-shadow:none}.history{display:grid;gap:0}.history-row{display:grid;grid-template-columns:28px 1fr auto;gap:8px;align-items:center;padding:10px 1px;border-bottom:1px solid rgba(255,255,255,.07)}.history-row:last-child{border-bottom:0}.history-seq{color:var(--gold);font-size:10px;font-weight:800}.history-main{font-size:12px;font-weight:700}.history-sub{display:block;margin-top:2px;color:var(--muted);font-size:10px;font-weight:500}.history-amount{color:#e9d6ac;font-size:12px;font-variant-numeric:tabular-nums}.error{margin-bottom:13px;padding:12px 14px;border:1px solid rgba(255,100,100,.35);border-radius:13px;background:#642e2d;color:#fff}.settlement-pot{margin:10px 0;padding:13px;border:1px solid var(--line);border-radius:15px;background:#0d1813}.winner-option{display:flex!important;align-items:center;gap:9px;margin:7px 0!important;color:var(--ink);font-size:13px}.new-session{margin-top:9px}.muted{color:var(--muted)}
        @media(max-width:390px){body{padding:15px 10px 30px}.card{padding:14px;border-radius:17px}.table-felt{padding:17px 11px 13px}.status{gap:5px}.status-box{padding:7px 3px}.status-box span{font-size:14px}.status-box.pot span{font-size:17px}.app-title{font-size:19px}.app-logo{width:43px;height:43px}.raise-form{grid-template-columns:minmax(0,1fr) 106px}}
        @media(min-width:700px){body{padding-top:34px}.container{width:min(100%,560px)}}
   
    .player-seat.winner {
        border-color: var(--gold);
        box-shadow:
            0 0 0 1px rgba(246, 194, 74, 0.45),
            0 0 18px rgba(246, 194, 74, 0.45);
        animation: winnerGlow 1.8s ease-in-out infinite;
    }

    @keyframes winnerGlow {
        0%, 100% {
            transform: translateY(0);
            box-shadow:
                0 0 0 1px rgba(246, 194, 74, 0.35),
                0 0 12px rgba(246, 194, 74, 0.30);
        }

        50% {
            transform: translateY(-2px);
            box-shadow:
                0 0 0 2px rgba(246, 194, 74, 0.65),
                0 0 26px rgba(246, 194, 74, 0.60);
        }
    }
        
   /* ===== PREMIUM BUTTON ANIMATIONS ===== */

button {
    transition:
        transform 0.18s ease,
        box-shadow 0.18s ease,
        filter 0.18s ease,
        background 0.18s ease;
}

button:hover {
    transform: translateY(-2px);
    filter: brightness(1.08);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.28);
}

button:active {
    transform: translateY(1px) scale(0.98);
    box-shadow: 0 3px 8px rgba(0, 0, 0, 0.25);
}

button:focus-visible {
    outline: 2px solid rgba(246, 194, 74, 0.8);
    outline-offset: 3px;
}

@media (prefers-reduced-motion: reduce) {
    button {
        transition: none;
    }

    button:hover,
    button:active {
        transform: none;
    }
}
    /* ===== ACTIVE PLAYER LIVE SPARKLE ===== */

        .player-seat.active-turn {
            position: relative;
            overflow: hidden;
            border-color: rgba(246, 194, 74, 0.9);
            box-shadow:
                0 0 0 1px rgba(246, 194, 74, 0.25),
                0 0 18px rgba(246, 194, 74, 0.18);
            animation: activePlayerGlow 2s ease-in-out infinite;
        }

        .player-seat.active-turn::before {
            content: "";
            position: absolute;
            top: -30%;
            bottom: -30%;
            left: -70%;
            width: 45%;
            pointer-events: none;
            background: linear-gradient(
                100deg,
                transparent 0%,
                rgba(255, 255, 255, 0.02) 25%,
                rgba(255, 255, 255, 0.18) 45%,
                rgba(246, 194, 74, 0.42) 50%,
                rgba(255, 255, 255, 0.16) 55%,
                rgba(255, 255, 255, 0.02) 75%,
                transparent 100%
            );
            filter: blur(6px);
            transform: skewX(-18deg);
            animation: activePlayerShimmer 2.8s ease-in-out infinite;
        }

        .player-seat.active-turn::after {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            border-radius: inherit;
            box-shadow:
                inset 0 0 18px rgba(246, 194, 74, 0.18),
                inset 0 0 35px rgba(16, 185, 129, 0.12);
            animation: activePlayerPulse 1.8s ease-in-out infinite;
        }

        @keyframes activePlayerGlow {
            0%, 100% {
                box-shadow:
                    0 0 0 1px rgba(246, 194, 74, 0.22),
                    0 0 12px rgba(246, 194, 74, 0.12);
            }

            50% {
                box-shadow:
                    0 0 0 1px rgba(246, 194, 74, 0.75),
                    0 0 28px rgba(246, 194, 74, 0.32);
            }
        }

        @keyframes activePlayerPulse {
            0%, 100% {
                opacity: 0.35;
            }

            50% {
                opacity: 1;
            }
        }

        @keyframes activePlayerShimmer {
            0% {
                left: -70%;
                opacity: 0;
            }

            15% {
                opacity: 0.15;
            }

            45% {
                opacity: 0.9;
            }

            65% {
                opacity: 0.35;
            }

            100% {
                left: 125%;
                opacity: 0;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .player-seat.active-turn,
            .player-seat.active-turn::before,
            .player-seat.active-turn::after {
                animation: none;
            }
        }
    
    /* ===== PREMIUM STATUS TILES ===== */

    .status-box {
        position: relative;
        overflow: hidden;
        transition:
            transform 0.25s ease,
            border-color 0.25s ease,
            box-shadow 0.25s ease;
    }

    .status-box:hover {
        transform: translateY(-2px);
        border-color: rgba(246, 194, 74, 0.55);
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.22);
    }

    .status-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        margin: 0 auto 5px;
        color: var(--gold);
        font-size: 18px;
        line-height: 1;
        text-shadow: 0 0 10px rgba(246, 194, 74, 0.35);
    }

    .status-icon svg {
        width: 24px;
        height: 24px;
        display: block;
    }

    .status-box strong {
        display: block;
        margin-bottom: 4px;
        color: var(--muted);
        font-size: 10px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .status-box > span:last-child {
        display: block;
        font-size: 17px;
        font-weight: 800;
    }

    /* Gentle breathing animation for the status icons */

    .status-hand .status-icon,
    .status-street .status-icon,
    .status-pot .status-icon,
    .status-bet .status-icon {
        animation: statusIconBreath 2.4s ease-in-out infinite;
    }

    .status-street .status-icon {
        animation-delay: 0.3s;
    }

    .status-pot .status-icon {
        position: relative;
        animation: potShimmer 3.2s ease-in-out infinite;
        filter:
            drop-shadow(0 0 3px rgba(246, 194, 74, 0.35))
            drop-shadow(0 0 8px rgba(246, 194, 74, 0.18));
    }

    .status-pot .status-icon svg {
        width: 24px;
        height: 24px;
    }

    .status-hand .status-icon svg {
        width: 24px;
        height: 24px;
        display: block;
        margin: 0 auto;
    }

    .status-bet .status-icon {
        animation: moneyShimmer 2.6s ease-in-out infinite;
        filter:
            drop-shadow(0 0 3px rgba(246, 194, 74, 0.28))
            drop-shadow(0 0 8px rgba(246, 194, 74, 0.12));
    }

    @keyframes statusIconBreath {
        0%, 100% {
            transform: scale(1);
            opacity: 0.72;
        }

        50% {
            transform: scale(1.12);
            opacity: 1;
            text-shadow: 0 0 16px rgba(246, 194, 74, 0.65);
        }
    }
    
    @keyframes potShimmer {
        0%, 100% {
            opacity: 0.78;
            filter:
                drop-shadow(0 0 3px rgba(246, 194, 74, 0.22))
                drop-shadow(0 0 7px rgba(246, 194, 74, 0.10));
        }

        20% {
            opacity: 0.88;
            filter:
                drop-shadow(0 0 4px rgba(246, 194, 74, 0.32))
                drop-shadow(0 0 9px rgba(246, 194, 74, 0.16));
        }

        35% {
            opacity: 1;
            filter:
                drop-shadow(0 0 5px rgba(255, 255, 255, 0.55))
                drop-shadow(0 0 12px rgba(246, 194, 74, 0.42));
        }

        50% {
            opacity: 0.9;
            filter:
                drop-shadow(0 0 4px rgba(246, 194, 74, 0.35))
                drop-shadow(0 0 9px rgba(246, 194, 74, 0.18));
        }

        70%, 100% {
            opacity: 0.78;
            filter:
                drop-shadow(0 0 3px rgba(246, 194, 74, 0.22))
                drop-shadow(0 0 7px rgba(246, 194, 74, 0.10));
        }
    }

    @keyframes moneyShimmer {
        0%, 100% {
            transform: translateY(0) scale(1);
            opacity: 0.78;
            filter:
                drop-shadow(0 0 3px rgba(246, 194, 74, 0.25))
                drop-shadow(0 0 7px rgba(246, 194, 74, 0.10));
        }

        50% {
            transform: translateY(-2px) scale(1.08);
            opacity: 1;
            filter:
                drop-shadow(0 0 5px rgba(246, 194, 74, 0.55))
                drop-shadow(0 0 12px rgba(246, 194, 74, 0.28));
        }
    }

    /* ===== PREMIUM STREET CARDS ===== */

    .street-cards {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 3px;
        min-height: 34px;
        margin-bottom: 6px;
    }

    .street-card {
        position: relative;
        width: 20px;
        height: 29px;
        border: 1px solid rgba(246, 194, 74, 0.75);
        border-radius: 4px;
        background:
            linear-gradient(135deg,
                rgba(246, 194, 74, 0.16),
                rgba(255, 255, 255, 0.035));
        box-shadow:
            0 2px 8px rgba(0, 0, 0, 0.25),
            inset 0 0 0 1px rgba(255, 255, 255, 0.06);
        animation: streetCardReveal 0.55s ease-out both;
    }

    .street-card::before {
        content: "";
        position: absolute;
        inset: 3px;
        border: 1px solid rgba(246, 194, 74, 0.28);
        border-radius: 2px;
        background:
            repeating-linear-gradient(
                45deg,
                rgba(246, 194, 74, 0.07) 0,
                rgba(246, 194, 74, 0.07) 2px,
                transparent 2px,
                transparent 4px
            );
    }

    .street-card:nth-child(1) {
        animation-delay: 0.05s;
    }

    .street-card:nth-child(2) {
        animation-delay: 0.10s;
    }

    .street-card:nth-child(3) {
        animation-delay: 0.15s;
    }

    .street-card:nth-child(4) {
        animation-delay: 0.20s;
    }

    .street-card:nth-child(5) {
        animation-delay: 0.25s;
    }

    @keyframes streetCardReveal {
        0% {
            opacity: 0;
            transform: translateY(8px) scale(0.82);
        }

        70% {
            opacity: 1;
            transform: translateY(-1px) scale(1.03);
        }

        100% {
            opacity: 1;
            transform: translateY(0) scale(1);
        }
    }
    
    </style>
</head>

<body>
<div class="container">

    <div class="app-header">
        <div class="app-logo">♠</div>

        <div>
            <div class="app-title">TEXAS HOLD'EM</div>
            <div class="app-subtitle">THE TABLE · POKER TRACKER</div>
        </div>
    </div>

    {% if error %}
        <div class="error">{{ error }}</div>
    {% endif %}

    {% if not game or game.hand_status == "NOT_STARTED" %}

        <div class="card">
            <div class="section-head"><div><div class="eyebrow">Set the table</div><h2 style="margin-top:4px">Game Setup</h2></div><span class="players-count">TEXAS HOLD'EM</span></div>

            <form method="POST" action="/start">
                <div class="setup-grid">
                    <label class="field">SMALL BLIND<input type="number" name="small_blind" value="5" min="1" required></label>
                    <label class="field">BIG BLIND<input type="number" name="big_blind" value="10" min="1" required></label>
                    <label class="field full">DEALER SEAT<select name="dealer_seat">
                        {% for seat in range(1, 11) %}
                            <option value="{{ seat }}"
                                {% if seat == 1 %}selected{% endif %}>
                                {{ seat }}
                            </option>
                        {% endfor %}
                    </select></label>
                </div>

                <div class="players-heading">
                    <span>PLAYERS</span>
                    <span class="players-count">NAME + STARTING STACK</span>
                </div>

                <div class="setup-players">
                {% for seat in range(1, 11) %}
                    <div class="setup-player">
                        <span class="seat-tag">SEAT {{ seat }}</span>
                        <input aria-label="Player {{ seat }} name" type="text" name="name_{{ seat }}" placeholder="Player {{ seat }}" value="{% if seat <= 6 %}P{{ seat }}{% endif %}">
                        <input aria-label="Player {{ seat }} starting stack" type="number" name="stack_{{ seat }}" value="100" min="1">
                    </div>
                {% endfor %}
                </div>
                <button class="primary-wide" type="submit">♠ &nbsp; START SESSION</button>

            </form>
        </div>

    {% else %}

        <div class="table-felt">
            <div class="eyebrow">Hand {{ game.hand_number }} &nbsp;·&nbsp; {{ game.street.value }}</div>
            <div class="status">

                <div class="status-box status-hand">
                    <span class="status-icon hand-icon" aria-hidden="true">
                        <svg viewBox="0 0 64 64" role="img">
                            <rect x="17" y="10" width="30" height="44" rx="3"
                                fill="none" stroke="currentColor" stroke-width="3"/>
                            <rect x="11" y="16" width="30" height="44" rx="3"
                                fill="none" stroke="currentColor" stroke-width="3"/>
                            <path d="M26 27
                                    c-3-4-8-1-6 4
                                    l5 10
                                    c1 3 4 5 7 5
                                    h7
                                    c5 0 8-3 8-8
                                    v-7
                                    c0-3-4-4-5-1
                                    l-1 3
                                    v-9
                                    c0-3-4-4-5-1
                                    l-1 6
                                    v-7
                                    c0-3-4-4-5-1
                                    l-1 6
                                    v-3
                                    c0-3-4-4-4-1z"
                                fill="currentColor"/>
                        </svg>
                    </span>
                    <strong>Hand</strong>
                    <span>{{ game.hand_number }}</span>
                </div>

                <div class="status-box status-street">
                    <div class="street-cards" aria-hidden="true">
                        {% if game.street.value == "Flop" %}
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                        {% elif game.street.value == "Turn" %}
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                        {% elif game.street.value == "River" %}
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                            <span class="street-card"></span>
                        {% endif %}
                    </div>

                    <strong>Street</strong>
                    <span>{{ game.street.value }}</span>
                </div>

                <div class="status-box status-pot">
                    <span class="status-icon pot-icon" aria-hidden="true">
                        <svg viewBox="0 0 64 64" role="img" aria-hidden="true">
                            <ellipse cx="32" cy="20" rx="20" ry="7"
                                    fill="none"
                                    stroke="currentColor"
                                    stroke-width="3"/>
                            <path d="M12 20v25c0 7 9 12 20 12s20-5 20-12V20"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="3"/>
                            <path d="M15 27c4 3 10 4 17 4s13-1 17-4"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="2"/>
                            <circle cx="23" cy="18" r="4" fill="currentColor"/>
                            <circle cx="32" cy="16" r="4" fill="currentColor"/>
                            <circle cx="41" cy="19" r="4" fill="currentColor"/>
                            <path d="M19 38h26"
                                stroke="currentColor"
                                stroke-width="2"
                                stroke-linecap="round"/>
                        </svg>
                    </span>
                    <strong>Pot</strong>
                    <span>{{ game.pot }}</span>
                </div>

                <div class="status-box status-bet">
                    <span class="status-icon bet-icon" aria-hidden="true">
                        <svg viewBox="0 0 64 64" role="img" aria-hidden="true">
                            <rect x="16" y="18" width="32" height="28" rx="4"
                                fill="none"
                                stroke="currentColor"
                                stroke-width="3"/>
                            <path d="M16 25h32"
                                stroke="currentColor"
                                stroke-width="2"/>
                            <path d="M16 39h32"
                                stroke="currentColor"
                                stroke-width="2"/>
                            <circle cx="25" cy="32" r="5"
                                    fill="none"
                                    stroke="currentColor"
                                    stroke-width="2"/>
                            <path d="M34 30h9M34 35h7"
                                stroke="currentColor"
                                stroke-width="2"
                                stroke-linecap="round"/>
                            <path d="M21 14h22"
                                stroke="currentColor"
                                stroke-width="3"
                                stroke-linecap="round"/>
                        </svg>
                    </span>
                    <strong>Bet</strong>
                    <span>{{ game.current_bet }}</span>
                </div>

                {% if game.current_actor %}
                    <div class="status-box">
                        <strong>At the Table</strong><span>{{ game.player(game.current_actor).name }}</span>
                    </div>
                {% endif %}

            </div>

        </div>

        <div class="card">
            <div class="players-heading"><span>SEATS AT THE TABLE</span><span class="players-count">{{ game.players|length }} PLAYERS</span></div>
            <div class="player-list">
                {% for p in game.players.values() %}
                    <div class="player-seat{% if p.seat in winner_seats %} winner{% endif %}{% if p.seat == game.current_actor %} active-turn{% endif %}">
                        <span class="seat-no">{{ p.seat }}</span>
                        <div><div class="player-name">{{ p.name }}</div><div class="player-meta">{{ game.role(p.seat) }} · Street {{ p.street_contribution }} / Total {{ p.total_contribution }}</div></div>
                        <div class="stack-value">{{ p.stack }}<span class="stack-label">stack</span></div>
                        {% if p.folded %}<span class="seat-state folded">FOLDED</span>{% elif p.all_in %}<span class="seat-state all-in">ALL IN</span>{% elif p.seat == game.current_actor %}<span class="seat-state">TO ACT</span>{% endif %}
                    </div>
                {% endfor %}
            </div>
        </div>

        {% if game.current_actor and game.hand_status == "ACTIVE" %}

            <div class="card turn-card">
                <div class="turn-top"><span class="eyebrow">Your move</span><span class="turn-pill">SEAT {{ game.current_actor }}</span></div>
                <div class="turn-name">{{ game.player(game.current_actor).name }}</div>
                <p class="call-line">Call amount &nbsp;<strong>{{ game.call_amount() }}</strong></p>

                <div class="actions">

                    {% for action in game.legal_actions() %}

                        {% if action.value == "RAISE" %}

                            <form method="POST"
                                  action="/action"
                                  class="raise-form">

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
                                    {% elif action.value == "ALL_IN" %}
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
                <div class="section-head"><div><div class="eyebrow">Table tools</div><h2 style="margin-top:4px">Game Controls</h2></div><span class="players-count">MOVE THROUGH ACTIONS</span></div>

                <div class="control-row"><form method="POST" action="{{ url_for('undo') }}"><button class="secondary" type="submit">↶ &nbsp; UNDO</button></form><form method="POST" action="{{ url_for('redo') }}"><button class="secondary" type="submit">REDO &nbsp; ↷</button></form></div>
            </div>

            {% elif game.hand_status == "AWAITING_SETTLEMENT" %}

                <div class="card">
                    <h2>Hand Ready for Settlement</h2>
                    <p>The betting is complete.</p>

                    <form method="POST" action="{{ url_for('settle') }}">

                        {% for pot in game.pots() %}
                                {% set pot_index = loop.index0 %}

                                <div class="settlement-pot">
                                <h3>{{ pot.label }} — {{ pot.amount }}</h3>

                                <p>Select winner(s):</p>

                                {% for seat in pot.eligible_seats %}
                                    <label class="winner-option">
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

                <div class="history">
                    {% for a in game.actions %}
                        <div class="history-row"><span class="history-seq">{{ a.sequence }}</span><div class="history-main">{{ a.player }} · {{ a.action.value }}<span class="history-sub">{{ a.street.value }}</span></div><span class="history-amount">{{ a.amount }}</span></div>
                    {% endfor %}
                </div>

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

            <form method="POST" action="/new-session" class="new-session">
                <button class="secondary" type="submit">
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
        winner_seats=winner_seats,
    )


@app.route("/start", methods=["POST"])
def start():
    global game, winner_seats, error_message

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
    global game, winner_seats, error_message

    if game is not None:
        try:
            winners_by_pot = {}

            for idx, pot in enumerate(game.pots()):
                winners = request.form.getlist(f"winners_{idx}")
                winners_by_pot[idx] = [int(seat) for seat in winners]

            history.push(game.snapshot())

            game.settle(winners_by_pot)
            winner_seats = {seat for winners in winners_by_pot.values() for seat in winners}

            error_message = ""

        except (ValueError, PokerRuleError) as exc:
            error_message = str(exc)

    return redirect(url_for("home"))

@app.route("/new-hand", methods=["POST"])
def new_hand():
    global winner_seats, error_message

    if game is not None:
        try:
            winner_seats = set()
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
