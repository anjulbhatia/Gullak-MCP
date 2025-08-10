import asyncio
import json
import re
from typing import Annotated, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import INVALID_PARAMS

import cachetools
import os
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Rich Tool Description model ---
class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: Optional[str] = None

# --- MCP Setup ---
mcp = FastMCP(
    "GullakAI MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Cache for Expense/Budget data (per user) ---
expense_cache = cachetools.TTLCache(maxsize=1000, ttl=60*60*24*7)  # 7 days TTL
CACHE_LOCK = asyncio.Lock()

def get_user_state(user_id: str) -> dict:
    if user_id not in expense_cache:
        expense_cache[user_id] = {
            "budgets": {},
            "expenses": [],
            "debts_bills": []
        }
    return expense_cache[user_id]

def save_user_state(user_id: str, state: dict):
    expense_cache[user_id] = state

# --- Load purchasing power data ---
with open("purchasingpower.json", "r") as f:
    purchasing_power_json = json.load(f)

purchasing_power_data = purchasing_power_json.get("cities", [])

# --- Utils ---
def normalize_language(lang: str) -> str:
    if not lang:
        return "en"
    lang = lang.lower()
    if lang.startswith("hi"):
        return "hi"
    if lang.startswith("en"):
        return "en"
    return "en"

def extract_cities_from_query(query: str):
    query = query.lower()
    words = re.findall(r"[a-zA-Z]+", query)
    matched_cities = []
    for city in purchasing_power_data:
        city_lower = city["city"].lower()
        for w in words:
            if w in city_lower and city not in matched_cities:
                matched_cities.append(city)
                if len(matched_cities) == 2:
                    return matched_cities
    return matched_cities

# --- Dummy call_puch_llm to simulate AI response ---
async def call_puch_llm(prompt: str) -> str:
    # Replace this with your actual LLM call
    await asyncio.sleep(0.1)
    return f"[AI response simulated for prompt]: {prompt[:200]}..."

# --- Tools ---

@mcp.tool
async def validate() -> str:
    return MY_NUMBER

CoreFinanceQADescription = RichToolDescription(
    description="Conversational AI tool that answers personal finance questions simply and clearly in multiple languages.",
    use_when="Use this tool when users want quick, actionable advice on loans, savings, budgeting, investing, and other finance topics.",
    side_effects="Returns concise and easy-to-understand financial explanations tailored to user queries."
)

@mcp.tool(description=CoreFinanceQADescription.model_dump_json())
async def core_finance_qa(
    query: Annotated[str, Field(description="User's personal finance question")],
    language: Annotated[str, Field(description="Language code, e.g., 'en' or 'hi'")] = "en"
) -> str:
    lang = normalize_language(language)
    prompt = f"Answer this personal finance question clearly and simply in {lang}:\n\n{query}\n\nKeep it brief and actionable."
    return await call_puch_llm(prompt)

FinancialNewsSimplifierDescription = RichToolDescription(
    description="AI-powered tool to simplify and summarize complex financial news or jargon into easy-to-understand language.",
    use_when="Use when users provide financial news text, reports, or articles they want explained in simple terms.",
    side_effects="Outputs summarized news with jargon explained and key points highlighted."
)

@mcp.tool(description=FinancialNewsSimplifierDescription.model_dump_json())
async def financial_news_simplifier(
    news_text: Annotated[str, Field(description="Raw financial news text")],
    language: Annotated[str, Field(description="Language code")] = "en"
) -> str:
    lang = normalize_language(language)
    prompt = f"Summarize this financial news article in simple {lang} language, explaining any jargon:\n\n{news_text}\n\nSummary:"
    return await call_puch_llm(prompt)

ExpenseBudgetMonitorDescription = RichToolDescription(
    description="Expense and budget management tool allowing users to set budgets, log expenses, and track debts or bills via simple commands.",
    use_when="Use when users want to manage monthly budgets, record spending, and track debts or bills through chat commands.",
    side_effects="Stores and updates user financial data in local cache; returns status messages and alerts when budgets are exceeded."
)

@mcp.tool(description=ExpenseBudgetMonitorDescription.model_dump_json())
async def expense_budget_monitor(
    user_id: Annotated[str, Field(description="User unique ID (WhatsApp phone number)")],
    command: Annotated[str, Field(description="Commands: set budget, spent, owe, bill, summary")]
) -> str:
    """
    Commands supported:
      - set budget <month> <Category1> <amount1> <Category2> <amount2> ...
      - spent <amount> on <Category>
      - owe <person/description> <amount>
      - bill <description> <amount> due YYYY-MM-DD
      - summary [month]   -> returns budget / spend summary for month
    """
    command_orig = command.strip()
    command_lower = command_orig.lower()

    async with CACHE_LOCK:
        state = get_user_state(user_id)

        if command_lower.startswith("set budget"):
            parts = command_lower.split()
            if len(parts) < 5 or (len(parts) - 3) % 2 != 0:
                return "⚠️ Format error. Use: set budget <month> <category1> <amount1> ..."
            month = parts[2].capitalize()
            cats_amts = parts[3:]
            for i in range(0, len(cats_amts), 2):
                cat = cats_amts[i].capitalize()
                try:
                    amt = float(cats_amts[i + 1])
                except Exception:
                    return f"⚠️ Invalid amount: {cats_amts[i + 1]}"
                if month not in state["budgets"]:
                    state["budgets"][month] = {}
                state["budgets"][month][cat] = amt
            save_user_state(user_id, state)
            return f"✅ Budget set for {month}: " + ", ".join(f"{c} ₹{a}" for c, a in state["budgets"][month].items())

        if command_lower.startswith("spent"):
            m = re.match(r"spent\s+(\d+\.?\d*)\s+on\s+(.+)", command_lower)
            if not m:
                return "⚠️ Format error. Use: spent <amount> on <category>"
            amount = float(m.group(1))
            category = m.group(2).strip().capitalize()
            month = datetime.utcnow().strftime("%B")
            if month not in state["budgets"] or category not in state["budgets"][month]:
                return f"⚠️ No budget found for {category} in {month}. Set it first using 'set budget {month} <Category> <amount>'"
            state["expenses"].append({
                "month": month,
                "category": category,
                "amount": amount,
                "date": datetime.utcnow().isoformat()
            })
            total_spent = sum(e["amount"] for e in state["expenses"] if e["month"] == month and e["category"] == category)
            budget_amt = state["budgets"][month][category]
            save_user_state(user_id, state)
            if total_spent > budget_amt:
                over = total_spent - budget_amt
                return f"⚠️ You have exceeded your {category} budget by ₹{over:.2f}. Total spent: ₹{total_spent:.2f}."
            return f"✅ Recorded spending ₹{amount:.2f} on {category}. Total spent: ₹{total_spent:.2f} / ₹{budget_amt:.2f}."

        if command_lower.startswith("owe"):
            m = re.match(r"owe\s+(.+?)\s+(\d+\.?\d*)$", command_lower)
            if not m:
                return "⚠️ Format: owe <person/description> <amount>"
            desc = m.group(1).strip()
            amt = float(m.group(2))
            state["debts_bills"].append({
                "type": "debt",
                "description": desc,
                "amount": amt,
                "due_date": None,
                "is_paid": False,
                "created_at": datetime.utcnow().isoformat()
            })
            save_user_state(user_id, state)
            return f"✅ Debt recorded: Owe {desc} ₹{amt:.2f}."

        if command_lower.startswith("bill"):
            m = re.match(r"bill\s+(.+?)\s+(\d+\.?\d*)\s+due\s+(\d{4}-\d{2}-\d{2})", command_lower)
            if not m:
                return "⚠️ Format: bill <description> <amount> due YYYY-MM-DD"
            desc = m.group(1).strip()
            amt = float(m.group(2))
            due_date = m.group(3)
            state["debts_bills"].append({
                "type": "bill",
                "description": desc,
                "amount": amt,
                "due_date": due_date,
                "is_paid": False,
                "created_at": datetime.utcnow().isoformat()
            })
            save_user_state(user_id, state)
            return f"✅ Bill recorded: {desc} ₹{amt:.2f}, due {due_date}."

        if command_lower.startswith("summary"):
            parts = command_lower.split()
            month = datetime.utcnow().strftime("%B")
            if len(parts) >= 2:
                month = parts[1].capitalize()
            budgets = state["budgets"].get(month, {})
            spent_by_cat = {}
            for e in state["expenses"]:
                if e["month"] == month:
                    spent_by_cat[e["category"]] = spent_by_cat.get(e["category"], 0) + e["amount"]
            lines = [f"📊 Summary for {month}:"]
            if not budgets:
                lines.append("No budgets set for this month.")
            else:
                for cat, amt in budgets.items():
                    spent = spent_by_cat.get(cat, 0.0)
                    pct = (spent / amt * 100) if amt else 0
                    lines.append(f"- {cat}: Spent ₹{spent:.2f} / Budget ₹{amt:.2f} ({pct:.0f}%)")
            upcoming = [d for d in state["debts_bills"] if d.get("due_date")]
            if upcoming:
                lines.append("\n🔔 Bills/Debts:")
                for d in upcoming:
                    lines.append(f"- {d['type'].capitalize()}: {d['description']} ₹{d['amount']:.2f} due {d['due_date']} (paid: {d['is_paid']})")
            save_user_state(user_id, state)
            return "\n".join(lines)

        return "⚠️ Unknown command. Use 'set budget', 'spent', 'owe', 'bill', or 'summary [month]'."

PurchasingPowerCheckerDescription = RichToolDescription(
    description="AI tool to compare salary affordability and cost of living across cities in South Asia, providing simple explanations and scores using local purchasing power parity data.",
    use_when="Use when users ask if a salary is enough for a city or want comparisons between living costs in different locations.",
    side_effects="Returns a rating or score out of 10 along with a short, clear explanation."
)

@mcp.tool(description=PurchasingPowerCheckerDescription.model_dump_json())
async def purchasing_power_checker(
    query: Annotated[str, Field(description="Affordability or salary comparison query")]
) -> str:
    cities = extract_cities_from_query(query)
    if not cities:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Could not find any city from the query in purchasing power data. Please specify a valid city."))

    if len(cities) == 1:
        city = cities[0]
        return (f"📍 Purchasing Power Index for **{city['city']}**: {city['local_purchasing_power_index']}\n"
                f"This means the local purchasing power is approximately {city['local_purchasing_power_index']}% relative to a baseline.\n"
                "Higher values indicate stronger purchasing power.")

    city1, city2 = cities[0], cities[1]
    ppi1 = city1["local_purchasing_power_index"]
    ppi2 = city2["local_purchasing_power_index"]

    if ppi1 == ppi2:
        comparison = "are about the same."
    elif ppi1 > ppi2:
        diff = ppi1 - ppi2
        comparison = f"is stronger by {diff:.1f} points."
    else:
        diff = ppi2 - ppi1
        comparison = f"is weaker by {diff:.1f} points."

    return (f"📍 Purchasing Power Index comparison:\n"
            f"- **{city1['city']}**: {ppi1}\n"
            f"- **{city2['city']}**: {ppi2}\n"
            f"On this scale, {city1['city']} {comparison}\n"
            "Higher values mean stronger local purchasing power.")

# --- MCP server runner ---
async def main():
    print("🚀 Starting GullakAI MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
