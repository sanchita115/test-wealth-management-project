import pandas as pd
import anthropic
import json
import os
import re

# Indian bank CSV column names vary a lot — this maps them all to standard names
COLUMN_ALIASES = {
    "date": ["date", "transaction date", "trans date", "posted date", "posting date",
             "value date", "tran date", "txn date", "valuedate", "transactiondate"],
    "description": ["description", "narration", "particulars", "remarks", "details", "memo",
                    "transaction remarks", "transaction description", "chq/ref number",
                    "transaction narration", "narrative"],
    "amount": ["amount", "transaction amount", "inr amount"],
    "debit": ["debit", "debit amount", "withdrawal amt", "withdrawal amount",
              "dr", "debit(inr)", "withdrawal (inr)", "debit amount (inr )"],
    "credit": ["credit", "credit amount", "deposit amt", "deposit amount",
               "cr", "credit(inr)", "deposit (inr)", "deposit amount (inr )"],
    "category": ["category", "type", "transaction type"],
}

KNOWN_CATEGORIES = {
    "Food & Dining": [
        "swiggy", "zomato", "blinkit", "dunzo", "zepto", "bigbasket", "grofers",
        "mcdonald", "domino", "pizza", "kfc", "burger king", "subway", "haldiram",
        "cafe coffee day", "ccd", "starbucks", "chaayos", "wow momo",
        "box8", "freshmenu", "food", "restaurant", "cafe", "canteen",
    ],
    "Transportation": [
        "ola", "uber", "rapido", "namma yatri", "bluemart", "yulu",
        "irctc", "indian railway", "railways", "metro", "dmrc", "bmtc",
        "indigo", "air india", "spicejet", "vistara", "goair", "akasa",
        "petrol", "fuel", "hp petrol", "indian oil", "iocl", "bharat petroleum", "bpcl",
        "parking", "fastag", "toll",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho", "snapdeal",
        "reliance", "dmart", "big bazaar", "more supermarket", "spencer",
        "croma", "vijay sales", "apple", "samsung", "mi store",
        "lifestyle", "westside", "pantaloons", "max fashion",
    ],
    "Entertainment": [
        "hotstar", "disney", "jiocinema", "zee5", "sonyliv", "netflix", "amazon prime",
        "spotify", "gaana", "wynk", "youtube premium",
        "bookmyshow", "pvr", "inox", "carnival cinemas",
        "steam", "playstation", "xbox",
    ],
    "Health & Fitness": [
        "cult.fit", "curefit", "gym", "fitness", "yoga",
        "apollo", "fortis", "max hospital", "aiims", "medanta",
        "1mg", "netmeds", "pharmeasy", "medlife", "tata 1mg",
        "pharmacy", "medical", "doctor", "dentist", "hospital", "clinic",
    ],
    "Utilities & Bills": [
        "bescom", "tata power", "adani electricity", "msedcl", "bses",
        "mahanagar gas", "igl", "mgl", "piped gas",
        "airtel", "jio", "vodafone", "vi ", "bsnl", "idea",
        "tata sky", "dish tv", "d2h",
        "electricity", "water bill", "internet", "broadband",
        "insurance", "lic", "hdfc life", "icici pru", "star health",
    ],
    "Rent & Housing": [
        "rent", "nobroker", "housing", "magicbricks", "maintenance", "society",
    ],
    "Investments & Savings": [
        "groww", "zerodha", "upstox", "indmoney", "ind money", "kuvera",
        "coin by zerodha", "etmoney", "paytm money", "angel broking", "motilal",
        "mutual fund", "sip", "nps", "ppf", "fd ", "fixed deposit", "rd ",
        "recurring deposit", "gold bond", "sovereign gold",
    ],
    "UPI & Transfers": [
        "upi/", "upi-", "imps/", "neft/", "rtgs/", "transfer to", "transfer from",
        "phonepe", "gpay", "google pay", "paytm", "bhim", "amazon pay",
        "razorpay", "cashfree",
    ],
    "ATM & Cash": ["atm", "cash withdrawal", "atw"],
    "Income": [
        "salary", "payroll", "neft cr", "imps cr", "credit by", "interest credit",
        "dividend", "refund", "cashback", "reward", "bonus",
    ],
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    lower_cols = {c.lower().strip(): c for c in df.columns}

    for standard, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lower_cols and standard not in rename_map.values():
                rename_map[lower_cols[alias]] = standard
                break

    df = df.rename(columns=rename_map)

    # Many Indian bank CSVs give separate Debit / Credit columns instead of a signed Amount
    if "amount" not in df.columns and "debit" in df.columns and "credit" in df.columns:
        df["debit"] = pd.to_numeric(
            df["debit"].astype(str).str.replace(",", ""), errors="coerce"
        ).fillna(0)
        df["credit"] = pd.to_numeric(
            df["credit"].astype(str).str.replace(",", ""), errors="coerce"
        ).fillna(0)
        df["amount"] = df["credit"] - df["debit"]

    return df


def _clean_amount(val) -> float:
    """Strip Indian comma formatting and convert to float."""
    if pd.isna(val):
        return 0.0
    cleaned = re.sub(r"[^\d.\-]", "", str(val).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def categorize(description: str) -> str:
    desc_lower = str(description).lower()
    for category, keywords in KNOWN_CATEGORIES.items():
        if any(kw in desc_lower for kw in keywords):
            return category
    return "Other"


def parse_csv(file) -> pd.DataFrame:
    # Some Indian bank exports have junk header rows — skip blank/summary lines
    df = pd.read_csv(file, thousands=",", skipinitialspace=True)
    df.columns = df.columns.str.strip()
    df = df.dropna(how="all")

    df = normalize_columns(df)

    if "date" not in df.columns:
        raise ValueError(
            "Could not find a date column. Expected one of: Date, Transaction Date, Tran Date, Value Date."
        )
    if "amount" not in df.columns:
        raise ValueError(
            "Could not find an amount column. Expected Amount, or separate Debit/Credit columns."
        )
    if "description" not in df.columns:
        df["description"] = "Unknown"

    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date"])
    df["amount"] = df["amount"].apply(_clean_amount)
    df["description"] = df["description"].astype(str).str.strip()

    if "category" not in df.columns:
        df["category"] = df["description"].apply(categorize)

    df = df.sort_values("date")
    return df


def compute_stats(df: pd.DataFrame) -> dict:
    expenses = df[df["amount"] < 0].copy()
    income = df[df["amount"] > 0].copy()

    expenses["amount_abs"] = expenses["amount"].abs()

    date_range = (df["date"].max() - df["date"].min()).days + 1
    months = max(date_range / 30, 1)

    by_category = (
        expenses.groupby("category")["amount_abs"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "total", "count": "transactions"})
        .sort_values("total", ascending=False)
    )

    daily = expenses.set_index("date")["amount_abs"].resample("D").sum()
    weekly = expenses.set_index("date")["amount_abs"].resample("W").sum()

    top_merchants = (
        expenses.groupby("description")["amount_abs"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    largest_transactions = expenses.nlargest(5, "amount_abs")[
        ["date", "description", "amount_abs", "category"]
    ]

    avg_daily = daily.mean()
    highest_day = daily.idxmax()
    highest_day_amount = daily.max()

    weekly_list = weekly.tolist()
    wow_change = None
    if len(weekly_list) >= 2:
        prev, curr = weekly_list[-2], weekly_list[-1]
        wow_change = ((curr - prev) / prev * 100) if prev > 0 else None

    return {
        "total_expenses": float(expenses["amount_abs"].sum()),
        "total_income": float(income["amount"].sum()),
        "net": float(df["amount"].sum()),
        "num_transactions": len(df),
        "num_expense_transactions": len(expenses),
        "date_range_days": date_range,
        "months": months,
        "avg_monthly_spend": float(expenses["amount_abs"].sum() / months),
        "avg_daily_spend": float(avg_daily),
        "highest_spending_day": str(highest_day.date()) if pd.notna(highest_day) else None,
        "highest_spending_day_amount": float(highest_day_amount),
        "by_category": by_category.to_dict(),
        "top_merchants": top_merchants.to_dict(),
        "largest_transactions": largest_transactions.to_dict("records"),
        "wow_change": wow_change,
        "weekly_totals": weekly.to_dict(),
        "daily_totals": daily.to_dict(),
    }


def detect_anomalies(stats: dict, df: pd.DataFrame) -> list:
    anomalies = []

    daily = pd.Series(stats["daily_totals"])
    if len(daily) > 7:
        mean = daily.mean()
        std = daily.std()
        spikes = daily[daily > mean + 2 * std]
        for date, amount in spikes.items():
            anomalies.append({
                "type": "spending_spike",
                "date": str(date.date()) if hasattr(date, "date") else str(date),
                "amount": round(float(amount), 2),
                "message": f"Unusually high spending of ₹{amount:,.0f} on {date}",
            })

    by_cat = stats["by_category"]["total"]
    total = stats["total_expenses"]
    for cat, amount in by_cat.items():
        pct = amount / total * 100 if total > 0 else 0
        if pct > 40 and cat not in ("Other", "Income", "UPI & Transfers"):
            anomalies.append({
                "type": "category_dominance",
                "category": cat,
                "percentage": round(pct, 1),
                "amount": round(float(amount), 2),
                "message": f"{cat} is eating {pct:.1f}% of your budget (₹{amount:,.0f})",
            })

    for tx in stats["largest_transactions"]:
        if tx["amount_abs"] > stats["avg_monthly_spend"] * 0.3:
            anomalies.append({
                "type": "large_single_transaction",
                "date": str(tx["date"].date()) if hasattr(tx["date"], "date") else str(tx["date"]),
                "description": tx["description"],
                "amount": round(float(tx["amount_abs"]), 2),
                "message": f"Big one-off: {tx['description']} for ₹{tx['amount_abs']:,.0f}",
            })

    if stats["wow_change"] is not None and abs(stats["wow_change"]) > 30:
        direction = "up" if stats["wow_change"] > 0 else "down"
        anomalies.append({
            "type": "week_over_week",
            "change_pct": round(stats["wow_change"], 1),
            "message": f"Spending went {direction} {abs(stats['wow_change']):.1f}% last week vs the week before",
        })

    return anomalies


def generate_narrative(stats: dict, anomalies: list) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    summary_data = {
        "currency": "INR (₹)",
        "total_expenses": round(stats["total_expenses"], 2),
        "total_income": round(stats["total_income"], 2),
        "net": round(stats["net"], 2),
        "avg_monthly_spend": round(stats["avg_monthly_spend"], 2),
        "avg_daily_spend": round(stats["avg_daily_spend"], 2),
        "date_range_days": stats["date_range_days"],
        "top_categories": {k: round(v, 2) for k, v in list(stats["by_category"]["total"].items())[:6]},
        "top_merchants": {k: round(v, 2) for k, v in list(stats["top_merchants"].items())[:5]},
        "highest_day": {
            "date": stats["highest_spending_day"],
            "amount": round(stats["highest_spending_day_amount"], 2),
        },
        "anomalies": anomalies[:5],
    }

    prompt = f"""You're a witty but insightful personal finance analyst for an Indian user. You understand Indian spending culture — UPI payments, Swiggy/Zomato habits, SIPs, EMIs, and the guilt of yet another Blinkit order.

Data (all amounts in Indian Rupees ₹):
{json.dumps(summary_data, indent=2, default=str)}

Write a 4-6 paragraph narrative spending report that:
1. Opens with a punchy, personality-driven observation about their overall financial picture
2. Breaks down the top spending categories with specific observations — light roast where deserved (e.g. Swiggy dependency, ATM cash habit)
3. Calls out patterns — good habits (SIPs! investments!) and red flags — with concrete ₹ numbers
4. Highlights the biggest anomalies or surprises
5. Closes with 2-3 actionable, India-specific recommendations (e.g. switch to UPI for X, start a ₹500/month SIP, etc.)

Tone: conversational, a little cheeky, honest but not cruel. Use ₹ for all amounts. Reference Indian apps and context naturally. No bullet points — pure narrative prose."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
