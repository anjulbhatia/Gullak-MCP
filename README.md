# GullakAI MCP Server

A lightweight MCP server for personal finance assistance, expense tracking, financial news simplification, and local purchasing power comparisons across South Asian cities.

---

## Features

- **Core Finance Q&A**  
  Conversational AI that answers personal finance questions clearly and simply in multiple languages.

- **Financial News Simplifier**  
  Summarizes and explains complex financial news and jargon in easy-to-understand language.

- **Expense & Budget Monitor**  
  Manage budgets, record expenses, track debts and bills using simple chat commands.

- **Purchasing Power Checker**  
  Compare salary affordability and cost of living across cities using local purchasing power parity data.

---

## Setup Instructions

1. **Clone the repository and install dependencies:**

   ```bash
   uv .venv
   uv sync
   source .venv/activate
   ```

2. **Configure environment variables:**
Create a ```.env``` file in the root folder with:

```ini
AUTH_TOKEN=your_secure_token_here
MY_NUMBER=your_whatsapp_number_here
```

3. **Add purchasing power data:**
Ensure the file purchasingpower.json is present with the structure:

```json
{
  "cities": [
    {"city": "Hyderabad, India", "local_purchasing_power_index": 154.1},
    {"city": "Bangalore, India", "local_purchasing_power_index": 149.7}
    // ... more cities
  ]
}
```

4. **Run the MCP server:**

```bash
python server.py
```

---

## Usage
1. Interact with the MCP tools through your WhatsApp bot or other MCP-compatible clients.

Expense commands supported:

set budget <month> <category1> <amount1> ...

spent <amount> on <category>

owe <person/description> <amount>

bill <description> <amount> due YYYY-MM-DD

summary [month]

2. Ask natural language finance questions or purchasing power comparisons.

---

## Notes

Expense and budget data is cached in memory with a 7-day expiration.

Designed for asynchronous operation suitable for WhatsApp and browser-based chatbot integration.

---

## License
This project is licensed under the MIT License.


***Let me know if you want it expanded or more examples included!***