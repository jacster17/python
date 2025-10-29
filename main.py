import streamlit as st
from datetime import datetime
from typing import Dict, Tuple, List
import os


# ---------- App State Initialization ----------
def initialize_state() -> None:
    if "players" not in st.session_state:
        # players: name -> { rating, wins, losses, games }
        st.session_state.players: Dict[str, Dict[str, float | int]] = {}
    if "matches" not in st.session_state:
        # matches: list of { time, winner, loser, k, delta }
        st.session_state.matches: List[Dict[str, object]] = []
    if "default_k" not in st.session_state:
        st.session_state.default_k = 32
    if "authed" not in st.session_state:
        st.session_state.authed = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""


# ---------- Elo Utilities ----------
def get_or_create_player(name: str) -> None:
    if name not in st.session_state.players:
        st.session_state.players[name] = {
            "rating": 1200.0,
            "wins": 0,
            "losses": 0,
            "games": 0,
        }


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def update_elo(winner: str, loser: str, k_factor: int) -> Tuple[float, float, float]:
    get_or_create_player(winner)
    get_or_create_player(loser)

    ra = st.session_state.players[winner]["rating"]
    rb = st.session_state.players[loser]["rating"]

    ea = expected_score(ra, rb)
    eb = 1.0 - ea

    delta_w = k_factor * (1 - ea)
    delta_l = k_factor * (0 - eb)

    st.session_state.players[winner]["rating"] = ra + delta_w
    st.session_state.players[loser]["rating"] = rb + delta_l

    st.session_state.players[winner]["wins"] += 1
    st.session_state.players[winner]["games"] += 1
    st.session_state.players[loser]["losses"] += 1
    st.session_state.players[loser]["games"] += 1

    return ra + delta_w, rb + delta_l, delta_w


def leaderboard_rows() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for name, info in st.session_state.players.items():
        games = int(info["games"]) if info["games"] else 0
        wins = int(info["wins"]) if info["wins"] else 0
        win_rate = (wins / games * 100.0) if games > 0 else 0.0
        rows.append(
            {
                "Player": name,
                "Rating": round(float(info["rating"]), 1),
                "Games": games,
                "Wins": wins,
                "Losses": int(info["losses"]) if info["losses"] else 0,
                "Win %": round(win_rate, 1),
            }
        )
    rows.sort(key=lambda r: (r["Rating"], r["Wins"], -r["Losses"]), reverse=True)
    return rows


# ---------- Auth ----------
def load_credentials() -> Dict[str, str]:
    # Preferred: st.secrets["auth"]["users"] = { user: pass }
    try:
        if "auth" in st.secrets and "users" in st.secrets["auth"]:
            users_obj = st.secrets["auth"]["users"]
            if isinstance(users_obj, dict) and users_obj:
                return {str(u): str(p) for u, p in users_obj.items()}
    except Exception:
        pass

    # Fallback: environment variables AUTH_USER, AUTH_PASS (single user)
    env_user = os.getenv("AUTH_USER")
    env_pass = os.getenv("AUTH_PASS")
    if env_user and env_pass:
        return {env_user: env_pass}

    # Final fallback: no creds configured -> set demo user
    return {"admin": "admin"}


def render_login(users: Dict[str, str]) -> None:
    st.title("🔒 Sign in to Ping Pong Elo")
    with st.form("login_form", clear_on_submit=False):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
        if submitted:
            username = username_input.strip()
            password = password_input
            users_lower = {str(k).lower(): str(v) for k, v in users.items()}
            if username.lower() in users_lower and users_lower[username.lower()] == password:
                st.session_state.authed = True
                st.session_state.auth_user = username
                st.success("Signed in.")
                st.rerun()
            else:
                st.error("Invalid credentials.")


# ---------- UI ----------
initialize_state()

st.set_page_config(page_title="Ping Pong Elo", page_icon="🏓", layout="wide")
users = load_credentials()
if not st.session_state.authed:
    render_login(users)
    st.stop()

st.title("🏓 Ping Pong Elo Dashboard")
st.caption("Track matches, compute Elo ratings, and view the live leaderboard.")

with st.sidebar:
    st.header("Settings")
    k_factor = st.slider("K-Factor", min_value=8, max_value=64, value=int(st.session_state.default_k), step=2)
    st.session_state.default_k = k_factor

    if st.button("Reset all data", type="secondary"):
        st.session_state.players = {}
        st.session_state.matches = []
        st.success("All data cleared.")

    st.divider()
    st.caption(f"Signed in as: {st.session_state.auth_user}")
    if st.button("Log out"):
        st.session_state.authed = False
        st.session_state.auth_user = ""
        st.experimental_clear_query_params()
        st.rerun()


left, right = st.columns([1, 1])

with left:
    st.subheader("Add Match Result")

    existing_players = sorted(list(st.session_state.players.keys()))

    col_a, col_b = st.columns(2)
    with col_a:
        player_a = st.text_input(
            "Player A",
            value=existing_players[0] if existing_players else "",
            placeholder="Enter or select player name",
        )
    with col_b:
        player_b = st.text_input(
            "Player B",
            value=existing_players[1] if len(existing_players) > 1 else "",
            placeholder="Enter or select player name",
        )

    winner = st.radio("Winner", options=["Player A", "Player B"], horizontal=True)

    can_submit = bool(player_a.strip()) and bool(player_b.strip()) and player_a.strip() != player_b.strip()
    submit = st.button("Record Match", type="primary", disabled=not can_submit)

    if submit and can_submit:
        a = player_a.strip()
        b = player_b.strip()
        win_name = a if winner == "Player A" else b
        lose_name = b if winner == "Player A" else a

        new_ra, new_rb, delta = update_elo(win_name, lose_name, k_factor)

        st.session_state.matches.insert(
            0,
            {
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Winner": win_name,
                "Loser": lose_name,
                "Δ Rating": round(delta, 1),
                "K": k_factor,
            },
        )

        st.success(f"Recorded: {win_name} def. {lose_name}  |  Δ={delta:.1f}")

with right:
    st.subheader("Leaderboard")
    rows = leaderboard_rows()
    if rows:
        st.dataframe(
            rows,
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No players yet. Add a match to start rankings.")


st.subheader("Recent Matches")
if st.session_state.matches:
    st.dataframe(st.session_state.matches, width="stretch", hide_index=True)
else:
    st.write("—")


st.caption(
    "Elo formula: E = 1 / (1 + 10^((Rb - Ra)/400)); R' = R + K * (S - E)."
)
