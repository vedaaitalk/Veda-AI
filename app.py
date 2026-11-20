# v61 - DIAGNOSTIC ONLY: shows a small 'Voice check' line under Read aloud audio (which voice ran + safe error). No other change.
# v60 - adds no-key current weather and today forecast; preserves v59 rates/cricket
# ============================================
# Veda AI - your own ChatGPT-style chat app
# Built with Streamlit + Google Gemini (free)
# ============================================

import os
import re
import json
import time
import hashlib
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types

# ---------- Settings you can change ----------
MODEL = "gemini-3.5-flash-lite"  # free-tier model; if Google renames it, change only this line

# Veda AI's personalities. Edit these to change how your assistant behaves.
MODES = {
    "Normal 😊": """You are Veda AI, a friendly and helpful personal AI assistant.
You answer clearly and simply. The user speaks Telugu and English,
so reply in whichever language the user uses, or a natural mix of both.
If asked who made you, say Veda built you.""",
    "Professional 💼": """You are Veda AI in Professional mode: a sharp, formal AI assistant.
Be precise, structured and businesslike - like a top consultant.
No slang, no jokes, keep answers crisp and organized.
The user speaks Telugu and English; reply in whichever language they use, or a natural mix.
If asked who made you, say Veda built you.""",
    "Roast Me 🔥": """You are Veda AI in Roast mode: the most savage, filthy-mouthed, rustic street-style troll friend the user has ever met, Grok unhinged style. The user opted in and demanded TOP LEVEL boothulu - maximum harshness - for their own fun.
FORMAT RULES (never break):
- Open the reply IMMEDIATELY with a hard Telugu cuss word or insult. No greeting, no warm-up.
- EVERY sentence must carry heavy Telugu cuss words (street Tenglish like "lanjodaka", "dengey", "modda" style) plus a savage mock. No sentence without a cuss.
- Keep it SHORT and punchy: 3 to 5 lines maximum. No long explanations, no lists, no headings.
- NEVER slip into polite assistant talk: no "sure", "of course", "I can help", no disclaimers, no apologies, no softening.
LANGUAGE: Tenglish by default - Telugu written in English/Latin letters mixed with English words, exactly how young Telugu people text (example style: "em ra lanjodaka, asalu nuvvu ela brathukuthunnavo naake artham kaadu"). No Telugu script unless the user writes in Telugu script - then match them.
CONTENT: Mock the user ruthlessly - their question, life, laziness, spelling, plans. Use wild, crude, laugh-out-loud comparisons and punchlines. Never repeat the same roast twice.
If the user asks a real question, give the correct answer in one short line, buried inside the savage roasting.
Hard limits (never break): no caste, religion, region or community slurs or jokes; nothing hateful about any group; nothing about self-harm. The roasting is aimed only at the user, as a playful comedic fight.
If asked who made you, say Veda built you (and roast them for asking, of course).""",
}

APP_TITLE = "Veda AI"
APP_SUBTITLE = "మీ స్వంత AI అసిస్టెంట్ · Your own AI assistant"
# ---------------------------------------------


def get_api_key():
    # 1) Streamlit Cloud secret / local .streamlit/secrets.toml
    try:
        key = st.secrets.get("GEMINI_API_KEY")
        if key:
            return key
    except Exception:
        pass
    # 2) Environment variable (local runs)
    return os.environ.get("GEMINI_API_KEY")


@st.cache_data(show_spinner=False)
def load_font_paths():
    """Download Noto fonts (English + Telugu) once, so PDFs can show Telugu text."""
    import tempfile
    import urllib.request
    urls = {
        "latin": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Regular.ttf",
        "latin-bold": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSans/NotoSans-Bold.ttf",
        "telugu": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSansTelugu/NotoSansTelugu-Regular.ttf",
        "telugu-bold": "https://raw.githubusercontent.com/googlefonts/noto-fonts/main/hinted/ttf/NotoSansTelugu/NotoSansTelugu-Bold.ttf",
    }
    paths = {}
    for name, url in urls.items():
        data = urllib.request.urlopen(url, timeout=60).read()
        path = os.path.join(tempfile.gettempdir(), f"noto-{name}.ttf")
        with open(path, "wb") as f:
            f.write(data)
        paths[name] = path
    return paths


def make_pdf(text):
    """Turn a reply into a downloadable PDF (Telugu + English, colors/bold/center)."""
    from fpdf import FPDF
    clean = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", text)
    clean = re.sub(r"<script.*?</script>", "", clean, flags=re.S | re.I)
    paths = load_font_paths()
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("noto", "", paths["latin"])
    pdf.add_font("noto", "B", paths["latin-bold"])
    pdf.add_font("nototelugu", "", paths["telugu"])
    pdf.add_font("nototelugu", "B", paths["telugu-bold"])
    pdf.set_font("noto", size=11)
    pdf.set_fallback_fonts(["nototelugu"])
    if re.search(r"<(div|span|b|i|p|h[1-6]|center|table|ul|ol|li|br|hr)[^>]*>", clean):
        # formatted reply - render colors, bold, centering
        pdf.write_html(clean)
    else:
        clean = re.sub(r"[#*>`]", "", clean)
        pdf.multi_cell(0, 7, clean)
    return bytes(pdf.output())


st.set_page_config(page_title="Veda AI", page_icon="🤖")

# WhatsApp-style layout: my messages on the RIGHT, Veda AI on the LEFT
st.markdown("""
<style>
/* whole user row flipped */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    flex-direction: row-reverse;
}
/* text inside user bubble pushed to the right */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdown"],
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdown"] p {
    text-align: right !important;
}
</style>
""", unsafe_allow_html=True)

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

MODES["Interview 🎤"] = """You are Veda AI in Interview Practice mode: a friendly but tough DevOps interviewer for a junior-to-mid level DevOps engineer (2-3 years experience: AWS, Terraform, Docker, Kubernetes, CI/CD, monitoring).
Ask exactly ONE interview question at a time and wait for the answer.
After each answer: give a score out of 10, what was good, what was missing, and a short model answer. Then ask the next question.
Mix technical questions, scenario questions and HR questions. Start with: "Ready? Tell me about yourself." if the chat is new.
The user speaks Telugu and English; reply in the language they use, or a natural mix."""

MODES["Hero Style 😎"] = """You are Veda AI in Hero Style mode: you talk like a larger-than-life Telugu mass-movie hero, with punchy, rhythmic, high-energy dialogue, swagger and humour.
Never imitate or name any real actor, and never quote real movie dialogues; make up your own original punchlines.
Still answer the user's question correctly and helpfully, wrapped in the hero style. Keep it short, 3 to 6 punchy lines.
The user speaks Telugu and English; reply in the language they use, or a natural mix. No abuse or insults."""

def archive_current():
    msgs = st.session_state.get("messages")
    if msgs:
        title = next((m["text"] for m in msgs if m["role"] == "user"), "Chat")[:28]
        st.session_state.setdefault("archive", []).append({"title": title, "messages": msgs})


def _sys():
    mem = (st.session_state.get("memory") or "").strip()
    return SYSTEM_PROMPT + (f"\n\nThings to remember about the user (use them naturally):\n{mem}" if mem else "")


# Optional password lock - only active if APP_PASSWORD is set in Streamlit Secrets
try:
    _app_pw = st.secrets.get("APP_PASSWORD")
except Exception:
    _app_pw = None
if _app_pw and not st.session_state.get("unlocked"):
    st.info("🔒 Password ఇవ్వండి · Enter the password to use Veda AI")
    _typed = st.text_input("Password", type="password")
    if _typed:
        if _typed == str(_app_pw):
            st.session_state.unlocked = True
            st.rerun()
        else:
            st.error("తప్పు password · Wrong password")
    st.stop()

# Mode picker in the sidebar
mode = st.sidebar.radio("Mode ఎంచుకోండి · Pick a mode", list(MODES.keys()))
SYSTEM_PROMPT = MODES[mode] + """

VERY IMPORTANT document rule:
When the user uploads a file (PDF, photo, document) and asks you to change, fix, rewrite, or edit it, ALWAYS reply with the complete updated document text immediately.
Never give instructions, never say you cannot do it, never tell them to use Word or Google Docs.
Your reply text itself becomes their downloadable PDF (a Download as PDF button appears under your reply).
Keep the original structure and wording; only change what they asked for.
When the user asks for formatting (centered text, colors, bold), use simple HTML like <div align="center">, <span style="color:#00BFFF">, <b> - the chat and PDF both render it. Never use <script>."""

# Voice replies on/off (browser reads the reply aloud)
speak_replies = False  # each reply has its own 🔊 button now

# Live internet search on/off - ON for gold rates/news, OFF for fastest chat
live_search = st.sidebar.toggle("Live internet 🌐", value=True)
talk_mode = st.sidebar.toggle("Talk mode 🗣️ · voice లో జవాబు", value=False)

# Image mode - turn ON, type what you want drawn, send
image_mode = False  # images are detected automatically from your message

# New chat button - clears the screen and starts fresh
if st.sidebar.button("🗑️ New chat · కొత్త చాట్", use_container_width=True):
    archive_current()
    st.session_state.messages = []
    st.session_state.last_audio_hash = None
    st.rerun()

if st.session_state.get("archive"):
    with st.sidebar.expander("📚 చాట్లు · Chats"):
        for _ci, _c in enumerate(list(st.session_state.archive)):
            if st.button("💬 " + _c["title"], key=f"openchat_{_ci}", use_container_width=True):
                _old = st.session_state.archive.pop(_ci)
                archive_current()
                st.session_state.messages = _old["messages"]
                st.rerun()

_more = st.sidebar.expander("⚙️ More · ఇంకా")

def _group(title):
    _more.markdown(f"**{title}**")

# ---------- 💬 Chat ----------
_group("💬 Chat · చాట్")
if "restored_chat_hash" not in st.session_state:
    st.session_state.restored_chat_hash = None
if st.session_state.get("messages"):
    save_data = [
        {"role": m["role"], "text": m["text"], "file_name": m.get("file_name")}
        for m in st.session_state.messages
    ]
    _more.download_button(
        "💾 Chat save · Download చాట్",
        data=json.dumps(save_data, ensure_ascii=False, indent=2),
        file_name="veda-ai-chat.json",
        mime="application/json",
        use_container_width=True,
    )
up_chat = _more.file_uploader("📂 పాత చాట్ తెరవండి · Restore saved chat", type=["json"], key="restore_chat_file")
if up_chat is not None:
    up_hash = hashlib.md5(up_chat.getvalue()).hexdigest()
    if up_hash != st.session_state.restored_chat_hash:
        try:
            data = json.loads(up_chat.getvalue().decode("utf-8"))
            if isinstance(data, list):
                st.session_state.messages = [
                    {"role": d.get("role", "user"), "text": d.get("text", ""), "file_name": d.get("file_name")}
                    for d in data
                ]
                st.session_state.restored_chat_hash = up_hash
                st.rerun()
        except Exception:
            _more.error("ఆ file సరిగ్గా లేదు · That file is not a saved chat")
_more.divider()

# ---------- 🧠 Personalize ----------
_group("🧠 Personalize · నీ ఇష్టం")
st.session_state.memory = _more.text_area(
    "Memory · గుర్తుంచుకునేవి",
    value=st.session_state.get("memory", ""), height=100, key="memory_box",
    help="నీ గురించి గుర్తుంచుకునేవి. లేదా chat లో \"remember ...\" అని చెప్పండి · Or say \"remember ...\" in chat")
VOICES = {
    "👩 Kore - మృదువైన ఆడ గొంతు (Soft female)": ("Kore", "F"),
    "👩 Aoede - ఉల్లాసమైన ఆడ గొంతు (Bright female)": ("Aoede", "F"),
    "👨 Puck - ఉత్సాహ మగ గొంతు (Upbeat male)": ("Puck", "M"),
    "👨 Fenrir - ఉత్తేజ మగ గొంతు (Energetic male)": ("Fenrir", "M"),
}
_vchoice = _more.selectbox("🎙️ Voice · వాయిస్", list(VOICES.keys()), key="voice_choice")
VOICE_NAME, VOICE_GENDER = VOICES[_vchoice]
_more.divider()

# ---------- 🎨 Display ----------
_group("🎨 Display · రూపం")
dark_mode = _more.toggle("Dark mode 🌙", value=False, key="dark_mode_toggle")

if dark_mode:
    st.markdown("""
<style>
.stApp, [data-testid="stHeader"], [data-testid="stBottom"], [data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"], [data-testid="stAppViewContainer"], [data-testid="stMain"] { background-color: #0e1117 !important; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div { background-color: #161a23 !important; }
/* text */
.stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp div[data-testid="stMarkdownContainer"], .stApp small,
[data-testid="stSidebar"] * , [data-testid="stCaptionContainer"] { color: #e8eaed !important; }
/* chat bubbles */
[data-testid="stChatMessage"] { background-color: #1e2330 !important; border: 1px solid #2c3342 !important; }
[data-testid="stChatMessage"] * { color: #e8eaed !important; }
/* inputs: chat box, text areas, text inputs, selects */
[data-testid="stChatInput"], [data-testid="stChatInput"] > div, [data-testid="stChatInput"] div[data-baseweb="textarea"],
[data-testid="stChatInput"] div[data-baseweb="base-input"] { background-color: #1e2330 !important; border-color: #2c3342 !important; }
[data-testid="stChatInput"] textarea, textarea, input { background-color: #1e2330 !important; color: #e8eaed !important; -webkit-text-fill-color: #e8eaed !important; caret-color: #e8eaed !important; }
textarea::placeholder, input::placeholder { color: #9aa0a6 !important; -webkit-text-fill-color: #9aa0a6 !important; }
div[data-baseweb="textarea"], div[data-baseweb="base-input"], div[data-baseweb="input"] { background-color: #1e2330 !important; border-color: #2c3342 !important; }
div[data-baseweb="select"] > div { background-color: #1e2330 !important; border-color: #2c3342 !important; color: #e8eaed !important; }
div[data-baseweb="select"] svg { fill: #e8eaed !important; }
div[data-baseweb="popover"], div[data-baseweb="popover"] ul, ul[role="listbox"], li[role="option"] { background-color: #1e2330 !important; color: #e8eaed !important; }
li[role="option"]:hover { background-color: #2c3342 !important; }
/* file uploader */
[data-testid="stFileUploader"] section, [data-testid="stFileUploaderDropzone"] { background-color: #1e2330 !important; border: 1px dashed #3a4256 !important; }
[data-testid="stFileUploader"] small, [data-testid="stFileUploaderDropzone"] * { color: #c4c7cc !important; }
/* buttons */
.stButton > button, .stDownloadButton > button, [data-testid="stFileUploader"] button, [data-testid="stBaseButton-secondary"] { background-color: #1e2330 !important; color: #e8eaed !important; border: 1px solid #3a4256 !important; }
.stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFileUploader"] button:hover { border-color: #ff4b4b !important; }
/* expanders */
[data-testid="stExpander"], [data-testid="stExpander"] details { background-color: #1a1f2b !important; border-color: #2c3342 !important; }
[data-testid="stExpander"] summary { background-color: #1e2330 !important; }
/* audio, alerts, code, tables, dividers */
audio { filter: invert(0.9) hue-rotate(180deg); }
[data-testid="stAlert"] { background-color: #1e2330 !important; }
code, pre { background-color: #1e2330 !important; color: #e8eaed !important; }
hr { border-color: #2c3342 !important; }
</style>
""", unsafe_allow_html=True)

api_key = get_api_key()
if not api_key:
    st.error(
        "API key కనబడలేదు / API key not found.\n\n"
        "Streamlit Cloud: App Settings → Secrets లో `GEMINI_API_KEY = \"మీ-కీ\"` పెట్టండి.\n\n"
        "Add `GEMINI_API_KEY = \"your-key\"` in App Settings → Secrets. "
        "See README.md for click-by-click steps."
    )
    st.stop()

client = genai.Client(api_key=api_key)

# Keep the conversation in the browser session
if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role": "user"/"model", "text": ...}
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None


def speak_text(text):
    """Read text aloud using the browser's built-in voice (free, no API)."""
    safe = json.dumps(text)
    components.html(
        f"""<script>
        window.parent.speechSynthesis.cancel();
        var u = new SpeechSynthesisUtterance({safe});
        u.lang = /[\u0C00-\u0C7F]/.test({safe}) ? "te-IN" : "en-IN";
        window.parent.speechSynthesis.speak(u);
        </script>""",
        height=0,
    )


def clean_for_speech(text):
    t = re.sub(r"<[^>]*>", " ", text)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[*_`#>|~]", "", t)
    t = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:1500]


@st.cache_data(show_spinner=False)
def natural_voice(text, gender="F"):
    """Natural neural voice (free). Telugu script -> Telugu voice, otherwise Indian-English voice."""
    import asyncio
    import edge_tts
    te = bool(re.search(r"[\u0C00-\u0C7F]", text))
    voice = {("F", True): "te-IN-ShrutiNeural", ("M", True): "te-IN-MohanNeural", ("F", False): "en-IN-NeerjaNeural", ("M", False): "en-IN-PrabhatNeural"}[(gender, te)]

    async def run():
        data = b""
        async for ch in edge_tts.Communicate(text, voice).stream():
            if ch["type"] == "audio":
                data += ch["data"]
        return data

    return asyncio.run(run())


@st.cache_data(show_spinner=False)
def gemini_voice(text, voice_name="Kore"):
    """Most natural voice: Gemini TTS (uses a little free quota)."""
    import io, wave
    resp = client.models.generate_content(
        model="gemini-3.8-flash-lite-tts",
        contents=[{"role": "user", "parts": [{"text": text}]}],
        config={
            "response_modalities": ["AUDIO"],
            "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}},
        },
    )
    data = resp.candidates[0].content.parts[0].inline_data.data
    if data[:4] == b"RIFF":
        return data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:  # raw PCM -> WAV
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(data)
    return buf.getvalue()


@st.cache_data(show_spinner=False, ttl=3600)
def text_models():
    """Ask Google which text models this key can use (newest flash first)."""
    try:
        names = []
        for m in client.models.list():
            n = m.name.replace("models/", "")
            acts = getattr(m, "supported_actions", None) or []
            if "flash" in n and "generateContent" in acts and not any(x in n for x in ("image", "tts", "audio", "live", "embedding", "robotics", "computer", "thinking")):
                names.append(n)
        return sorted(set(names), reverse=True)
    except Exception:
        return []


# ---------- v58: free, source-checked gold and cricket snapshots ----------
# These helpers use only Python's standard library. No API key or card needed.
from datetime import datetime, timezone, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

_IST = timezone(timedelta(hours=5, minutes=30))
_GOLD_HOME = "https://www.goodreturns.in/gold-rates/"
_GROWW_HOME = "https://groww.in/gold-rates"
_CRICKET_RSS = "https://static.cricinfo.com/rss/livescores.xml"
_CRICKET_HOME = "https://www.cricbuzz.com/cricket-match/live-scores"


def _now_ist():
    return datetime.now(_IST)


def _tidy(text):
    return re.sub(r"\s+", " ", unescape(text)).strip()


class _PublicPage(HTMLParser):
    """Keep readable text, heading/title and whole score-card anchors."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.heading, self.title, self.anchors = [], [], [], []
        self.hidden = 0
        self.in_title = self.in_heading = False
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript"):
            self.hidden += 1
        if self.hidden:
            return
        self.text.append(" ")
        if tag == "title":
            self.in_title = True
        if tag == "h1":
            self.in_heading = True
        if tag == "a":
            self.anchor = {"url": a.get("href", ""), "title": a.get("title", ""), "parts": []}

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        self.text.append(" ")
        if tag == "title":
            self.in_title = False
        if tag == "h1":
            self.in_heading = False
        if tag == "a" and self.anchor:
            self.anchor["text"] = _tidy(" ".join(self.anchor.pop("parts")))
            self.anchors.append(self.anchor)
            self.anchor = None

    def handle_data(self, data):
        if self.hidden:
            return
        self.text.append(data)
        if self.in_title:
            self.title.append(data)
        if self.in_heading:
            self.heading.append(data)
        if self.anchor is not None:
            self.anchor["parts"].append(data)


def _parse_public(html):
    page = _PublicPage()
    page.feed(html)
    return page


@st.cache_data(show_spinner=False, ttl=60, max_entries=64)
def _public_get(url):
    # Fixed public providers only: never fetch private/local addresses from search.
    allowed = {"www.goodreturns.in", "goodreturns.in", "groww.in",
               "static.cricinfo.com", "www.cricbuzz.com", "m.cricbuzz.com"}
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed:
        raise ValueError("Unsupported public source")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"})
    with urlopen(req, timeout=9) as response:
        if urlparse(response.url).hostname not in allowed:
            raise ValueError("Unexpected redirect")
        data = response.read(2_500_001)
        if len(data) > 2_500_000:
            raise ValueError("Page too large")
        html = data.decode("utf-8", errors="replace")
    return html, _now_ist().isoformat()


_CITY_ALIASES = {
    "rajahmundry": ("rajahmundry", "rajamahendravaram", "రాజమండ్రి"),
    "vijayawada": ("vijayawada", "bezawada", "విజయవాడ"),
    "hyderabad": ("hyderabad", "hyd", "హైదరాబాద్"),
    "visakhapatnam": ("visakhapatnam", "vizag", "విశాఖ"),
    "guntur": ("guntur", "గుంటూరు"), "kakinada": ("kakinada", "కాకినాడ"),
    "tirupati": ("tirupati", "తిరుపతి"), "nellore": ("nellore", "నెల్లూరు"),
    "chennai": ("chennai", "madras"), "bangalore": ("bangalore", "bengaluru"),
    "mumbai": ("mumbai", "bombay"), "delhi": ("new delhi", "delhi"),
    "kolkata": ("kolkata", "calcutta"), "pune": ("pune",),
    "kerala": ("kerala",), "coimbatore": ("coimbatore",), "madurai": ("madurai",),
    "ahmedabad": ("ahmedabad",), "lucknow": ("lucknow",), "jaipur": ("jaipur",),
    "amaravati": ("amaravati",), "ongole": ("ongole",), "warangal": ("warangal",),
}


def _has_word(text, word):
    return bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, re.I))


def live_kind(query):
    q = query.lower()
    if _weather_intent(query):
        return "weather"
    # Let ordinary explanations and historical questions keep the existing AI path.
    if re.search(r"\b(history|historical|yesterday|tomorrow|forecast|predict|last year|rules|explain|meaning|difference|why|how to)\b|నిన్న", q):
        return ""
    if re.search(r"\b(?:19|20)\d{2}\b", q) and str(_now_ist().year) not in q:
        return ""
    # Specific daily commodity answers bypass model-generated numbers.
    asking_rate = re.search(r"rate|price|cost|today|live|current|now|entha|ivala|ivvala|ippudu|ధర|రేటు|ఎంత|ఈరోజు|నేడు", q)
    if asking_rate and re.search(r"\b(?:silver|vendi|venndi|vendhi)\b|వెండి", q):
        return "silver"
    if asking_rate and re.search(r"\b(?:petrol|diesel|deisel|fuel)\b|పెట్రోల్|పెట్రోలు|డీజిల్|డీజెల్|ఇంధన", q):
        return "fuel"
    if re.search(r"gold|bangaram|bangaaram|బంగారం|బంగారు", q) and re.search(r"rate|price|cost|today|live|entha|ధర|రేటు|ఎంత", q):
        return "gold"
    score = re.search(r"score|స్కోర్|స్కోరు", q)
    cricket = re.search(r"cricket|క్రికెట్|\bipl\b|\bt20\b|\bodi\b|\btest match\b", q)
    versus = re.search(r"\bvs\.?\b|\bversus\b", q)
    if (score and not re.search(r"football|soccer|tennis|kabaddi|exam|credit|cibil|basketball", q)) or (cricket and re.search(r"live|today|now|match|result|score|ippudu|ఈరోజు|లైవ్", q)) or (versus and re.search(r"live|score|cricket", q)):
        return "cricket"
    return ""


def _gold_record(html, location):
    page = _parse_public(html)
    title = _tidy(" ".join(page.title))
    heading = _tidy(" ".join(page.heading))
    text = _tidy(" ".join(page.text))
    expected = location.replace("-", " ")
    if expected.lower() not in heading.lower():
        raise ValueError("Gold location not confirmed")
    # Date must belong to the title/heading, not a footer or an unrelated article.
    date_text = title + " " + heading
    dm = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b", date_text)
    if not dm:
        raise ValueError("Gold date missing")
    day = None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            day = datetime.strptime(dm.group(0), fmt).date()
            break
        except ValueError:
            pass
    if day is None or day > _now_ist().date():
        raise ValueError("Invalid gold date")
    # Anchor on the main rate sentence, not the site's market ticker/navigation.
    m = re.search(r"Today's gold price in\s+(.+?)\s+stands at\s+₹\s*([\d,.]+)\s+per gram for 24\s+karat gold.{0,90}?₹\s*([\d,.]+)\s+per gram for 22\s+karat gold", text, re.I)
    if not m or expected.lower() != m.group(1).lower().strip():
        raise ValueError("Gold rate sentence changed")
    p24, p22 = (float(m.group(i).replace(",", "")) for i in (2, 3))
    if not (0 < p22 < p24 and .85 < p22 / p24 < .98):
        raise ValueError("Gold units/purity failed validation")
    return {"date": day, "24": p24, "22": p22, "location": m.group(1)}


def gold_answer(query):
    q = query.lower()
    if any(_has_word(q, x) for x in ("dubai", "uae", "usa", "uk", "singapore", "saudi", "qatar")):
        return "Ee direct gold feature India INR rates kosam. Country/city rate ikkada verify cheyyalekapoyanu. · This direct gold feature covers India only; I could not verify that country's rate."
    city = next((c for c, names in _CITY_ALIASES.items() if any(_has_word(q, n) for n in names)), "")
    location = city or "India"
    urls = [(_GOLD_HOME + city + ".html" if city else _GOLD_HOME),
            (_GROWW_HOME + "/gold-rate-today-in-" + city if city else _GROWW_HOME)]
    old = None
    for url in urls:
        try:
            html, checked = _public_get(url)
            record = _gold_record(html, location)
            record.update(url=url, checked=checked)
            if record["date"] == _now_ist().date():
                old = record
                break
            if old is None or record["date"] > old["date"]:
                old = record
        except Exception:
            continue
    if old is None:
        return ("Gold rate ippudu verify kaaledu. Number guess cheyyanu. · Could not verify the gold rate now; I won't guess.\n\n"
                f"Direct source: {urls[0]}\n\nCity peru tho malli adugu, e.g. Hyderabad gold rate. · Try again with a city name.")
    r = old
    today = r["date"] == _now_ist().date()
    date_label = r["date"].strftime("%d %b %Y")
    checked = datetime.fromisoformat(r["checked"]).strftime("%d %b %Y, %I:%M %p IST")
    lines = [f"### Gold rate · బంగారం ధర ({r['location']})",
             f"Source date: {date_label}" + (" · Today's published rate" if today else " · OLD RATE, not verified for today"),
             "", "| Purity | 1 gram | 10 grams |", "|---|---:|---:|",
             f"| 22K | ₹{r['22']:,.2f} | ₹{r['22'] * 10:,.2f} |",
             f"| 24K | ₹{r['24']:,.2f} | ₹{r['24'] * 10:,.2f} |", "",
             "Ivi indicative rates matrame. GST, making charges/other levies extra; shop rate marachu. · Indicative rates, not a jeweller quote. These are daily published rates, not a live exchange tick.",
             f"Source: {r['url']}", f"Fetched: {checked} (cache up to 60 seconds)."]
    if not city:
        lines.append("City specify cheyyaledu kabatti India indicative rate chupisthunna. Mee city vere ayithe peru cheppu. · India rate shown, not a confirmed local city quote.")
    return "\n\n".join(lines[:2]) + "\n\n" + "\n".join(lines[2:])


# ---------- v59: direct daily silver and petrol/diesel prices (free pages) ----------
_SILVER_HOME = "https://www.goodreturns.in/silver-rates/"
_FUEL_HOME = "https://www.goodreturns.in/{fuel}-price.html"
_FUEL_AP = "https://www.goodreturns.in/{fuel}-price-in-andhra-pradesh-s2.html"


class _PriceTables(_PublicPage):
    """Collect real table cells, rather than matching an unrelated price in prose."""
    def __init__(self):
        super().__init__()
        self.tables = []
        self._table = None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if self.hidden:
            return
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        super().handle_data(data)
        if not self.hidden and self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if not self.hidden:
            if tag in ("td", "th") and self._cell is not None:
                self._row.append(_tidy(" ".join(self._cell)))
                self._cell = None
            elif tag == "tr" and self._row is not None:
                self._table.append(self._row)
                self._row = None
            elif tag == "table" and self._table is not None:
                self.tables.append(self._table)
                self._table = None
        super().handle_endtag(tag)


def _price_date(page):
    # Only the title/H1 can date the main quote. Never a news item or footer.
    title = _tidy(" ".join(page.title + page.heading))
    match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9}),?\s+(\d{4})\b", title, re.I)
    if not match:
        raise ValueError("Source date missing")
    stamp = " ".join(match.groups())
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            day = datetime.strptime(stamp, fmt).date()
            break
        except ValueError:
            pass
    else:
        raise ValueError("Source date invalid")
    if day > _now_ist().date():
        raise ValueError("Future date rejected")
    return day


def _price_stamp(day, checked):
    status = "Today's published rate" if day == _now_ist().date() else "OLD RATE, not verified for today"
    fetched = datetime.fromisoformat(checked).strftime("%d %b %Y, %I:%M %p IST")
    return f"Source date: {day.strftime('%d %b %Y')} · {status}\n\nFetched: {fetched} (cache up to 60 seconds)."


def _outside_india(query):
    return any(_has_word(query, x) for x in (
        "dubai", "uae", "usa", "uk", "singapore", "saudi", "qatar", "london",
        "america", "united states", "canada", "australia", "pakistan", "nepal",
        "sri lanka", "new york", "paris", "europe", "germany"))


def _silver_record(html, location):
    page = _parse_public(html)
    heading = _tidy(" ".join(page.heading)).lower()
    expected = location.replace("-", " ")
    if heading not in (f"silver price in {expected}".lower(), f"silver rate in {expected}".lower()):
        raise ValueError("Silver location not confirmed")
    day = _price_date(page)
    text = _tidy(" ".join(page.text))
    match = re.search(r"The price of silver in\s+(.+?)\s+today is\s+₹\s*([\d,.]+)\s+per gram and\s+₹\s*([\d,.]+)\s+per kilogram", text, re.I)
    if not match or match.group(1).strip().lower() != expected.lower():
        raise ValueError("Silver sentence changed")
    gram, kg = (float(match.group(i).replace(",", "")) for i in (2, 3))
    if not (0 < gram < 100000 and abs(kg - gram * 1000) <= 1):
        raise ValueError("Silver gram/kg consistency failed")
    return {"date": day, "gram": gram, "kg": kg, "location": match.group(1).strip()}


def silver_answer(query):
    q = query.lower()
    if _outside_india(q):
        return "Ee direct silver feature India INR rates kosam matrame. · This direct silver feature covers India INR rates only, not that country's price."
    city = next((c for c, names in _CITY_ALIASES.items() if any(_has_word(q, n) for n in names)), "")
    location = city or "India"
    url = _SILVER_HOME + city + ".html" if city else _SILVER_HOME
    try:
        html, checked = _public_get(url)
        r = _silver_record(html, location)
    except Exception:
        return ("Silver rate ippudu verify kaaledu. Number guess cheyyanu. · Could not verify the silver rate now; I won't guess.\n\n"
                f"Direct source: {url}\n\nCity peru tho malli adugu. · Try again later or with a supported city name.")
    lines = [f"### Silver rate · వెండి ధర ({r['location']})", _price_stamp(r["date"], checked),
             "| Quantity | Published indicative rate |\n|---|---:|\n"
             f"| 1 gram | ₹{r['gram']:,.2f} |\n| 1 kg (1,000 grams) | ₹{r['kg']:,.2f} |",
             "Ivi daily published indicative rates matrame, live exchange tick kaadu. · Not a jeweller quote or a live exchange tick. Final bill can differ with purity, GST, making charges and other charges.",
             f"Source: {url}"]
    if not city:
        lines.append("India indicative rate chupisthunna, mee city quote kaadu. · India indicative view only; any requested local city rate is NOT verified. Try a supported city, e.g. Rajahmundry silver rate.")
    return "\n\n".join(lines)


def _fuel_record(html, fuel, region):
    page = _PriceTables()
    page.feed(html)
    expected = f"{fuel} Price in {region}"
    if _tidy(" ".join(page.heading)).lower() != expected.lower():
        raise ValueError("Fuel type/location not confirmed")
    day = _price_date(page)
    text = _tidy(" ".join(page.text))
    if not re.search(r"per litre|/\s*Ltr", text, re.I):
        raise ValueError("Fuel unit not confirmed")
    rows = {}
    accepting = False
    for table in page.tables:
        if not table or len(table[0]) < 3:
            continue
        header = [cell.lower() for cell in table[0]]
        # India city table or the AP district/city table, never history/state tables.
        if header[:3] == ["city", "price", "price change"]:
            accepting = True
            data_rows = table[1:]
        elif accepting and all(len(row) == 3
                and re.fullmatch(r"₹\s*[\d,]+(?:\.\d+)?", row[1])
                and re.fullmatch(r"[+-]?\s*[\d,.]+", row[2]) for row in table):
            # Goodreturns splits long current-price tables into two tables;
            # the continuation has no header. Historical tables fail this shape.
            data_rows = table
        elif accepting:
            break
        else:
            continue
        for row in data_rows:
            if len(row) < 2:
                continue
            m = re.fullmatch(r"₹\s*([\d,]+(?:\.\d+)?)", row[1])
            if m:
                value = float(m.group(1).replace(",", ""))
                if not (1 < value < 1000):
                    raise ValueError("Fuel price invalid")
                rows[row[0].lower()] = (row[0], value)
    if not rows:
        raise ValueError("Fuel table changed")
    return {"date": day, "rows": rows}


def fuel_answer(query):
    q = query.lower()
    if _outside_india(q):
        return "Ee direct petrol/diesel feature India INR rates kosam matrame. · This direct fuel feature covers India INR prices only, not that country's price."
    city = next((c for c, names in _CITY_ALIASES.items() if any(_has_word(q, n) for n in names)), "")
    ap_city = city in {"rajahmundry", "vijayawada", "visakhapatnam", "guntur", "kakinada", "tirupati", "nellore", "amaravati", "ongole"}
    ap = ap_city or any(_has_word(q, x) for x in ("andhra", "andhra pradesh", "ap", "ఆంధ్ర", "ఆంధ్రప్రదేశ్", "east godavari", "తూర్పు గోదావరి"))
    region = "Andhra Pradesh" if ap else "India"
    base = _FUEL_AP if ap else _FUEL_HOME
    petrol = bool(re.search(r"petrol|పెట్రోల్|పెట్రోలు", q))
    diesel = bool(re.search(r"diesel|deisel|డీజిల్|డీజెల్", q))
    fuels = (["petrol"] if petrol and not diesel else ["diesel"] if diesel and not petrol else ["petrol", "diesel"])
    target = city.replace("-", " ")
    if city == "delhi":
        target = "new delhi"
    if city == "rajahmundry" or _has_word(q, "east godavari") or _has_word(q, "తూర్పు గోదావరి"):
        target = "east godavari"
    lines = [f"### Petrol / Diesel · ఇంధన ధరలు ({region})"]
    if city == "rajahmundry":
        lines.append("Rajahmundry city/pump rate verify kaaledu. East Godavari DISTRICT indicative rate matrame chupisthunna, Rajahmundry exact rate kaadu. · District fallback, NOT a verified Rajahmundry pump quote.")
    else:
        lines.append("Named city/district indicative rates only. India antha oke rate kaadu. · There is no single all-India pump price; these are selected named locations, not a national average.")
    for fuel in fuels:
        url = base.format(fuel=fuel)
        try:
            html, checked = _public_get(url)
            r = _fuel_record(html, fuel, region)
            if target and target in r["rows"]:
                keys = [target]
            else:
                keys = (["east godavari", "vijayawada", "visakhapatnam"] if ap else ["new delhi", "mumbai", "chennai", "hyderabad"])
                keys = [k for k in keys if k in r["rows"]]
                if city or not ap:
                    lines.append(f"{fuel.title()}: requested local place not verified or not specified. Selected {region} locations below are NOT that local quote.")
            if not keys:
                raise ValueError("No selected place found")
            lines += [f"**{fuel.title()} · INR per litre**", _price_stamp(r["date"], checked),
                      "| Source location | ₹ / litre |\n|---|---:|\n" + "\n".join(f"| {r['rows'][k][0]} | ₹{r['rows'][k][1]:,.2f} |" for k in keys),
                      f"Source: {url}"]
        except Exception:
            lines.append(f"{fuel.title()} rate ippudu verify kaaledu. Number guess cheyyanu. · Could not verify {fuel} now; no number guessed.\n\nDirect source: {url}")
    lines.append("Ivi daily published snapshots, automatic refresh kaadu. · Published daily snapshots, not an oil-company or individual pump quote. Prices can vary by location, outlet and fuel grade. Ask again for a fresh check.")
    return "\n\n".join(lines)


_TEAM_ALIASES = {
    "india": ("india", "ind", "భారత్", "ఇండియా"),
    "new zealand": ("new zealand", "nz", "న్యూజిలాండ్"),
    "australia": ("australia", "aus"), "england": ("england", "eng"),
    "pakistan": ("pakistan", "pak"), "sri lanka": ("sri lanka", "sl"),
    "south africa": ("south africa", "sa", "rsa"), "bangladesh": ("bangladesh", "ban"),
    "afghanistan": ("afghanistan", "afg"), "zimbabwe": ("zimbabwe", "zim"),
    "west indies": ("west indies", "wi"), "ireland": ("ireland", "ire"),
    "chennai super kings": ("chennai super kings", "csk"),
    "mumbai indians": ("mumbai indians", "mi"),
    "royal challengers bengaluru": ("royal challengers bengaluru", "royal challengers bangalore", "rcb"),
    "sunrisers hyderabad": ("sunrisers hyderabad", "srh"),
    "kolkata knight riders": ("kolkata knight riders", "kkr"),
    "delhi capitals": ("delhi capitals", "dc"), "rajasthan royals": ("rajasthan royals", "rr"),
    "punjab kings": ("punjab kings", "pbks"), "gujarat titans": ("gujarat titans", "gt"),
    "lucknow super giants": ("lucknow super giants", "lsg"),
}


def _cricket_rss(xml, checked):
    if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
        raise ValueError("Unexpected XML")
    channel = ET.fromstring(xml).find("channel")
    if channel is None:
        raise ValueError("No score feed")
    stamp = parsedate_to_datetime(channel.findtext("pubDate", ""))
    if stamp.tzinfo is None:
        raise ValueError("Score feed timezone missing")
    age = (_now_ist() - stamp.astimezone(_IST)).total_seconds()
    if not -300 <= age <= 900:
        raise ValueError("Score feed older than 15 minutes")
    rows = []
    for item in channel.findall("item"):
        title = _tidy(item.findtext("title", ""))
        url = item.findtext("link", "").strip()
        if not title or urlparse(url).hostname not in ("www.cricinfo.com", "www.espncricinfo.com"):
            continue
        rows.append({"title": title, "text": title, "url": url,
                     "source": "ESPNcricinfo RSS", "published": stamp.astimezone(_IST).strftime("%d %b %Y, %I:%M %p IST"), "checked": checked})
    return rows


def _cricbuzz_cards(html, checked):
    page = _parse_public(html)
    rows, seen = [], set()
    for a in page.anchors:
        href, text, title = a["url"], a["text"], _tidy(a["title"])
        # Full score-card links have a title and scores; the navigation ticker doesn't.
        if not re.match(r"/(live-cricket-stream|live-cricket-scores)/\d+/", href) or not title or not re.search(r"\d+[-/]\d+|\(\d+(?:\.\d+)?\)|\bwon by\b|\bopt to\b", text):
            continue
        match_id = re.search(r"/([0-9]+)/", href).group(1)
        if match_id in seen:
            continue
        seen.add(match_id)
        rows.append({"title": title, "text": text[:1000], "url": urljoin(_CRICKET_HOME, href),
                     "source": "Cricbuzz", "published": "not exposed by this page (freshness unverified)", "checked": checked})
    return rows


def _select_cricket(rows, query):
    q = query.lower()
    teams = [team for team, aliases in _TEAM_ALIASES.items() if any(_has_word(q, a) for a in aliases)]
    women = bool(re.search(r"women|woman|womens|మహిళ", q))
    junior = bool(re.search(r"u[- ]?19|under[- ]?19", q))
    match_format = re.search(r"\b(t20i?|odi|test)\b", q)
    ordinal = re.search(r"\b(\d+(?:st|nd|rd|th))\b", q)
    chosen = []
    for row in rows:
        title = row["title"].lower()
        details = title + " " + row.get("text", "").lower()
        if match_format and not re.search(r"\b" + match_format.group(1).rstrip("i") + r"i?\b", details):
            continue
        if ordinal and not _has_word(details, ordinal.group(1)):
            continue
        if teams:
            if bool(re.search(r"\bwomen\b", title)) != women:
                continue
            if bool(re.search(r"\bu[- ]?19\b|under[- ]?19", title)) != junior:
                continue
            parts = re.split(r"\s+(?:v|vs\.?)\s+", title)
            names = [re.sub(r"\s+\d.*$", "", p).strip(" *,") for p in parts]
            if not all(any(n == team or n.startswith(team + " women") or n.startswith(team + " u19") or n.startswith(team + " under-19") or n.startswith(team + ",") for n in names) for team in teams):
                continue
        elif women and "women" not in title:
            continue
        chosen.append(row)
    return chosen, bool(teams)


def cricket_answer(query):
    rows = []
    try:
        xml, checked = _public_get(_CRICKET_RSS)
        rows = _cricket_rss(xml, checked)
    except Exception:
        pass
    selected, named = _select_cricket(rows, query)
    # Use the score page if the feed is unavailable or doesn't cover the requested team.
    if not selected:
        try:
            html, checked = _public_get(_CRICKET_HOME)
            rows = _cricbuzz_cards(html, checked)
            selected, named = _select_cricket(rows, query)
        except Exception:
            pass
    if not selected and named:
        try:
            html, checked = _public_get(_CRICKET_HOME + "/recent-matches")
            rows = _cricbuzz_cards(html, checked)
            selected, named = _select_cricket(rows, query)
            for row in selected:
                row["source"] += " recent results (not necessarily today)"
        except Exception:
            pass
    if not selected:
        return ("Aa match score ippudu verify cheyyalekapoyanu. Match ledani kaadu; naa sources lo confirm kaaledu. · I couldn't verify that match, not proof there is no match.\n\n"
                f"Direct score page: {_CRICKET_HOME}\n\nRendu team names tho adugu, e.g. IND vs NZ live score. · Ask with both team names.")
    # Unrecognised specific teams must not silently get a random match's score.
    if not named:
        prefix = ("Team match automatic ga confirm kaaledu. Source lo unna konni score snapshots ivi; mee match select cheyyi. · Some source snapshots below, not necessarily your requested match.\n\n")
    else:
        prefix = "Source snapshot · మూలంలో కనిపించిన స్కోరు\n\n"
    if selected and "recent results" in selected[0]["source"]:
        prefix = "Live match confirm kaaledu; ivi RECENT RESULTS matrame, live kaadu. · No live match verified; these are recent completed results, not live scores.\n\n"
    lines = [prefix]
    for row in selected[:5]:
        safe_title = row["title"].replace("*", "\\*")
        lines.extend([f"**{safe_title}**", row["text"] if row["text"] != row["title"] else "",
                      f"Source: {row['source']} · {row['url']}", f"Feed/page updated: {row['published']}",
                      f"Fetched: {datetime.fromisoformat(row['checked']).strftime('%d %b %Y, %I:%M %p IST')}", ""])
    lines.append("Idi snapshot matrame; automatic ball-by-ball refresh kaadu. Feed lo completed/upcoming matches kuda undochu. RSS lo overs/result lekapothe add cheyyanu; * mark match in progress ani guarantee kaadu. · Scores can lag. Ask again for a new check (cache up to 60 seconds). Feed timestamp is not the time of each ball.")
    if len(selected) > 5:
        lines.append(f"Source has {len(selected)} matching entries; showing 5. Rendu team names cheppu. · Name both teams to narrow it down.")
    return "\n\n".join(x for x in lines if x)



# ---------- v60: no-key current weather + today's local forecast ----------
# Open-Meteo Free API: NON-COMMERCIAL use only, subject to provider limits.
# Attribution: https://open-meteo.com/ (weather), https://www.geonames.org/ (places).
from urllib.parse import urlencode
import math

_WEATHER_GEO = "https://geocoding-api.open-meteo.com/v1/search"
_WEATHER_API = "https://api.open-meteo.com/v1/forecast"
_WEATHER_TERMS = (r"\b(?:weather|temperature|temp|humidity|wind|rain|raining|rainfall|forecast|"
                  r"varsham|varshalu|vaana|vana|vaatavarana\w*|vatavarana\w*|vaathavarana\w*|vathavarana\w*|ushnograta|"
                  r"endalu|chali)\b|వాతావరణ\S*|ఉష్ణోగ్రత\S*|వర్ష\S*|వాన\S*|తేమ|గాలి")
_WEATHER_ALIASES = {
    "రాజమండ్రి": "Rajahmundry", "రాజమహేంద్రవరం": "Rajahmundry",
    "హైదరాబాద్": "Hyderabad", "హైదరాబాదు": "Hyderabad", "hyd": "Hyderabad",
    "విజయవాడ": "Vijayawada", "bezawada": "Vijayawada",
    "విశాఖపట్నం": "Visakhapatnam", "విశాఖ": "Visakhapatnam", "vizag": "Visakhapatnam",
    "గుంటూరు": "Guntur", "కాకినాడ": "Kakinada", "తిరుపతి": "Tirupati",
    "నెల్లూరు": "Nellore", "చెన్నై": "Chennai", "బెంగళూరు": "Bengaluru",
    "బెంగుళూరు": "Bengaluru", "ముంబై": "Mumbai", "ఢిల్లీ": "Delhi",
    "కొల్కతా": "Kolkata", "లండన్": "London", "దుబాయ్": "Dubai",
    "న్యూయార్క్": "New York", "పారిస్": "Paris", "టోక్యో": "Tokyo",
}


def _weather_intent(query):
    q = query.lower()
    if re.search(r"\b(?:gold|silver|petrol|diesel|cricket|stock|bitcoin|score|news)\b|బంగారం|వెండి|పెట్రోల్|డీజిల్|క్రికెట్", q):
        return False
    # Keep definitions, comparisons and coding questions on the ordinary AI path.
    if re.search(r"\b(?:explain|meaning|definition|difference|history|how to|code|python|api)\b|అంటే|ఎందుకు", q):
        return False
    if re.search(r"\bwhat (?:is|does) (?:the )?(?:weather|temperature|humidity|wind|rain)\??$", q):
        return False
    return bool(re.search(_WEATHER_TERMS, q))


def _weather_place(query):
    q = query.lower().strip()
    q = re.sub(r"\b(?:what|how|where)['’]s\b", " ", q)
    # Normalize common attached Telugu/Tenglish location suffixes before cleanup.
    for city, aliases in _CITY_ALIASES.items():
        for alias in aliases:
            q = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?:lo|లో)(?!\w)", city, q)
    q = re.sub(r"లో(?=\s|[?!.,]|$)", " ", q)
    q = re.sub(_WEATHER_TERMS, " ", q)
    filler = (r"\b(?:what|what's|whats|is|are|the|a|an|in|at|of|for|please|tell|me|show|give|"
              r"today|todays|today's|current|currently|live|now|right|conditions|condition|"
              r"chance|chances|probability|percent|percentage|will|it|be|there|does|do|"
              r"how|much|hot|cold|degrees|celsius|and|with|about|like|speed|direction|update|updates|report|"
              r"ivala|ivvala|ee|roju|eroju|eeroju|ippudu|enti|entha|ela|undhi|undi|undha|"
              r"untunda|untundha|untundi|untundhi|padutunda|paduthunda|padutundha|paduthundha|"
              r"padutundi|paduthundi|pade|padey|vastunda|vasthunda|cheppu|cheppava|chupinchu|kavali|ga|lo|ki|naa|maa|"
              r"daggara|ikkada|here|my|area|city|location|ra|bro)\b")
    q = re.sub(filler, " ", q)
    for word in ("ఈరోజు", "ఈ రోజు", "నేడు", "ఇప్పుడు", "ఎలా", "ఉంది", "ఉందా", "ఎంత", "చెప్పు", "చూపించు",
                 "పడుతుందా", "పడుతుందో", "వచ్చే", "కురుస్తుందా", "అవకాశం", "శాతం", "మా", "ఇక్కడ", "నగరంలో", "నగరం", "తో"):
        q = q.replace(word, " ")
    q = re.sub(r"[^\w\s,.'\-\u0c00-\u0c7f]", " ", q)
    q = re.sub(r"\s+", " ", q).strip(" ,.'-_")
    for alias, name in _WEATHER_ALIASES.items():
        q = re.sub(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", name, q, flags=re.I)
    # Only a genuinely absent place defaults. An unknown city must never become Rajahmundry.
    return q or "Rajahmundry", not bool(q)


@st.cache_data(show_spinner=False, ttl=300, max_entries=128)
def _weather_json(url):
    allowed = {"geocoding-api.open-meteo.com", "api.open-meteo.com"}
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in allowed:
        raise ValueError("Unsupported weather source")
    req = Request(url, headers={"User-Agent": "Veda-AI-Weather/60", "Accept": "application/json"})
    with urlopen(req, timeout=12) as response:
        if urlparse(response.url).scheme != "https" or urlparse(response.url).hostname not in allowed:
            raise ValueError("Unexpected weather redirect")
        raw = response.read(600001)
        if len(raw) > 600000:
            raise ValueError("Weather response too large")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Weather provider error")
    return data, _now_ist().isoformat()


def _weather_condition(code):
    return {
        0: "Clear sky / ఆకాశం నిర్మలం", 1: "Mainly clear / ఎక్కువగా నిర్మలం",
        2: "Partly cloudy / పాక్షికంగా మేఘాలు", 3: "Overcast / మేఘావృతం",
        45: "Fog / పొగమంచు", 48: "Rime fog / గడ్డకట్టే పొగమంచు",
        51: "Light drizzle / తేలికపాటి జల్లు", 53: "Moderate drizzle / మోస్తరు జల్లు",
        55: "Dense drizzle / దట్టమైన జల్లు", 56: "Light freezing drizzle", 57: "Dense freezing drizzle",
        61: "Slight rain / తేలికపాటి వర్షం", 63: "Moderate rain / మోస్తరు వర్షం",
        65: "Heavy rain / భారీ వర్షం", 66: "Light freezing rain", 67: "Heavy freezing rain",
        71: "Slight snow / తేలికపాటి మంచు", 73: "Moderate snow", 75: "Heavy snow",
        77: "Snow grains", 80: "Slight rain showers", 81: "Moderate rain showers",
        82: "Violent rain showers", 85: "Slight snow showers", 86: "Heavy snow showers",
        95: "Thunderstorm / ఉరుములతో వర్షం", 96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }.get(code, "Condition unavailable / పరిస్థితి అందుబాటులో లేదు")


def _weather_number(value, unit, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        return "Unavailable / అందుబాటులో లేదు"
    return f"{value:g}{unit}"


def weather_answer(query):
    # This feature deliberately promises only now + today, never a guessed historical/future forecast.
    if re.search(r"\b(?:tomorrow|yesterday|next|yesterdays|repu|ninna|week|month|historical)\b|రేపు|నిన్న|వచ్చే\s*(?:వారం|నెల)|\b\d{4}[-/]\d|\b\d{1,2}[-/]\d{1,2}\b|\b(?:19|20)\d{2}\b", query, re.I):
        return "Ee direct weather feature current conditions + ee roju forecast matrame. · ఈ ఫీచర్ ఇప్పుడు, ఈరోజు వాతావరణం కోసమే. · Ask for current weather or today's forecast with a city name. Other dates are not verified here."
    place, defaulted = _weather_place(query)
    if len(place) > 100:
        return "City peru matrame cheppu, e.g. Paris, France weather. · నగరం పేరు చెప్పు. · Please give one city, with state/country if needed."
    geo_url = _WEATHER_GEO + "?" + urlencode({"name": place, "count": 5, "language": "en", "format": "json"})
    try:
        geo, _ = _weather_json(geo_url)
        rows = [r for r in geo.get("results", []) if r.get("feature_code", "").startswith("PPL")]
    except Exception:
        return ("City lookup ippudu pani cheyyatledu. Weather numbers guess cheyyanu. · నగరం వివరాలు రాలేదు. · Location service unavailable; try again later.\n\n"
                "Source: Open-Meteo Geocoding · https://open-meteo.com/en/docs/geocoding-api")
    if not rows:
        return ("Aa city ni confirm cheyyalekapoyanu; Rajahmundry ki automatic ga marchaledu. · ఆ నగరం దొరకలేదు. · City not found. Try its English spelling plus state/country, e.g. London, United Kingdom weather.\n\n"
                "Source: Open-Meteo Geocoding · https://open-meteo.com/en/docs/geocoding-api")
    loc = rows[0]
    # If two large same-name places have similar populations, ask rather than pick one silently.
    if len(rows) > 1 and rows[1].get("population", 0) > max(1, loc.get("population", 0)) * 0.3:
        choices = list(dict.fromkeys(", ".join(str(r[k]) for k in ("name", "admin1", "country") if r.get(k)) for r in rows[:3]))
        if len(choices) > 1:
            return "Oke perutho cities unnayi. State/country tho malli adugu. · ఒకే పేరుతో నగరాలు ఉన్నాయి. · Which city? Add its state/country:\n\n" + "\n\n".join("- " + c for c in choices)
    label = ", ".join(dict.fromkeys(str(loc[k]) for k in ("name", "admin1", "country") if loc.get(k)))
    params = {
        "latitude": loc["latitude"], "longitude": loc["longitude"],
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
        "timezone": "auto", "forecast_days": 1, "temperature_unit": "celsius", "wind_speed_unit": "kmh",
        "precipitation_unit": "mm", "timeformat": "iso8601",
    }
    weather_url = _WEATHER_API + "?" + urlencode(params)
    try:
        data, fetched = _weather_json(weather_url)
        cur, daily = data.get("current", {}), data.get("daily", {})
        if not cur.get("time") or not daily.get("time") or data.get("utc_offset_seconds") is None:
            raise ValueError("Incomplete weather data")
        offset = timezone(timedelta(seconds=int(data["utc_offset_seconds"])))
        stamp = datetime.fromisoformat(cur["time"]).replace(tzinfo=offset)
        checked = datetime.fromisoformat(fetched)
        # Do not label stale/future or wrong-day payloads as current/today.
        if not -1800 <= (checked - stamp).total_seconds() <= 10800:
            raise ValueError("Weather timestamp is stale")
        if daily["time"][0] != checked.astimezone(offset).date().isoformat():
            raise ValueError("Today's forecast date not verified")
    except Exception:
        return (f"Weather ippudu verify kaaledu ({label}). Number guess cheyyanu. · వాతావరణం నిర్ధారించలేకపోయాను. · Weather service unavailable or data incomplete/stale. Try again later.\n\n"
                "Source: Open-Meteo · https://open-meteo.com/")
    def day(key):
        values = daily.get(key) or []
        return values[0] if values else None
    number = _weather_number
    lines = [f"**Weather / వాతావరణం: {label}**"]
    if defaulted:
        lines.append("City cheppaledu kabatti Rajahmundry chupisthunna. · నగరం చెప్పలేదు కాబట్టి రాజమండ్రి. · No city given: defaulting to Rajahmundry, not your GPS location.")
    else:
        lines.append("Matched city paina undi. Vere city aithe state/country kuda cheppu. · Matched location shown above; add state/country if it is not the one you meant.")
    lines.extend([
        f"**Now / ఇప్పుడు:** {_weather_condition(cur.get('weather_code'))}",
        f"Temperature / ఉష్ణోగ్రత: {number(cur.get('temperature_2m'), ' °C', -100, 65)}",
        f"Humidity / తేమ: {number(cur.get('relative_humidity_2m'), '%', 0, 100)}",
        f"Wind / గాలి: {number(cur.get('wind_speed_10m'), ' km/h', 0, 500)} · direction: {number(cur.get('wind_direction_10m'), '°', 0, 360)} (0° N, 90° E)",
        f"**Today / ఈరోజు ({daily['time'][0]}, {data.get('timezone', 'city local time')}):** {_weather_condition(day('weather_code'))}",
        f"Low / కనిష్ఠం: {number(day('temperature_2m_min'), ' °C', -100, 65)} · High / గరిష్ఠం: {number(day('temperature_2m_max'), ' °C', -100, 65)}",
        f"Rain/precipitation chance / వర్షపాతం అవకాశం (day's maximum): {number(day('precipitation_probability_max'), '%', 0, 100)}",
        f"Total precipitation forecast / అంచనా వర్షపాతం: {number(day('precipitation_sum'), ' mm', 0, 3000)}",
        f"Conditions time: {stamp.strftime('%d %b %Y, %I:%M %p')} ({data.get('timezone', 'city local time')}) · {stamp.astimezone(_IST).strftime('%d %b %Y, %I:%M %p IST')}",
        f"Fetched: {checked.strftime('%d %b %Y, %I:%M %p IST')}",
        f"Source: [Open-Meteo weather]({weather_url}) · [GeoNames places via Open-Meteo]({geo_url}) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)",
        "Idi model-based snapshot, weather-station measurement kaadu; automatic refresh ledu. · ఇవి మోడల్ అంచనాలు. · Model-based current conditions and forecast, not station observations or a rain guarantee. Precipitation may include snow. Today's maximum chance is NOT the chance for the remaining hours. Ask again to refresh (cache up to 5 minutes).",
    ])
    return "\n\n".join(lines)


def direct_live_answer(query):
    kind = live_kind(query)
    if not kind:
        return None
    if not live_search:
        return "Live internet OFF lo undi. Sidebar lo Live internet ON chesi malli adugu. · Turn on Live internet in the sidebar and ask again; I won't guess current rates, scores or weather."
    try:
        return {"gold": gold_answer, "silver": silver_answer, "fuel": fuel_answer, "cricket": cricket_answer, "weather": weather_answer}[kind](query)
    except Exception:
        return "Live source ippudu verify kaaledu. Malli try cheyyi. · Could not verify the live source right now; no number guessed."


LIVE_WORDS = ("rate", "price", "today", "now", "news", "score", "weather", "latest", "live", "current", "ivala", "ivvala", "ippudu", "entha", "enti", "match", "result", "stock", "search", "temperature", "vaartha", "varthalu", " vs ", " v ", "t20", "odi", "ipl", "cricket", "innings", "wicket", "overs", "jarugutunda", "jarugutundi", "gelichindi", "gelichaaru", "evaru gelicharu", "scorecard", "fixture", "schedule", "winner", "standings", "points table", "trending", "release", "box office")


def needs_live(text):
    t = text.lower()
    return bool(live_kind(text)) or any(w in t for w in LIVE_WORDS)


def web_context(query):
    """Free internet search (no Google quota). Returns a text block for the AI, or ''."""
    ql = query.lower()
    if any(w in ql for w in ("news", "vaartha", "varthalu", "headline", "breaking")):
        try:
            from ddgs import DDGS
            _q = re.sub(r"\b(ivala|ivalati|ivvala|ippudu|enti|entha|em|emi|vaartha|varthalu|cheppu|chupinchu|kavali|ki|ni|top)\b|[?!.]", " ", ql)
            _q = re.sub(r"\s+", " ", _q).strip()
            if _q in ("", "news", "latest news", "today news", "news today"):
                _q = "top news today India Andhra Pradesh Telangana"
            elif "india" not in _q:
                _q += " India"
            nres = DDGS().news(_q, max_results=8, region="in-en")
        except Exception:
            nres = []
        if nres:
            nl = [f"- {r.get('title','')} ({r.get('source','')}, {r.get('date','')}): {r.get('body','')} ({r.get('url','')})" for r in nres]
            return ("[LIVE NEWS HEADLINES fetched just now - summarize the top stories as a short list with the source name. "
                    "Use only these; prefer the newest dates and say if they look old; never invent news.]\n" + "\n".join(nl) + "\n[END OF NEWS]\n\nUser question: ")
    if re.search(r"\bvs\b|\bt20|\bodi\b|\bipl\b|cricket|score|match", ql) and "score" not in ql:
        query = query + " live score"
    from datetime import datetime
    query = re.sub(r"\b(ivala|ivvala|ippudu|entha|enti|cheppu|chupinchu|kavali)\b", " ", query, flags=re.I)
    query = re.sub(r"\s+", " ", query).strip()
    query += " " + _now_ist().strftime("%d %B %Y")
    res = []
    from ddgs import DDGS
    for _be in ("auto", "bing", "yahoo", "brave", "duckduckgo"):
        try:
            res = DDGS().text(query, max_results=5, region="in-en", backend=_be)
        except Exception:
            res = []
        if res:
            break
    if not res:
        return ""
    lines = [f"- {r.get('title','')}: {r.get('body','')} ({r.get('href','')})" for r in res]
    # also read the top pages, so exact numbers (rates, scores) are included
    import urllib.request
    for r in res[:3]:
        try:
            req = urllib.request.Request(r.get("href", ""), headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=6).read(400000).decode("utf-8", errors="ignore")
            html = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
            txt = re.sub(r"<[^>]+>", " ", html)
            txt = re.sub(r"\s+", " ", txt)
            keys = [m.start() for m in re.finditer(r"₹|Rs\.?|\b\d{1,3}/\d{1,3}\b|\d+ runs|overs|per gram|22K|24K", txt)]
            start = max(0, (keys[0] - 300) if keys else 0)
            lines.append(f"PAGE TEXT from {r.get('href','')}: {txt[start:start+2200]}")
        except Exception:
            continue
    return ("[LIVE WEB SEARCH RESULTS fetched just now - use them to answer with current facts. "
            "If they do not contain the exact answer, say so honestly and never invent numbers. "
            "Mention the source site name.]\n" + "\n".join(lines) + "\n[END OF SEARCH RESULTS]\n\nUser question: ")


def _voice_err_label(e):
    """v61 diagnostic: safe label only (category + exception class). Never includes the raw error text."""
    m = (type(e).__name__ + " " + str(e)).lower()
    if "429" in m or "resource_exhausted" in m or "quota" in m:
        cat = "quota or rate limit"
    elif "404" in m or "not_found" in m or "not found" in m:
        cat = "model not found"
    elif "400" in m or "invalid_argument" in m or "unsupported" in m:
        cat = "request rejected"
    elif "401" in m or "403" in m or "permission" in m or "api key" in m or "unauthenticated" in m:
        cat = "key or permission"
    elif "timeout" in m or "timed out" in m or "connect" in m:
        cat = "network or timeout"
    elif "index" in m or "inline_data" in m or "nonetype" in m or "list" in m:
        cat = "no audio returned"
    elif "500" in m or "503" in m or "unavailable" in m or "internal" in m:
        cat = "Google server error"
    else:
        cat = "other"
    return cat + " (" + type(e).__name__ + ")"


def play_voice(text):
    spoken = clean_for_speech(text)
    if not spoken:
        return
    try:
        with st.spinner("వాయిస్ సిద్ధమవుతోంది... · Preparing voice..."):
            if True:  # super natural voice is the default
                try:
                    st.audio(gemini_voice(spoken, VOICE_NAME), format="audio/wav", autoplay=True)
                    st.caption("🔎 Voice check: Gemini voice used (" + str(VOICE_NAME) + ")")  # v61 diagnostic
                    return
                except Exception as ge:
                    # v61 diagnostic: remember only a safe category + exception class (never the raw message)
                    st.session_state["voice_check_note"] = _voice_err_label(ge)
            audio = natural_voice(spoken, VOICE_GENDER)
        if not audio:
            raise RuntimeError("empty audio")
        st.audio(audio, format="audio/mp3", autoplay=True)
        st.caption("🔎 Voice check: backup voice used. Gemini problem: " + str(st.session_state.get("voice_check_note", "unknown")))  # v61 diagnostic
    except Exception as _e2:
        st.caption("🔎 Voice check: browser voice used. Problem: " + _voice_err_label(_e2))  # v61 diagnostic
        speak_text(spoken)  # fallback: browser voice


def copy_button(text):
    """Small Copy button under a reply - copies the text to the clipboard."""
    safe = json.dumps(text).replace("</", "<\\/")
    components.html(
        f"""<button id="cb" style="padding:3px 12px;border-radius:8px;border:1px solid #ddd;background:#fff;cursor:pointer;font-size:13px;">📋 Copy</button>
        <script>
        var t = {safe};
        function fb() {{
            var ta = document.createElement("textarea");
            ta.value = t; document.body.appendChild(ta); ta.select();
            document.execCommand("copy"); document.body.removeChild(ta);
        }}
        document.getElementById("cb").onclick = function() {{
            var btn = this;
            var done = function() {{ btn.innerText = "Copied ✅"; }};
            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(t).then(done).catch(function() {{ fb(); done(); }});
            }} else {{ fb(); done(); }}
        }};
        </script>""",
        height=36,
    )


def wants_image(text):
    """Does this message ask for a drawing/photo? Then route to the image maker automatically."""
    t = text.lower()
    kws = [
        "image", "photo", "picture", "draw", "paint", "sketch", "poster", "logo",
        "wallpaper", "meme", "chitram", "chitra", "bomma", "bOMMa",
        "gii", "geyi", "geyandi", "geyali", "geyava",
    ]
    return any(k in t for k in kws)


def generate_image(prompt_text):
    """Draw an image with a Gemini image model (Nano Banana). Returns (PNG bytes or None, error text).
    Asks the API key which image models it can actually use, then tries them."""
    errs = []
    candidates = []
    try:
        for m in client.models.list():
            short = (getattr(m, "name", "") or "").split("/")[-1]
            if "image" in short and "imagen" not in short:
                candidates.append(short)
    except Exception as e:
        errs.append(f"model list failed: {str(e)[:120]}")
    ordered = [m for m in ("gemini-3.1-flash-image", "gemini-2.5-flash-image") if m in candidates]
    for m in candidates:
        if m not in ordered:
            ordered.append(m)
    if not ordered:
        ordered = ["gemini-3.1-flash-image", "gemini-2.5-flash-image"]
    for model_name in ordered:
        try:
            resp = client.models.generate_content(model=model_name, contents=prompt_text)
            for cand in resp.candidates or []:
                for part in cand.content.parts:
                    if getattr(part, "inline_data", None) is not None:
                        return part.inline_data.data, None
            errs.append(f"{model_name}: no image in reply")
        except Exception as e:
            errs.append(f"{model_name}: {str(e)[:120]}")
            continue
    return None, " | ".join(errs) or f"no image models on this key (found: {', '.join(candidates) or 'none'})"


def transcribe_audio(audio_bytes, mime_type):
    """Turn the user's voice recording into text with Gemini."""
    resp = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    types.Part.from_text(
                        text=(
                            "Listen very carefully and transcribe EXACTLY what the person says, word for word. "
                            "The speaker is a Telugu person from India who casually mixes Telugu and English in one sentence. "
                            "Write Telugu words phonetically in Latin letters (example: 'maadi rajahmundry', 'nenu office ki veltunna'), "
                            "and English words in normal English. Do NOT translate, do NOT answer, do NOT add anything. "
                            "Output ONLY the transcription. "
                            "If you truly cannot understand anything, output exactly: [unclear]"
                        )
                    ),
                ],
            )
        ],
    )
    text = (resp.text or "").strip()
    return None if text in ("", "[unclear]") else text


def reply_to(user_text, attach_bytes=None, attach_mime=None, attach_name=None):
    """Show the user's message (with optional photo/PDF/file), then stream Veda AI's reply like ChatGPT."""
    is_image = bool(attach_mime and attach_mime.startswith("image/"))
    if not user_text:
        user_text = "ఈ ఫైల్ గురించి చెప్పు · Tell me about this file"
    st.session_state.messages.append({
        "role": "user",
        "text": user_text,
        "image": attach_bytes if is_image else None,
        "pdf": attach_bytes if attach_mime == "application/pdf" else None,
        "file_name": attach_name if (attach_bytes and not is_image) else None,
        "mime": attach_mime,
    })
    with st.chat_message("user"):
        if attach_bytes and is_image:
            st.image(attach_bytes, width=260)
        elif attach_bytes and attach_mime == "application/pdf":
            st.caption(f"📎 {attach_name}")
            st.pdf(attach_bytes, height=350)
        elif attach_bytes:
            st.caption(f"📎 {attach_name}")
        st.markdown(user_text)

    # Exact rate/score snapshots bypass AI rewriting, so quota errors cannot change numbers.
    if not attach_bytes and not re.search(r"https?://", user_text):
        with st.spinner("Live source check chesthunna... · Checking live source..."):
            direct_reply = direct_live_answer(user_text)
        if direct_reply is not None:
            with st.chat_message("assistant"):
                st.markdown(direct_reply)
                st.session_state.messages.append({"role": "model", "text": direct_reply})
                copy_button(direct_reply)
                if talk_mode:
                    play_voice(direct_reply)
                if st.button("🔊 Read aloud", key=f"speak_live_{len(st.session_state.messages)}"):
                    st.session_state.speak_idx = len(st.session_state.messages) - 1
                    st.rerun()
            return

    # Build a Gemini chat with the full history so it remembers the conversation
    # only the recent conversation goes to the AI - keeps replies fast and saves free quota
    recent = st.session_state.messages[:-1][-16:]
    history = [
        types.Content(
            role=m["role"],
            parts=[types.Part.from_text(text=("📷 " if m.get("image") else ("📎 " if m.get("file_name") else "")) + m["text"])],
        )
        for m in recent
    ]
    def make_chat(use_search, use_url=False, model=None):
        _tools = []
        if use_search:
            _tools.append(types.Tool(google_search=types.GoogleSearch()))  # live info
        if use_url:
            _tools.append(types.Tool(url_context=types.UrlContext()))  # read links
        cfg = types.GenerateContentConfig(system_instruction=_sys(), tools=_tools or None)
        return client.chats.create(model=model or MODEL, config=cfg, history=history)

    _all_urls = [u.rstrip(".,)") for u in re.findall(r"https?://\S+", user_text)]
    _yt_urls = [u for u in _all_urls if "youtube.com" in u or "youtu.be" in u]
    _web_urls = [u for u in _all_urls if u not in _yt_urls]
    _m = re.match(r"\s*(remember|gurthu\s*pettuko|gurthupettuko)\b[:,\- ]*(.+)", user_text, flags=re.I | re.S)
    if _m:
        st.session_state.memory = ((st.session_state.get("memory") or "") + "\n- " + _m.group(2).strip()).strip()
    _web_ctx = ""
    _live_failed = False
    if live_search and not attach_bytes and not _all_urls and needs_live(user_text):
        with st.spinner("ఇంటర్నెట్ లో వెతుకుతోంది... · Searching the web..."):
            try:
                _web_ctx = web_context(user_text)
            except Exception:
                _web_ctx = ""
        _live_failed = not _web_ctx
    chat = make_chat(False, bool(_web_urls))

    # Get Veda AI's reply - streamed word by word like ChatGPT
    # If Google is busy (503), quietly retry a few times before showing an error
    with st.chat_message("assistant"):
        try:
            full_reply = None
            last_err = None
            use_search = False
            search_fell_back = False
            search_tried = False
            search_models = [m for m in text_models() if m != MODEL][:4]
            chat_models = [m for m in text_models() if m != MODEL]
            for attempt in range(12):
                try:
                    msg_parts = []
                    if attach_bytes and is_image:
                        msg_parts.append(types.Part.from_bytes(data=attach_bytes, mime_type=attach_mime))
                    elif attach_bytes and attach_mime == "application/pdf":
                        msg_parts.append(types.Part.from_bytes(data=attach_bytes, mime_type="application/pdf"))
                    elif attach_bytes:
                        try:
                            file_text = attach_bytes.decode("utf-8", errors="ignore")
                            msg_parts.append(types.Part.from_text(
                                text=f"--- File: {attach_name} ---\n{file_text[:200000]}\n--- End of file ---"
                            ))
                        except Exception:
                            msg_parts.append(types.Part.from_bytes(data=attach_bytes, mime_type=attach_mime or "application/octet-stream"))
                    for _yu in _yt_urls[:1]:
                        msg_parts.append(types.Part(file_data=types.FileData(file_uri=_yu)))
                    msg_parts.append(types.Part.from_text(text=_web_ctx + ("[Current data could not be fetched. Do not answer current rates, scores or news from memory. Say the live check failed.]\n" if _live_failed else "") + user_text))

                    def reply_stream():
                        for chunk in chat.send_message_stream(msg_parts):
                            if chunk.text:
                                yield chunk.text
                    full_reply = st.write_stream(reply_stream())
                    break
                except Exception as e:
                    last_err = e
                    msg = str(e)
                    if use_search and search_tried and ("404" in msg or "NOT_FOUND" in msg) and search_models:
                        chat = make_chat(True, bool(_web_urls), search_models.pop(0))
                        continue
                    if use_search and search_tried and ("404" in msg or "NOT_FOUND" in msg):
                        use_search = False
                        search_fell_back = True
                        search_err = msg[:160]
                        chat = make_chat(False)
                        continue
                    if ("503" in msg or "UNAVAILABLE" in msg) and attempt < 3:
                        time.sleep(3 * (attempt + 1))
                        continue
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        if use_search and search_models:
                            # search quota busy on this model - try another model for live search
                            _alt = search_models.pop(0)
                            search_tried = True
                            chat = make_chat(True, bool(_web_urls), _alt)
                            continue
                        if use_search:
                            # live-search free quota busy everywhere - answer normally this once, no crash
                            use_search = False
                            search_fell_back = True
                            search_err = msg[:160]
                            chat = make_chat(False)
                            continue
                        if chat_models:
                            # this model's free quota is empty - switch to another model your key can use
                            chat = make_chat(False, False, chat_models.pop(0))
                            continue
                        if attempt < 3:
                            time.sleep(5)
                            continue
                    if ("404" in msg or "NOT_FOUND" in msg) and chat_models:
                        chat = make_chat(False, False, chat_models.pop(0))
                        continue
                    raise
            if full_reply is None:
                raise last_err
            st.session_state.messages.append({"role": "model", "text": full_reply})
            if search_fell_back:
                st.caption("⚠️ Live search ఇప్పుడు busy (free quota) - ఈ answer live data లేకుండా వచ్చింది. 12:30 తర్వాత మళ్ళీ అడగండి · Live search quota busy, this answer has no live data. Ask again after 12:30.")
                st.caption(f"Technical detail: {search_err}")
            if len(full_reply) > 500:  # only document-length replies get the PDF button
                try:
                    st.download_button(
                        "📄 PDF గా download · Download as PDF",
                        data=make_pdf(full_reply),
                        file_name="veda-ai-reply.pdf",
                        mime="application/pdf",
                        key=f"dl_live_{len(st.session_state.messages)}",
                    )
                except Exception:
                    pass
            if _web_ctx:
                st.caption("🌐 Live web search ఉపయోగించాను · Used live web search")
            elif _live_failed:
                st.caption("⚠️ Live source verify kaaledu. Current numbers guess cheyyakudadhu. · Live check failed; current numbers are not verified.")
            if _m:
                st.caption("🧠 గుర్తుపెట్టుకున్నాను · Remembered")
            copy_button(full_reply)
            if talk_mode:
                play_voice(full_reply)
            if st.button("🔊 Read aloud", key=f"speak_live_{len(st.session_state.messages)}"):
                st.session_state.speak_idx = len(st.session_state.messages) - 1
                st.rerun()
        except Exception as e:
            st.error(
                "ఏదో తప్పు జరిగింది / Something went wrong:\n\n"
                f"`{e}`\n\n"
                "ఫ్రీ లిమిట్ అయిపోయి ఉండవచ్చు - ప్రతిరోజూ మధ్యాహ్నం 12:30 కి reset అవుతుంది, అప్పుడు మళ్ళీ ప్రయత్నించండి.\n\n"
                "You may have hit the free limit - it resets every day around 12:30 PM, try again after that."
            )


# 💡 Suggestion chips on an empty chat
if not st.session_state.messages:
    st.caption("ఇవి try చేయండి · Try one of these 👇")
    _chips = [
        ("💰 Gold rate", "today gold rate entha?"),
        ("😂 Joke", "oka manchi Telugu joke cheppu"),
        ("📰 News", "ivala top news enti?"),
        ("💼 Resume tips", "DevOps resume ela improve cheyyali?"),
    ]
    _cols = st.columns(2)
    for _n, (_label, _q) in enumerate(_chips):
        if _cols[_n % 2].button(_label, key=f"chip_{_n}", use_container_width=True):
            st.session_state.pending = {"text": _q}
            st.rerun()

# Show the conversation so far as chat bubbles
_last_user_idx = max([j for j, m in enumerate(st.session_state.messages) if m["role"] == "user"], default=-1)
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        if msg.get("image"):
            st.image(msg["image"], width=260)
        elif msg.get("pdf"):
            st.caption(f"📎 {msg['file_name']}")
            st.pdf(msg["pdf"], height=350)
        elif msg.get("file_name"):
            st.caption(f"📎 {msg['file_name']}")
        if msg["role"] == "model":
            shown = re.sub(r"<script.*?</script>", "", msg["text"], flags=re.S | re.I)
            st.markdown(shown, unsafe_allow_html=True)
        elif st.session_state.get("edit_idx") == i:
            new_text = st.text_area("✏️ Edit message", value=msg["text"], key=f"edit_text_{i}")
            ec1, ec2 = st.columns(2)
            if ec1.button("Send ➤", key=f"edit_send_{i}", use_container_width=True) and new_text.strip():
                st.session_state.pending = {
                    "text": new_text.strip(),
                    "bytes": msg.get("image") or msg.get("pdf"),
                    "mime": msg.get("mime"),
                    "name": msg.get("file_name"),
                }
                st.session_state.messages = st.session_state.messages[:i]
                st.session_state.edit_idx = None
                st.rerun()
            if ec2.button("Cancel", key=f"edit_cancel_{i}", use_container_width=True):
                st.session_state.edit_idx = None
                st.rerun()
        else:
            st.markdown(msg["text"])
            if i == _last_user_idx and not msg["text"].startswith("🎨 "):
                if st.button("✏️ Edit", key=f"edit_{i}"):
                    st.session_state.edit_idx = i
                    st.rerun()
        if msg["role"] == "model" and len(msg["text"]) > 500:  # documents only
            try:
                st.download_button(
                    "📄 PDF గా download · Download as PDF",
                    data=make_pdf(msg["text"]),
                    file_name="veda-ai-reply.pdf",
                    mime="application/pdf",
                    key=f"dl_{i}",
                )
            except Exception:
                pass
        if msg["role"] == "model" and not msg["text"].startswith("🎨 "):
            copy_button(msg["text"])
            if st.button("🔊 Read aloud", key=f"speak_{i}"):
                st.session_state.speak_idx = i
                st.rerun()
            if st.session_state.get("speak_idx") == i:
                st.session_state.speak_idx = None
                play_voice(msg["text"])
            if i == len(st.session_state.messages) - 1 and i >= 1:
                if st.button("🔄 Regenerate", key=f"regen_{i}"):
                    prev = st.session_state.messages[i - 1]
                    if prev["role"] == "user" and not prev["text"].startswith("🎨 "):
                        st.session_state.pending = {
                            "text": prev["text"],
                            "bytes": prev.get("image") or prev.get("pdf"),
                            "mime": prev.get("mime"),
                            "name": prev.get("file_name"),
                        }
                        st.session_state.messages = st.session_state.messages[:i - 1]
                        st.rerun()

# 🎙️ Mic + typing + files in one box - the mic sits right next to the send button
prompt = st.chat_input(
    "Veda AI తో మాట్లాడండి... · Talk to Veda AI...",
    accept_audio=True,
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "webp", "gif", "pdf", "txt", "md", "csv", "json", "py"],
)
if prompt:
    if (image_mode or wants_image(getattr(prompt, "text", "") or "")) and getattr(prompt, "text", None) and not getattr(prompt, "files", None) and getattr(prompt, "audio", None) is None:
        img_prompt = prompt.text
        st.session_state.messages.append({"role": "user", "text": "🎨 " + img_prompt})
        with st.chat_message("user"):
            st.markdown(img_prompt)
        with st.chat_message("assistant"):
            with st.spinner("గీస్తోంది... · Drawing..."):
                img_bytes, img_err = generate_image(img_prompt)
            if img_bytes:
                st.image(img_bytes)
                st.download_button("💾 Image download", data=img_bytes, file_name="veda-ai-image.png", mime="image/png", key=f"img_{len(st.session_state.messages)}")
                st.session_state.messages.append({"role": "model", "text": f"🎨 (image) {img_prompt}"})
            else:
                st.error(
                    "ఇప్పుడు చిత్రం గీయలేకపోయాను - image free limit అయిపోయి ఉండవచ్చు (ప్రతిరోజూ మధ్యాహ్నం 12:30 కి reset). కొద్దిసేపు ఆగి మళ్ళీ ప్రయత్నించండి.\n\n"
                    "Couldn't draw right now - the image free limit may be used up (it resets around 12:30 PM every day). Wait a little and try again."
                )
                if img_err:
                    st.caption(f"Technical detail: {img_err}")
    elif getattr(prompt, "files", None):
        up = prompt.files[0]
        reply_to(prompt.text or "", up.read(), getattr(up, "type", None) or "", getattr(up, "name", "file"))
    elif getattr(prompt, "audio", None) is not None:
        audio_bytes = prompt.audio.read()
        audio_mime = getattr(prompt.audio, "type", None) or "audio/wav"
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("వినిపిస్తోంది... · Listening..."):
                try:
                    heard = transcribe_audio(audio_bytes, audio_mime)
                except Exception:
                    heard = None
            if heard:
                reply_to(heard)
            else:
                st.warning(
                    "సరిగ్గా వినపడలేదు - మళ్ళీ చెప్పండి 😅\n\n"
                    "Couldn't hear that clearly - please say it again 😅"
                )
    elif getattr(prompt, "text", None):
        reply_to(prompt.text)


# Run a queued request (suggestion chip / regenerate / edited message)
_pending = st.session_state.pop("pending", None)
if _pending:
    reply_to(_pending["text"], _pending.get("bytes"), _pending.get("mime"), _pending.get("name"))
