"""
Ford Blue Theme — Streamlit CSS Styling

Canonical Ford colour palette and CSS injection for Streamlit apps.

Usage:
    from src.styles import apply_ford_theme

    apply_ford_theme()  # Call once at app startup
"""

import streamlit as st

# === Ford Colour Palette ===

# Primary colours
FORD_BLUE = "#00095B"
FORD_ACCENT_BLUE = "#1C69D4"
FORD_LIGHT_BLUE = "#E8F1FC"

# Neutral colours
WHITE = "#FFFFFF"
DARK_GRAY = "#333333"
LIGHT_GRAY = "#F5F5F5"

# Status colours
SUCCESS_GREEN = "#198754"
WARNING_YELLOW = "#FFC107"
ERROR_RED = "#DC3545"

# Dark theme variants
DARK_BACKGROUND = "#1B1B2F"
DARK_SIDEBAR = "#162447"


# === CSS Templates ===

FORD_BLUE_CSS = """
<style>
/* ===== Ford Blue Theme ===== */

/* Main container padding */
.main { padding: 2rem; }

/* Headers in Ford Blue */
h1 {
    color: #00095B !important;
    font-weight: 600;
}
h2, h3 {
    color: #1C69D4 !important;
    font-weight: 500;
}

/* Primary buttons */
.stButton > button[kind="primary"],
.stButton > button {
    background-color: #00095B;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.5rem 1rem;
    font-weight: 500;
    transition: background-color 0.2s ease;
}
.stButton > button:hover {
    background-color: #1C69D4;
    color: white;
}

/* Download buttons */
.stDownloadButton button {
    background-color: #00095B;
    color: white;
    border: none;
}
.stDownloadButton button:hover {
    background-color: #1C69D4;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #F5F5F5;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2 {
    color: #00095B !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border-left: 4px solid #00095B;
    padding: 1rem;
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
[data-testid="stMetricLabel"] {
    color: #333333 !important;
}
[data-testid="stMetricValue"] {
    color: #00095B !important;
    font-weight: 600;
}

/* Expander styling */
.streamlit-expanderHeader {
    background-color: #E8F1FC;
    border-radius: 4px;
    font-weight: 500;
}
.streamlit-expanderHeader:hover {
    background-color: #D0E4F7;
}

/* Dataframe styling */
.stDataFrame {
    border: 1px solid #E8F1FC;
    border-radius: 4px;
}

/* Tab indicator */
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    border-bottom-color: #00095B;
    color: #00095B;
}

/* Info box */
.stAlert[data-baseweb="notification"][kind="info"] {
    background-color: #E8F1FC;
    border-left-color: #1C69D4;
}

/* Success alert */
.stAlert[data-baseweb="notification"][kind="success"] {
    border-left-color: #198754;
}

/* Warning alert */
.stAlert[data-baseweb="notification"][kind="warning"] {
    border-left-color: #FFC107;
}

/* Error alert */
.stAlert[data-baseweb="notification"][kind="error"] {
    border-left-color: #DC3545;
}

/* Selectbox and multiselect */
[data-baseweb="select"] {
    border-color: #E8F1FC;
}
[data-baseweb="select"]:focus-within {
    border-color: #1C69D4;
}

/* Text input */
.stTextInput input:focus {
    border-color: #1C69D4;
    box-shadow: 0 0 0 1px #1C69D4;
}

/* Progress bar */
.stProgress > div > div {
    background-color: #1C69D4;
}

/* Spinner */
.stSpinner > div {
    border-top-color: #00095B !important;
}

</style>
"""


def apply_ford_theme() -> None:
    """Apply Ford Blue theme CSS to the Streamlit app.

    Call this function once at the beginning of your app, typically
    right after st.set_page_config().

    Example:
        st.set_page_config(page_title="My App", layout="wide")
        apply_ford_theme()
    """
    st.markdown(FORD_BLUE_CSS, unsafe_allow_html=True)


def apply_page_config(
    page_title: str,
    page_icon: str = "🔹",
    layout: str = "wide",
    initial_sidebar_state: str = "expanded",
) -> None:
    """Apply standard Ford page configuration.

    Args:
        page_title: The browser tab title.
        page_icon: Emoji or path to icon file.
        layout: "wide" or "centered".
        initial_sidebar_state: "expanded", "collapsed", or "auto".
    """
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar_state,
    )
    apply_ford_theme()


# === Utility Components ===


def ford_header(title: str, subtitle: str | None = None, logo_path: str | None = None) -> None:
    """Render a Ford-branded header.

    Args:
        title: Main header text.
        subtitle: Optional subtitle below the main header.
        logo_path: Optional path to logo image.
    """
    cols = st.columns([1, 4]) if logo_path else [st.container()]

    if logo_path:
        with cols[0]:
            st.image(logo_path, width=80)
        with cols[1]:
            st.markdown(f"# {title}")
            if subtitle:
                st.markdown(f"*{subtitle}*")
    else:
        st.markdown(f"# {title}")
        if subtitle:
            st.markdown(f"*{subtitle}*")


def ford_info_box(message: str, icon: str = "ℹ️") -> None:
    """Render a Ford-styled info box.

    Args:
        message: The message to display.
        icon: Emoji icon to prefix the message.
    """
    st.info(f"{icon} {message}")


def ford_success_box(message: str, icon: str = "✅") -> None:
    """Render a Ford-styled success box."""
    st.success(f"{icon} {message}")


def ford_warning_box(message: str, icon: str = "⚠️") -> None:
    """Render a Ford-styled warning box."""
    st.warning(f"{icon} {message}")


def ford_error_box(message: str, icon: str = "❌") -> None:
    """Render a Ford-styled error box."""
    st.error(f"{icon} {message}")
