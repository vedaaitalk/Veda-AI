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
    import re
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
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

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
speak_replies = st.sidebar.toggle("Replies గట్టిగా చదువు 🔊 · Read replies aloud", value=False)

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


def transcribe_audio(audio_bytes):
    """Turn the user's voice recording into text with Gemini."""
    resp = client.models.generate_content(
        model=MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
                    types.Part.from_text(
                        text=(
                            "Transcribe exactly what the person says in this audio. "
                            "They speak Telugu and/or English (or a mix). "
                            "Output ONLY the transcription, nothing else. "
                            "If you cannot understand it, output exactly: [unclear]"
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
    history = [
        types.Content(
            role=m["role"],
            parts=[types.Part.from_text(text=("📷 " if m.get("image") else ("📎 " if m.get("file_name") else "")) + m["text"])],
        )
        for m in st.session_state.messages[:-1]  # everything before this message
    ]
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
        history=history,
    )

    # Get Veda AI's reply - streamed word by word like ChatGPT
    # If Google is busy (503), quietly retry a few times before showing an error
    with st.chat_message("assistant"):
        try:
            full_reply = None
            last_err = None
            for attempt in range(4):
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
                    msg_parts.append(types.Part.from_text(text=user_text))

                    def reply_stream():
                        for chunk in chat.send_message_stream(msg_parts):
                            if chunk.text:
                                yield chunk.text
                    full_reply = st.write_stream(reply_stream())
                    break
                except Exception as e:
                    last_err = e
                    if ("503" in str(e) or "UNAVAILABLE" in str(e)) and attempt < 3:
                        time.sleep(3 * (attempt + 1))
                        continue
                    raise
            if full_reply is None:
                raise last_err
            st.session_state.messages.append({"role": "model", "text": full_reply})
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
            if speak_replies:
                speak_text(full_reply)
        except Exception as e:
            st.error(
                "ఏదో తప్పు జరిగింది / Something went wrong:\n\n"
                f"`{e}`\n\n"
                "ఫ్రీ లిమిట్ అయిపోయి ఉండవచ్చు, కొద్దిసేపు ఆగి మళ్ళీ ప్రయత్నించండి.\n\n"
                "You may have hit the free limit - wait a little and try again."
            )


# Show the conversation so far as chat bubbles
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
        else:
            st.markdown(msg["text"])
        if msg["role"] == "model":
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

# 🎙️ Mic + typing in one box - the mic sits right next to the send button
prompt = st.chat_input(
    "Veda AI తో మాట్లాడండి... · Talk to Veda AI...",
    accept_audio=True,
    accept_file=True,
    file_type=["jpg", "jpeg", "png", "webp", "gif", "pdf", "txt", "md", "csv", "json", "py"],
)
if prompt:
    if getattr(prompt, "files", None):
        up = prompt.files[0]
        reply_to(prompt.text or "", up.read(), getattr(up, "type", None) or "", getattr(up, "name", "file"))
    elif getattr(prompt, "audio", None) is not None:
        audio_bytes = prompt.audio.read()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("వినిపిస్తోంది... · Listening..."):
                try:
                    heard = transcribe_audio(audio_bytes)
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
