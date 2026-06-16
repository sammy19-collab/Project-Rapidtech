# RapidTech GST Reconciliation System

Automates the complete GST reconciliation workflow for RapidTech's internal accounting.

## Stack
- **Frontend**: React + Tailwind + Recharts
- **Backend**: FastAPI + SQLAlchemy
- **Database**: PostgreSQL
- **Processing**: Pandas

## Quick Start (Docker)

```bash
docker-compose up -d
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

## Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## User Flow

1. Upload `Books` Excel (sheet must be named "Books")
2. Upload GSTR-2B Excel (sheet must be named "2B")
3. Click "Run Reconciliation"
4. View Dashboard → Results → Export Tally XML

## Validation Keys

| Key | Formula |
|-----|---------|
| val1 | GSTIN + InvoiceNo + MonthYear + TaxableValue |
| val2 | GSTIN + InvoiceNo + MonthYear + RoundedTaxable |
| val3 | GSTIN + CleanedInvoiceNo + MonthYear + RoundedTaxable |
| val4 | GSTIN + MonthYear + RoundedTaxable |
| val5 | GSTIN + RoundedTaxable |

## Match Categories
- **5/5** → Exact Match
- **4/5** → Strong Match
- **2-3/5** → Probable Match
- **0-1/5** → Manual Review
