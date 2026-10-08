# OCULUS (Market Intelligence

A market intelligence dashboard for Indonesian (IDX) stocks. It combines sector discovery, technical, fundamental and narrative analysis, and broker/foreign-flow data into one view, with an AI-generated narrative summary on top.

Built for **Sectors Hackathon 2026 (Track 3: Market Intelligence)** using the [Sectors.app](https://sectors.app) API.

## Features

- **Sector and sub-sector ranking**: finds the hot sub-sectors from market cap and daily price change
- **Technical analysis**: trend and indicator-based signals
- **Fundamental analysis**: bank-aware scoring covering profitability, financial risk, growth and valuation, with data coverage and flags
- **Narrative analysis**: insider activity, filings and corporate actions
- **Broker analysis**: broker ranking, broker activity and foreign flow
- **RAG narrative summary**: Chroma vector store and Google Gemini turn the module outputs into a readable summary
- **API caching**: TTL cache checked before any Sectors.app call, to save API quota

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI |
| Data | Sectors.app API v2 |
| AI / RAG | ChromaDB, Google Gemini |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |

## Project Structure

```
Market_Intelligence/
├── Backend/
│   ├── FastAPI_Service.py          # API entry point
│   ├── app/
│   │   ├── Analysis/               # Fundamental, narrative, sector, technical, broker analysis
│   │   ├── Cache/                  # TTL cache layer
│   │   ├── Data/                   # Sectors.app API calls
│   │   ├── RAG_Narrative_Analysis/ # ingest, retrieve, generate (Chroma + Gemini)
│   │   └── Service/                # Service functions used by the API routes
│   └── data/                       # Generated: narrative cache + vector DB (git-ignored)
├── frontend/
│   └── oculusui/                   # Next.js app
├── top20.json / top150.json        # Sample data for offline testing
├── requirement.txt
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- A [Sectors.app](https://sectors.app) API key
- A Google Gemini API key (free tier works)

## Setup

### 1. Clone

```bash
git clone <your-repo-url>
cd Market_Intelligence
```

### 2. Backend

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirement.txt
```

Create `Backend/.env` (see `.env.example`):

```env
SECTORS_API_KEY=your_sectors_api_key
GEMINI_API_KEY=your_gemini_api_key
```

Build the vector store for the RAG summary (first run only):

```bash
cd Backend
python -m app.RAG_Narrative_Analysis.ingest
```

Start the API:

```bash
uvicorn FastAPI_Service:app --reload --port 8000
```

API docs are available at http://localhost:8000/docs.

### 3. Frontend

```bash
cd frontend/oculusui
npm install
npm run dev
```

Open http://localhost:3000.

## Caching

Every Sectors.app call goes through a cache first. On a hit, the cached data is returned. On a miss or an expired TTL, the API is called and the result is stored. Cached narrative summaries are saved in `Backend/data/cache/`.

## Notes

- `Backend/data/` (cache and vector DB) is generated at runtime and not committed. Run the ingest step after cloning.
- This project is for informational purposes only and is not financial advice.

## Author

**Username: @joenath376xfc1x **: PT Solohackathon Team
