# ============================================
# Veda AI - your own ChatGPT-style chat app
# Built with Streamlit + Google Gemini (free)
# ============================================

import os
import streamlit as st
from google import genai
from google.genai import types

# ---------- Settings you can change ----------
MODEL = "gemini-2.5-flash"  # free-tier model; if Google renames it, change only this line

# Veda AI's personality. Edit this to change how your assistant behaves.
SYSTEM_PROMPT = """You are Veda AI, a friendly and helpful personal AI assistant.
You answer clearly and simply. The user speaks Telugu and English,
so reply in whichever language the user uses, or a natural mix of both.
You were built by Vedavyas as his own AI assistant."""

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

    # Get Veda AI's reply
    with st.chat_message("assistant"):
        try:
            with st.spinner("ఆలోచిస్తున్నాను... · Thinking..."):
                response = chat.send_message(user_text)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "model", "text": response.text})
        except Exception as e:
            st.error(
                "ఏదో తప్పు జరిగింది / Something went wrong:\n\n"
                f"`{e}`\n\n"
                "ఫ్రీ లిమిట్ అయిపోయి ఉండవచ్చు, కొద్దిసేపు ఆగి మళ్ళీ ప్రయత్నించండి.\n\n"
                "You may have hit the free limit - wait a little and try again."
            )
