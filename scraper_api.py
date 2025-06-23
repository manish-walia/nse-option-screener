from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import random

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/option-chain/{symbol}")
def get_option_chain(symbol: str):
    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Mozilla/5.0 (X11; Linux x86_64)"
        ]),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com"
    }

    session = requests.Session()
    session.headers.update(headers)

    # Warm up
    warmup = session.get("https://www.nseindia.com", timeout=5)
    if warmup.status_code != 200:
        return {"error": "Warmup failed", "status": warmup.status_code}

    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    response = session.get(url, timeout=10)

    if response.status_code != 200:
        return {"error": f"NSE returned status {response.status_code}"}

    return response.json()
