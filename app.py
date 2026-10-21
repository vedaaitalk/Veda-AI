# ============================================
# Veda AI - your own ChatGPT-style chat app
# Built with Streamlit + Google Gemini (free)
# ============================================

import os
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


st.set_page_config(page_title="Veda AI", page_icon="🤖")
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

# Mode picker in the sidebar
mode = st.sidebar.radio("Mode ఎంచుకోండి · Pick a mode", list(MODES.keys()))
SYSTEM_PROMPT = MODES[mode]

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


def reply_to(user_text):
    """Show the user's message, then stream Veda AI's reply like ChatGPT."""
    st.session_state.messages.append({"role": "user", "text": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    # Build a Gemini chat with the full history so it remembers the conversation
    history = [
        types.Content(role=m["role"], parts=[types.Part.from_text(text=m["text"])])
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
                    def reply_stream():
                        for chunk in chat.send_message_stream(user_text):
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
for msg in st.session_state.messages:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["text"])

# 🎙️ Mic - talk instead of typing (works in Telugu + English)
audio = st.audio_input("🎙️ మాట్లాడండి · Speak to Veda AI")
if audio is not None:
    audio_bytes = audio.read()
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

# Chat input box at the bottom
user_text = st.chat_input("Veda AI తో మాట్లాడండి... · Talk to Veda AI...")
if user_text:
    reply_to(user_text)
