# Polymarket Edge Finder

A web application for finding trading edges in Polymarket prediction markets.

## Structure

```
polymarket-edge-finder/
├── backend/           # FastAPI server
│   ├── api/          # API routes
│   ├── core/         # Business logic
│   │   ├── models.py      # Data models
│   │   ├── ingestion.py   # Market fetching
│   │   ├── detection.py   # Edge detection
│   │   └── research.py    # Research agents
│   ├── main.py       # FastAPI app
│   └── requirements.txt
│
├── frontend/         # React app
│   ├── src/
│   │   ├── api/     # API client
│   │   ├── components/
│   │   ├── hooks/
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

## Quick Start

### 1. Start the Backend

```bash
cd backend

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn main:app --reload --port 8000
```

The API will be available at http://localhost:8000
- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 2. Start the Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The app will be available at http://localhost:3000

## Usage

### Loading Demo Data

Click "Load Demo" to load sample data for testing the UI without hitting Polymarket APIs.

### Refreshing Real Data

Click "Refresh Data" to fetch live markets from Polymarket. This will:
1. Fetch active markets sorted by volume
2. Calculate edge scores for each market
3. Run edge detection algorithms
4. Generate research agent predictions

Note: Due to rate limiting, a full refresh may take 1-2 minutes.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats` | GET | Dashboard statistics |
| `/api/status` | GET | Loading status |
| `/api/markets` | GET | List markets (with filters) |
| `/api/markets/{id}` | GET | Get single market |
| `/api/opportunities` | GET | List edge opportunities |
| `/api/predictions` | GET | List predictions |
| `/api/refresh` | POST | Trigger data refresh |
| `/api/load-demo` | POST | Load demo data |

### Query Parameters

**Markets:**
- `category`: Filter by category (politics, sports, crypto, etc.)
- `min_score`: Minimum edge score (0-100)
- `min_volume`: Minimum 24h volume
- `limit`: Max results (default 50)
- `offset`: Pagination offset

**Opportunities:**
- `edge_type`: Filter by type (arbitrage, mispricing, etc.)
- `min_confidence`: Minimum confidence (0-100)
- `risk_level`: Filter by risk (low, medium, high)

**Predictions:**
- `direction`: Filter by direction (buy_yes, buy_no, hold)
- `min_edge`: Minimum absolute edge

## Edge Detection

The system detects several types of edges:

| Type | Description | Risk |
|------|-------------|------|
| **Arbitrage** | YES + NO ≠ 1.00 | Low |
| **Mispricing** | Prices don't match fundamentals | Medium |
| **Temporal** | Date-based inconsistencies | Low |
| **Volume Signal** | Unusual trading activity | High |
| **Liquidity Gap** | Wide spreads to exploit | Medium |

## Research Agents

Category-specific agents analyze markets:

- **PoliticsAgent**: Elections, policy (uses polling data)
- **SportsAgent**: Games, matches (uses statistics)
- **CryptoAgent**: Crypto markets (uses on-chain data)
- **EconomicsAgent**: Fed, indicators (uses economic data)

Currently using placeholder analysis - designed to be extended with real data sources.

## Extending

### Adding a New Edge Detector

In `backend/core/detection.py`:

```python
def detect_my_edge(markets: List[Market]) -> List[EdgeOpportunity]:
    opportunities = []
    for market in markets:
        if my_condition(market):
            opportunities.append(EdgeOpportunity(
                edge_type=EdgeType.MISPRICING,
                description="My edge description",
                confidence=75,
                # ... other fields
            ))
    return opportunities
```

Then add it to `detect_all_edges()`.

### Adding a New Research Agent

In `backend/core/research.py`:

```python
class MyAgent(ResearchAgent):
    def __init__(self):
        super().__init__("MyAgent", [MarketCategory.OTHER])
    
    def can_analyze(self, market: Market) -> bool:
        return "my_keyword" in market.question.lower()
    
    def analyze(self, market: Market) -> Prediction:
        # Fetch data from APIs
        # Run analysis
        return Prediction(...)
```

Then add it to `AgentOrchestrator.__init__()`.

## Deployment

### Backend on Render

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New > Web Service**
4. Connect your GitHub repo
5. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Deploy

Your API will be at: `https://your-service-name.onrender.com`

### Frontend on Netlify

1. Go to [Netlify Dashboard](https://app.netlify.com)
2. Click **Add new site > Import an existing project**
3. Connect your GitHub repo
4. Configure:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/dist`
5. Add environment variable:
   - **Key**: `VITE_API_URL`
   - **Value**: `https://your-render-service.onrender.com/api`
6. Deploy

### Environment Variables

**Frontend (Netlify):**
| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `https://myapi.onrender.com/api` |

**Backend (Render):**
| Variable | Description | Example |
|----------|-------------|---------|
| `FRONTEND_URL` | (Optional) Frontend URL for CORS | `https://mysite.netlify.app` |

---

## Development

### Backend

```bash
# Run with auto-reload
uvicorn main:app --reload

# Run tests (if added)
pytest
```

### Frontend

```bash
# Dev server with HMR
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

## License

MIT
