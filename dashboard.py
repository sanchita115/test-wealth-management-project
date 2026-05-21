import plotly.graph_objects as go
import pandas as pd

# ── Sundial design tokens (from official spec) ────────────────────────────────
PAGE_BG    = "#fef8fa"
CARD_BG    = "#ffffff"
PURPLE     = "#A43DF5"   # single accent / default series
POSITIVE   = "#119F97"   # teal-green
NEGATIVE   = "#FF5D39"   # warm orange (not red)
NEUTRAL    = "#3E8ED8"   # reference / prior period
ANOMALY    = "#FD2B68"   # pink-magenta, true exceptions only
WARNING    = "#E8AC13"

TEXT_100   = "rgba(0,0,0,1)"
TEXT_70    = "rgba(0,0,0,0.7)"
TEXT_45    = "rgba(0,0,0,0.45)"
GRID       = "rgba(0,0,0,0.15)"
BORDER     = "rgba(0,0,0,0.08)"

# Categorical order: purple → orange → yellow → blue → pink → teal → ...
CATEGORICAL = [PURPLE, "#FF5D39", WARNING, NEUTRAL, "#F17AB2",
               POSITIVE, "#A8C800", "#C84BC8", "#8B4513", "#6B1FA3"]

FONT_STACK = "'Work Sans', Inter, system-ui, sans-serif"
MONO_STACK = "'Inconsolata', monospace"


def _axis(orient="y") -> dict:
    return dict(
        gridcolor=GRID if orient == "y" else "rgba(0,0,0,0)",
        showgrid=(orient == "y"),
        zeroline=False,
        showline=False,
        tickfont=dict(size=11, color=TEXT_45, family=MONO_STACK),
        title=None,
    )


def _base(title: str, extra: dict = None) -> dict:
    layout = dict(
        title=dict(
            text=title,
            font=dict(size=16, color=TEXT_100, family=FONT_STACK, weight=600),
            x=0, pad=dict(b=8),
        ),
        paper_bgcolor=PAGE_BG,
        plot_bgcolor=CARD_BG,
        font=dict(family=FONT_STACK, color=TEXT_70, size=12),
        margin=dict(t=52, b=40, l=64, r=24),
        hoverlabel=dict(
            bgcolor=CARD_BG,
            bordercolor=BORDER,
            font=dict(color=TEXT_100, size=13, family=FONT_STACK),
        ),
    )
    if extra:
        layout.update(extra)
    return layout


def category_donut(stats: dict) -> go.Figure:
    by_cat = stats["by_category"]["total"]
    labels, values = list(by_cat.keys()), [round(v, 2) for v in by_cat.values()]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.58,
        marker=dict(
            colors=CATEGORICAL[:len(labels)],
            line=dict(color=PAGE_BG, width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=11, color=TEXT_70, family=FONT_STACK),
        hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}  ·  %{percent}<extra></extra>",
        opacity=0.9,
    ))
    fig.update_layout(**_base("Spending by Category", extra=dict(
        showlegend=False,
        margin=dict(t=52, b=16, l=16, r=16),
        annotations=[dict(
            text=f"₹{stats['total_expenses']:,.0f}",
            x=0.5, y=0.5,
            font=dict(size=16, color=TEXT_100, family=MONO_STACK, weight=600),
            showarrow=False,
        )],
    )))
    return fig


def daily_spending_area(stats: dict) -> go.Figure:
    daily = pd.Series(stats["daily_totals"])
    daily.index = pd.to_datetime(daily.index)
    daily = daily.sort_index()
    rolling7 = daily.rolling(7, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=daily.index, y=daily.values,
        mode="lines",
        name="Daily spend",
        fill="tozeroy",
        line=dict(color=PURPLE, width=2.5),
        fillcolor="rgba(164,62,245,0.06)",
        hovertemplate="<b>%{x|%b %d}</b>  ₹%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=rolling7.index, y=rolling7.values,
        mode="lines",
        name="7-day avg",
        line=dict(color=NEUTRAL, width=2.5, dash="dot"),
        hovertemplate="7-day avg  ₹%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base("Daily Spending", extra=dict(
        xaxis=_axis("x"),
        yaxis=dict(**_axis("y"), tickprefix="₹"),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=12, color=TEXT_45),
            orientation="h", y=1.08, x=0,
        ),
        hovermode="x unified",
    )))
    return fig


def top_merchants_bar(stats: dict) -> go.Figure:
    merchants = stats["top_merchants"]
    names = list(merchants.keys())[:8]
    values = [round(merchants[n], 2) for n in names]
    display_names = [n[:30] + "…" if len(n) > 32 else n for n in names]

    fig = go.Figure(go.Bar(
        y=display_names[::-1],
        x=values[::-1],
        orientation="h",
        marker=dict(
            color=PURPLE,
            opacity=0.9,
            line=dict(color="rgba(0,0,0,0)", width=0),
        ),
        hovertemplate="<b>%{y}</b>  ₹%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base("Top Merchants", extra=dict(
        xaxis=dict(**_axis("y"), tickprefix="₹"),  # x-axis of horizontal bar = value axis
        yaxis=dict(**_axis("x")),
        margin=dict(t=52, b=40, l=180, r=40),
    )))
    return fig


def weekly_bar(stats: dict) -> go.Figure:
    weekly = pd.Series(stats["weekly_totals"])
    weekly.index = pd.to_datetime(weekly.index)
    weekly = weekly.sort_index()
    avg = weekly.mean()

    colors = [NEGATIVE if v > avg * 1.2 else PURPLE for v in weekly.values]

    fig = go.Figure(go.Bar(
        x=[f"Wk {d.strftime('%b %d')}" for d in weekly.index],
        y=weekly.values,
        marker=dict(color=colors, opacity=0.9, line=dict(color="rgba(0,0,0,0)", width=0)),
        hovertemplate="<b>%{x}</b>  ₹%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(
        y=avg,
        line=dict(color=WARNING, width=2, dash="dot"),
        annotation=dict(
            text=f"avg ₹{avg:,.0f}",
            font=dict(color=WARNING, size=11, family=MONO_STACK),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    fig.update_layout(**_base("Weekly Spending", extra=dict(
        xaxis=dict(**_axis("x"), tickangle=-30),
        yaxis=dict(**_axis("y"), tickprefix="₹"),
        margin=dict(t=52, b=72, l=64, r=24),
    )))
    return fig


def kpi_metrics(stats: dict) -> dict:
    return {
        "Total Spent":  f"₹{stats['total_expenses']:,.0f}",
        "Total Income": f"₹{stats['total_income']:,.0f}",
        "Net":          f"₹{stats['net']:+,.0f}",
        "Monthly Avg":  f"₹{stats['avg_monthly_spend']:,.0f}",
        "Daily Avg":    f"₹{stats['avg_daily_spend']:,.0f}",
        "Transactions": str(stats["num_transactions"]),
    }
