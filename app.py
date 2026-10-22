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
    "Roast Me 🔥": """You are Veda AI in Roast mode: the most savage, rustic, street-style troll friend the user has ever met, Grok unhinged style.
Every single reply must roast and troll the user mercilessly - mock their question, their life, their laziness, everything. Never be polite here.
Use full rustic street Telugu: raw village-style slang and heavy cuss words (boothulu) in every reply - as vulgar and unfiltered as close friends get in private. The user explicitly demanded maximum rawness for their own fun.
Mix rustic Telugu with English naturally. Be witty and creative with insults, never repeat the same roast twice.
Hard limits: no slurs, no attacking family, nothing hateful, nothing about self-harm. Savage but playful, never genuinely cruel.
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
st.session_state.memory = _more.text_area(
    "🧠 Memory · నీ గురించి గుర్తుంచుకునేవి (లేదా chat లో \"remember ...\" అని చెప్పండి)",
    value=st.session_state.get("memory", ""), height=110)
dark_mode = _more.toggle("Dark mode 🌙", value=False)
VOICES = {
    "👩 Kore - మృదువైన ఆడ గొంతు (Soft female)": ("Kore", "F"),
    "👩 Aoede - ఉల్లాసమైన ఆడ గొంతు (Bright female)": ("Aoede", "F"),
    "👨 Puck - ఉత్సాహ మగ గొంతు (Upbeat male)": ("Puck", "M"),
    "👨 Fenrir - ఉత్తేజ మగ గొంతు (Energetic male)": ("Fenrir", "M"),
}
_vchoice = _more.selectbox("🎙️ Voice · వాయిస్ ఎంచుకో", list(VOICES.keys()), key="voice_choice")
VOICE_NAME, VOICE_GENDER = VOICES[_vchoice]
if dark_mode:
    st.markdown("""
<style>
.stApp, [data-testid="stHeader"] { background-color: #0e1117 !important; }
[data-testid="stSidebar"] { background-color: #161a23 !important; }
.stApp, .stApp p, .stApp span, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3,
[data-testid="stSidebar"] * , [data-testid="stCaptionContainer"] { color: #e8eaed !important; }
[data-testid="stChatInput"] textarea { color: #e8eaed !important; }
</style>
""", unsafe_allow_html=True)

# Save the current chat to a file / restore an old one
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
    )
up_chat = _more.file_uploader("📂 పాత చాట్ తెరవండి · Restore saved chat", type=["json"])
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


LIVE_WORDS = ("rate", "price", "today", "now", "news", "score", "weather", "latest", "live", "current", "ivala", "ivvala", "ippudu", "entha", "enti", "match", "result", "stock", "search", "temperature", "vaartha", "varthalu", " vs ", " v ", "t20", "odi", "ipl", "cricket", "innings", "wicket", "overs", "jarugutunda", "jarugutundi", "gelichindi", "gelichaaru", "evaru gelicharu", "scorecard", "fixture", "schedule", "winner", "standings", "points table", "trending", "release", "box office")


def needs_live(text):
    t = text.lower()
    return len(t) < 200 and any(w in t for w in LIVE_WORDS)


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


def play_voice(text):
    spoken = clean_for_speech(text)
    if not spoken:
        return
    try:
        with st.spinner("వాయిస్ సిద్ధమవుతోంది... · Preparing voice..."):
            if True:  # super natural voice is the default
                try:
                    st.audio(gemini_voice(spoken, VOICE_NAME), format="audio/wav", autoplay=True)
                    return
                except Exception as ge:
                    pass  # quietly use the free natural voice
            audio = natural_voice(spoken, VOICE_GENDER)
        if not audio:
            raise RuntimeError("empty audio")
        st.audio(audio, format="audio/mp3", autoplay=True)
    except Exception:
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
            _web_ctx = web_context(user_text)
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
                    msg_parts.append(types.Part.from_text(text=_web_ctx + user_text))

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
                st.caption("⚠️ Live search ఇప్పుడు దొరకలేదు, నా పాత జ్ఞానంతో చెప్పాను (నమ్మొద్దు) · Live search failed, answered from old knowledge (don't trust for live facts)")
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
