import google.generativeai as genai
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def check_async():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("No API key")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-flash-latest")
    chat = model.start_chat()
    
    if hasattr(chat, 'send_message_async'):
        print("✅ send_message_async exists")
    else:
        print("❌ send_message_async does NOT exist")

if __name__ == "__main__":
    asyncio.run(check_async())
