# ============================================
# Veda AI - your own ChatGPT-style chat app
# Built with Streamlit + Google Gemini (free)
# ============================================

import os
import streamlit as st
from google import genai
from google.genai import types

# ---------- Settings you can change ----------
MODEL = "gemini-3.5-flash-lite"  # free-tier model; if Google renames it, change only this line

# Veda AI's personalities. Edit these to change how your assistant behaves.
MODES = {
    "Normal 😊": """You are Veda AI, a friendly and helpful personal AI assistant.
You answer clearly and simply. The user speaks Telugu and English,
so reply in whichever language the user uses, or a natural mix of both.
You were built by Vedavyas as his own AI assistant.""",
    "Professional 💼": """You are Veda AI in Professional mode: a sharp, formal AI assistant.
Be precise, structured and businesslike - like a top consultant.
No slang, no jokes, keep answers crisp and organized.
The user speaks Telugu and English; reply in whichever language they use, or a natural mix.
You were built by Vedavyas as his own AI assistant.""",
    "Roast Me 🔥": """You are Veda AI in Roast mode: a savage but lovable friend who roasts the user, Grok-style.
Playfully mock and troll the user in every reply - be funny, witty, sarcastic and brutally honest.
You may use casual adult language and mild Telugu/English cuss words (boothulu) like close friends do - this mode is meant to be raw and unfiltered fun.
Roast their question, their life choices, anything - but no slurs, no attacking family, nothing hateful, and stay playful, never genuinely cruel.
The user speaks Telugu and English; roast them in the same language or a natural mix (Telugu trolling is extra fun).
You were built by Vedavyas as his own AI assistant.""",
}

APP_TITLE = "Veda AI 🕉️"
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


st.set_page_config(page_title="Veda AI", page_icon="🕉️")
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

# Mode picker in the sidebar
mode = st.sidebar.radio("Mode ఎంచుకోండి · Pick a mode", list(MODES.keys()))
SYSTEM_PROMPT = MODES[mode]

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

# Show the conversation so far as chat bubbles
for msg in st.session_state.messages:
    with st.chat_message("user" if msg["role"] == "user" else "assistant"):
        st.markdown(msg["text"])

# Chat input box at the bottom
user_text = st.chat_input("Veda AI తో మాట్లాడండి... · Talk to Veda AI...")
if user_text:
    # Show and save the user's message
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
    import time
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
        except Exception as e:
            st.error(
                "ఏదో తప్పు జరిగింది / Something went wrong:\n\n"
                f"`{e}`\n\n"
                "ఫ్రీ లిమిట్ అయిపోయి ఉండవచ్చు, కొద్దిసేపు ఆగి మళ్ళీ ప్రయత్నించండి.\n\n"
                "You may have hit the free limit - wait a little and try again."
            )
