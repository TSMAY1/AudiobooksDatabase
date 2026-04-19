import re
import streamlit as st
from db import run_query, load_cover_image_bytes

st.set_page_config(page_title="Guessing Game", page_icon="🎯")

MAX_WRONG_GUESSES = 6
AUTHOR_HINT_THRESHOLD = 2
SERIES_HINT_THRESHOLD = 4


# ----------------------------
# Data loading
# ----------------------------
@st.cache_data(show_spinner=False)
def get_hangman_books():
    query = """
    SELECT
        vd.BookID,
        vd.Title,
        vd.Authors,
        vd.SeriesName,
        vd.BookNumber,
        pc.ImageFilePath AS CoverImagePath
    FROM vw_book_details vd
    LEFT JOIN vw_book_primary_cover pc
        ON pc.BookID = vd.BookID
    WHERE vd.Title IS NOT NULL
      AND LEN(LTRIM(RTRIM(vd.Title))) >= 3
    ORDER BY vd.Title;
    """
    return run_query(query)


# ----------------------------
# Helpers
# ----------------------------
def normalize_text(text: str) -> str:
    """Normalize for full-title comparisons."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_guessable_char(ch: str) -> bool:
    """Letters and numbers must be guessed. Punctuation/spaces are revealed."""
    return ch.isalnum()


def build_display_title_words(secret_title: str, guessed_chars: set[str]) -> list[str]:
    words = secret_title.split(" ")
    displayed_words = []

    for word in words:
        displayed_chars = []
        for ch in word:
            if not is_guessable_char(ch):
                displayed_chars.append(ch)
            elif ch.lower() in guessed_chars:
                displayed_chars.append(ch)
            else:
                displayed_chars.append("_")

        displayed_words.append(" ".join(displayed_chars))

    return displayed_words


def get_unique_guessable_chars(secret_title: str) -> set[str]:
    return {ch.lower() for ch in secret_title if is_guessable_char(ch)}


def has_won(secret_title: str, guessed_chars: set[str]) -> bool:
    needed = get_unique_guessable_chars(secret_title)
    return needed.issubset(guessed_chars)


def choose_random_book(books_df, exclude_book_ids=None):
    if exclude_book_ids is None:
        exclude_book_ids = set()

    candidates = books_df[~books_df["BookID"].isin(exclude_book_ids)].copy()

    if candidates.empty:
        candidates = books_df.copy()

    row = candidates.sample(1).iloc[0]
    return {
        "BookID": int(row["BookID"]),
        "Title": str(row["Title"]),
        "Authors": "" if row["Authors"] is None else str(row["Authors"]),
        "SeriesName": "" if row["SeriesName"] is None else str(row["SeriesName"]),
        "BookNumber": row["BookNumber"],
        "CoverImagePath": "" if row["CoverImagePath"] is None else str(row["CoverImagePath"]),
    }


def unlock_hints():
    st.session_state.show_author_hint = (
        st.session_state.wrong_guess_count >= AUTHOR_HINT_THRESHOLD
        and bool(st.session_state.secret_authors)
    )
    st.session_state.show_series_hint = (
        st.session_state.wrong_guess_count >= SERIES_HINT_THRESHOLD
        and bool(st.session_state.secret_series)
        and st.session_state.secret_series != "Standalone"
    )


def finalize_round():
    """Update streak only once when a round finishes."""
    if st.session_state.round_scored:
        return

    if st.session_state.game_over:
        if st.session_state.won:
            st.session_state.current_streak += 1
            st.session_state.best_streak = max(
                st.session_state.best_streak,
                st.session_state.current_streak,
            )
        else:
            st.session_state.current_streak = 0

        st.session_state.round_scored = True


def start_new_game(books_df):
    used_ids = st.session_state.get("used_book_ids", set())
    book = choose_random_book(books_df, exclude_book_ids=used_ids)

    st.session_state.secret_book_id = book["BookID"]
    st.session_state.secret_title = book["Title"]
    st.session_state.secret_authors = book["Authors"]
    st.session_state.secret_series = book["SeriesName"]
    st.session_state.secret_book_number = book["BookNumber"]
    st.session_state.secret_cover_path = book["CoverImagePath"]

    st.session_state.guessed_chars = set()
    st.session_state.wrong_letters = []
    st.session_state.wrong_guess_count = 0
    st.session_state.game_over = False
    st.session_state.won = False
    st.session_state.message = ""
    st.session_state.last_full_guess = ""

    st.session_state.show_author_hint = False
    st.session_state.show_series_hint = False
    st.session_state.round_scored = False
    st.session_state.last_feedback_type = "neutral"

    used_ids.add(book["BookID"])
    st.session_state.used_book_ids = used_ids


def ensure_game_started(books_df):
    if "used_book_ids" not in st.session_state:
        st.session_state.used_book_ids = set()

    if "current_streak" not in st.session_state:
        st.session_state.current_streak = 0

    if "best_streak" not in st.session_state:
        st.session_state.best_streak = 0

    if "show_author_hint" not in st.session_state:
        st.session_state.show_author_hint = False

    if "show_series_hint" not in st.session_state:
        st.session_state.show_series_hint = False

    if "round_scored" not in st.session_state:
        st.session_state.round_scored = False

    if "last_feedback_type" not in st.session_state:
        st.session_state.last_feedback_type = "neutral"

    if "secret_cover_path" not in st.session_state:
        st.session_state.secret_cover_path = ""

    needed_keys = [
        "secret_title",
        "guessed_chars",
        "wrong_letters",
        "wrong_guess_count",
        "game_over",
        "won",
        "message",
    ]
    if not all(key in st.session_state for key in needed_keys):
        start_new_game(books_df)

    unlock_hints()
    finalize_round()


def process_letter_guess(raw_guess: str):
    guess = raw_guess.lower().strip()

    if len(guess) != 1 or not guess.isalnum():
        st.session_state.message = "Please enter a single letter or number."
        st.session_state.last_feedback_type = "neutral"
        return

    if guess in st.session_state.guessed_chars or guess in st.session_state.wrong_letters:
        st.session_state.message = f"You already guessed '{guess}'."
        st.session_state.last_feedback_type = "neutral"
        return

    secret_title = st.session_state.secret_title
    secret_chars = get_unique_guessable_chars(secret_title)

    if guess in secret_chars:
        st.session_state.guessed_chars.add(guess)
        st.session_state.message = f"Nice! '{guess}' is in the title."
        st.session_state.last_feedback_type = "correct"
    else:
        st.session_state.wrong_letters.append(guess)
        st.session_state.wrong_guess_count += 1
        st.session_state.message = f"Sorry, '{guess}' is not in the title."
        st.session_state.last_feedback_type = "wrong"

    unlock_hints()

    if has_won(secret_title, st.session_state.guessed_chars):
        st.session_state.game_over = True
        st.session_state.won = True
        st.session_state.message = "You won! 🎉"
        st.session_state.last_feedback_type = "win"

    if st.session_state.wrong_guess_count >= MAX_WRONG_GUESSES:
        st.session_state.game_over = True
        st.session_state.won = False
        st.session_state.message = "Out of guesses!"
        st.session_state.last_feedback_type = "loss"

    finalize_round()


def process_full_title_guess(raw_guess: str):
    guess = raw_guess.strip()

    if not guess:
        st.session_state.message = "Please enter a title guess."
        st.session_state.last_feedback_type = "neutral"
        return

    st.session_state.last_full_guess = guess

    if normalize_text(guess) == normalize_text(st.session_state.secret_title):
        secret_chars = get_unique_guessable_chars(st.session_state.secret_title)
        st.session_state.guessed_chars = set(secret_chars)
        st.session_state.game_over = True
        st.session_state.won = True
        st.session_state.message = "Perfect! You guessed the full title. 🎉"
        st.session_state.last_feedback_type = "win"
    else:
        st.session_state.wrong_guess_count += 1
        st.session_state.message = "That full-title guess was not correct."
        st.session_state.last_feedback_type = "wrong"

        unlock_hints()

        if st.session_state.wrong_guess_count >= MAX_WRONG_GUESSES:
            st.session_state.game_over = True
            st.session_state.won = False
            st.session_state.message = "Out of guesses!"
            st.session_state.last_feedback_type = "loss"

    finalize_round()


# ----------------------------
# Page UI
# ----------------------------
st.title("🎯 Audiobook Hangman")

books_df = get_hangman_books()

if books_df.empty:
    st.warning("No books were found in vw_book_details.")
    st.stop()

ensure_game_started(books_df)

secret_title = st.session_state.secret_title
display_words = build_display_title_words(secret_title, st.session_state.guessed_chars)

puzzle_html = " ".join(
    f'<span class="hangman-word">{word}</span>'
    for word in display_words
)

remaining_guesses = MAX_WRONG_GUESSES - st.session_state.wrong_guess_count

puzzle_state_class = {
    "neutral": "",
    "correct": "puzzle-correct",
    "wrong": "puzzle-wrong",
    "win": "puzzle-win",
    "loss": "puzzle-loss",
}.get(st.session_state.last_feedback_type, "")

st.markdown(
    f"""
    <style>
    .hangman-puzzle {{
        font-size: clamp(1.25rem, 5vw, 2rem);
        line-height: 1.8;
        padding: 0.85rem 1rem;
        border-radius: 0.75rem;
        border: 1px solid rgba(128,128,128,0.3);
        margin-bottom: 1rem;
        font-family: 'Courier New', monospace;
        background: rgba(255,255,255,0.02);
    }}

    .hangman-word {{
        display: inline-block;
        white-space: nowrap;
        margin-right: 1.25rem;
        margin-bottom: 0.35rem;
    }}

    .hangman-hints {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin: 0.5rem 0 1rem 0;
    }}

    .hint-card {{
        padding: 0.75rem 0.9rem;
        border-radius: 0.75rem;
        border: 1px solid rgba(128,128,128,0.25);
        background: rgba(255,255,255,0.03);
        flex: 1 1 260px;
    }}

    .hint-label {{
        font-size: 0.8rem;
        opacity: 0.75;
        margin-bottom: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}

    .streak-wrap {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-bottom: 1rem;
    }}

    .streak-card {{
        flex: 1 1 180px;
        padding: 0.85rem 1rem;
        border-radius: 0.75rem;
        border: 1px solid rgba(128,128,128,0.25);
        background: rgba(255,255,255,0.03);
    }}

    .streak-label {{
        font-size: 0.8rem;
        opacity: 0.75;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}

    .streak-value {{
        font-size: 1.5rem;
        font-weight: 700;
        margin-top: 0.2rem;
    }}

    @keyframes pulseGlow {{
        0% {{ transform: scale(1); box-shadow: 0 0 0 rgba(0,0,0,0); }}
        50% {{ transform: scale(1.01); box-shadow: 0 0 22px rgba(120, 255, 170, 0.18); }}
        100% {{ transform: scale(1); box-shadow: 0 0 0 rgba(0,0,0,0); }}
    }}

    @keyframes shakeSoft {{
        0% {{ transform: translateX(0); }}
        20% {{ transform: translateX(-3px); }}
        40% {{ transform: translateX(3px); }}
        60% {{ transform: translateX(-2px); }}
        80% {{ transform: translateX(2px); }}
        100% {{ transform: translateX(0); }}
    }}

    .puzzle-correct {{
        animation: pulseGlow 0.45s ease;
    }}

    .puzzle-wrong {{
        animation: shakeSoft 0.3s ease;
    }}

    .puzzle-win {{
        animation: pulseGlow 0.8s ease;
        border-color: rgba(80, 200, 120, 0.55);
    }}

    .puzzle-loss {{
        animation: shakeSoft 0.45s ease;
        border-color: rgba(255, 120, 120, 0.45);
    }}

    @media (max-width: 640px) {{
        .hangman-puzzle {{
            padding: 0.75rem;
            line-height: 1.6;
        }}

        .hangman-word {{
            margin-right: 0.9rem;
            margin-bottom: 0.25rem;
        }}

        .streak-value {{
            font-size: 1.3rem;
        }}
    }}
    </style>

    <div class="hangman-puzzle {puzzle_state_class}">{puzzle_html}</div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.show_author_hint or st.session_state.show_series_hint:
    hint_count = int(st.session_state.show_author_hint) + int(st.session_state.show_series_hint)

    if hint_count == 2:
        hint_col1, hint_col2 = st.columns(2)
        cols = [hint_col1, hint_col2]
    else:
        cols = [st.container()]

    idx = 0

    if st.session_state.show_author_hint:
        with cols[idx]:
            with st.container(border=True):
                st.caption("Author Hint")
                st.write(st.session_state.secret_authors)
        idx += 1

    if st.session_state.show_series_hint:
        with cols[idx]:
            with st.container(border=True):
                st.caption("Series Hint")
                st.write(st.session_state.secret_series)

if st.session_state.message:
    if st.session_state.game_over and st.session_state.won:
        st.success(st.session_state.message)
    elif st.session_state.game_over and not st.session_state.won:
        st.error(st.session_state.message)
    else:
        st.info(st.session_state.message)

if not st.session_state.game_over:
    tab1, tab2 = st.tabs(["Guess a Letter", "Guess Full Title"])

    with tab1:
        with st.form("letter_guess_form", clear_on_submit=True):
            letter_guess = st.text_input("Enter one letter or number", max_chars=1)
            submitted_letter = st.form_submit_button("Submit Letter")

        if submitted_letter:
            process_letter_guess(letter_guess)
            st.rerun()

    with tab2:
        with st.form("title_guess_form", clear_on_submit=True):
            title_guess = st.text_input("Enter your full title guess")
            submitted_title = st.form_submit_button("Submit Title Guess")

        if submitted_title:
            process_full_title_guess(title_guess)
            st.rerun()

else:
    st.markdown("### Answer")

    answer_col1, answer_col2 = st.columns([1, 1.6])

    with answer_col1:
        if st.session_state.secret_cover_path:
            try:
                st.image(
                    load_cover_image_bytes(st.session_state.secret_cover_path),
                    width=200
                )
            except Exception:
                st.caption("No cover")
        else:
            st.caption("No cover")

    with answer_col2:
        st.write(f"**{st.session_state.secret_title}**")

        meta_parts = []
        if st.session_state.secret_authors:
            meta_parts.append(f"**Author(s):** {st.session_state.secret_authors}")
        if st.session_state.secret_series:
            meta_parts.append(f"**Series:** {st.session_state.secret_series}")
        if st.session_state.secret_series != "Standalone":
            meta_parts.append(f"**Book #:** {st.session_state.secret_book_number}")

        if meta_parts:
            st.markdown("  \n".join(meta_parts))

wrong_letters_text = ", ".join(st.session_state.wrong_letters) if st.session_state.wrong_letters else "None"
st.markdown(f"**Wrong letters:** {wrong_letters_text}")

stat_col1, stat_col2 = st.columns(2)
with stat_col1:
    st.metric("Wrong Guesses", st.session_state.wrong_guess_count)
with stat_col2:
    st.metric("Remaining", remaining_guesses)

st.markdown(
    f"""
    <div class="streak-wrap">
        <div class="streak-card">
            <div class="streak-label">Current Streak</div>
            <div class="streak-value">{st.session_state.current_streak}</div>
        </div>
        <div class="streak-card">
            <div class="streak-label">Best Streak</div>
            <div class="streak-value">{st.session_state.best_streak}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.button("🔄 New Game", width='stretch'):
    start_new_game(books_df)
    st.rerun()

if st.button("♻️ Reset Used Books", width='stretch'):
    st.session_state.used_book_ids = set()
    start_new_game(books_df)
    st.rerun()