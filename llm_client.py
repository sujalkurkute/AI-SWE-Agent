"""
LLM Client - wraps the Groq API so the rest of the agent doesn't need to
know API details. Reads the key from a .env file (never hardcode it).
"""
import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # loads variables from a .env file in this folder into the environment

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not found. Create a .env file in this folder with:\n"
                "  GROQ_API_KEY=your_key_here"
            )
        _client = Groq(api_key=api_key)
    return _client


def ask_llm(prompt: str, system: str = "", model: str = "openai/gpt-oss-120b") -> str:
    """Send a prompt to the LLM and return its text response."""
    client = get_client()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,  # low temperature = more focused, less "creative" for code tasks
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    # Quick sanity test - requires GROQ_API_KEY to be set in .env
    reply = ask_llm("Say 'Hello, agent is connected!' and nothing else.")
    print(reply)