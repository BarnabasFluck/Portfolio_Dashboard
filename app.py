"""
Portfolio planner – Streamlit dashboard built on Portfolio_Analysis_Simple.xlsm

Run with:   streamlit run app.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import portfolio_model as pm

st.set_page_config(page_title="Portfolio planner", page_icon="📈", layout="wide")

DEFAULT_WORKBOOK = Path(__file__).with_name("Portfolio_Analysis_Simple.xlsm")
RISK_COLORS = {"Small": "#2F6F8F", "Medium": "#B7862B", "High": "#A8432F"}
ASSET_COLORS = {"LMT": "#3E5C76", "TXN": "#A8432F", "KO": "#B7862B", "UST 5Y": "#7A9E7E"}
INK, MUTED, GRID = "#1D2A33", "#6B7780", "#E3E7EA"

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1250px;}
      h1 {font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0;}
      .subtitle {color: #6B7780; margin-top: .2rem; margin-bottom: 1.4rem;}
      div[data-testid="stMetricValue"] {font-size: 1.65rem;}
      .profile-chip {display:inline-block; padding:.15rem .6rem; border-radius:4px;
                     color:white; font-weight:600; font-size:.85rem;}
      .note {color:#6B7780; font-size:.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def usd(x, decimals=0):
    return f"${x:,.{decimals}f}" if x >= 0 else f"−${abs(x):,.{decimals}f}"


def pct(x, decimals=1):
    return f"{x:.{decimals}%}"


# --------------------------------------------------------------------------- #
# Data (cached)
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Reading the workbook…")
def load_everything(file_bytes: bytes):
    wbi = pm.read_workbook(file_bytes)
    stats = pm.market_stats(wbi)
    profiles = pm.build_profiles(wbi, stats)
    pstats = {k: pm.profile_stats(p, stats, wbi) for k, p in profiles.items()}
    return wbi, stats, profiles, pstats


@st.cache_data(show_spinner="Simulating thousands of possible futures…")
def run_simulation(file_bytes, risk, initial, recurring, freq, years, n_sims):
    wbi, stats, profiles, pstats = load_everything(file_bytes)
    flows = pm.contribution_schedule(initial, recurring, freq, years)
    sims = pm.monte_carlo(flows, profiles[risk], pstats[risk], stats, wbi, n_sims=n_sims)
    return flows, sims


# --------------------------------------------------------------------------- #
# Sidebar – the investor's choices
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Your plan")
    initial = st.number_input("Amount invested today (USD)", min_value=0.0, value=1_000_000.0,
                              step=1_000.0, format="%.0f")

    recurring_on = st.toggle("Add recurring payments", value=False)
    recurring, freq = 0.0, "Monthly"
    if recurring_on:
        c1, c2 = st.columns([1.2, 1])
        recurring = c1.number_input("Amount each time (USD)", min_value=0.0, value=500.0,
                                    step=50.0, format="%.0f")
        freq = c2.selectbox("How often", list(pm.FREQ_MONTHS), index=0)

    years = st.slider("Investment length (years)", min_value=1, max_value=40, value=10)

    risk = st.radio("Risk you are willing to take", ["Small", "Medium", "High"], index=1,
                    horizontal=True)

    with st.expander("More settings"):
        inflation = st.number_input("Inflation per year, for today's-money values",
                                    min_value=0.0, max_value=0.15, value=0.025, step=0.005,
                                    format="%.3f")
        n_sims = st.select_slider("Number of simulations", [1000, 2500, 5000, 10000, 20000],
                                  value=5000)
        uploaded = st.file_uploader("Use a different version of the workbook", type=["xlsm", "xlsx"])

if uploaded is not None:
    file_bytes = uploaded.getvalue()
elif DEFAULT_WORKBOOK.exists():
    file_bytes = DEFAULT_WORKBOOK.read_bytes()
else:
    st.error(
        f"Workbook not found. Put **{DEFAULT_WORKBOOK.name}** in the same folder as app.py, "
        "or upload it under *More settings* in the sidebar."
    )
    st.stop()

if initial <= 0 and recurring <= 0:
    st.info("Enter an amount to invest today or a recurring payment to see your projection.")
    st.stop()

wbi, stats, profiles, pstats = load_everything(file_bytes)
profile, ps = profiles[risk], pstats[risk]
flows, sims = run_simulation(file_bytes, risk, initial, recurring, freq, years, n_sims)

expected_path = pm.deterministic_path(flows, ps.exp_return)
contributed = np.cumsum(flows)
total_in = contributed[-1]
final_expected = expected_path[-1]
gain = final_expected - total_in
final_sims = sims[:, -1]
p5, p25, p50, p75, p95 = np.percentile(final_sims, [5, 25, 50, 75, 95])
prob_loss = float((final_sims < total_in).mean())
real_factor = (1 + inflation) ** -years

# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("Portfolio Planner")
st.markdown(
    f"<div class='subtitle'>LMT, TXN, KO and the 5-year US Treasury, with an optional put on the "
    f"S&P 500 · market data {stats.returns.index[0]:%b %Y} – {stats.returns.index[-1]:%b %Y} "
    f"from Excel workbook</div>",
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Headline numbers
# --------------------------------------------------------------------------- #
c1, c2, c3, c4 = st.columns(4)
c1.metric("You put in", usd(total_in),
          help="Amount today plus every recurring payment over the period.")
c2.metric(f"Expected value after {years} yr", usd(final_expected),
          delta=f"{usd(final_expected * real_factor)} in today's money", delta_color="off",
          help="Grows at the portfolio's expected return (CAPM, after the cost of the put).")
c3.metric("Expected gain", usd(gain), delta=f"{pct(gain / total_in)} return on investment",
          help="Gain divided by everything you put in.")
c4.metric("Expected return per year", pct(ps.exp_return, 2),
          delta=f"volatility {pct(ps.vol)}", delta_color="off",
          help="Expected return after the put's cost, and how much it typically swings in a year.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Bad case (1 in 20)", usd(p5), delta=pct(p5 / total_in - 1), delta_color="normal",
          help="5% of simulations end below this value.")
c2.metric("Typical outcome (median)", usd(p50), delta=pct(p50 / total_in - 1),
          help="Half the simulations end above this value, half below.")
c3.metric("Good case (1 in 20)", usd(p95), delta=pct(p95 / total_in - 1),
          help="5% of simulations end above this value.")
c4.metric("Chance of ending below what you put in", pct(prob_loss),
          help=f"Share of {n_sims:,} simulations that finish below {usd(total_in)}.")

# --------------------------------------------------------------------------- #
# Projection chart
# --------------------------------------------------------------------------- #
months = np.arange(len(flows))
x_years = months / 12
bands = np.percentile(sims, [5, 25, 50, 75, 95], axis=0)
color = RISK_COLORS[risk]

fig = go.Figure()
fig.add_trace(go.Scatter(x=x_years, y=bands[4], line=dict(width=0), hoverinfo="skip",
                         showlegend=False))
fig.add_trace(go.Scatter(x=x_years, y=bands[0], fill="tonexty", line=dict(width=0),
                         fillcolor="rgba(120,130,140,0.14)", name="90% of outcomes",
                         hovertemplate="5th pct: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=x_years, y=bands[3], line=dict(width=0), hoverinfo="skip",
                         showlegend=False))
fig.add_trace(go.Scatter(x=x_years, y=bands[1], fill="tonexty", line=dict(width=0),
                         fillcolor="rgba(120,130,140,0.25)", name="50% of outcomes",
                         hovertemplate="25th pct: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=x_years, y=bands[2], line=dict(color=color, width=1.5, dash="dot"),
                         name="Typical (median)", hovertemplate="Median: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=x_years, y=expected_path, line=dict(color=color, width=3),
                         name="Expected", hovertemplate="Expected: $%{y:,.0f}<extra></extra>"))
fig.add_trace(go.Scatter(x=x_years, y=contributed, line=dict(color=INK, width=2, shape="hv"),
                         name="Money put in", hovertemplate="Put in: $%{y:,.0f}<extra></extra>"))
fig.update_layout(
    title=dict(text="How your portfolio could grow", font=dict(size=18, color=INK)),
    height=440, margin=dict(l=10, r=10, t=50, b=10), hovermode="x unified",
    plot_bgcolor="white", paper_bgcolor="white",
    legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    xaxis=dict(title="Years from today", gridcolor=GRID, zeroline=False),
    yaxis=dict(title="Portfolio value (USD)", gridcolor=GRID, tickprefix="$", tickformat=",.0f",
               rangemode="tozero"),
)
st.plotly_chart(fig, width="stretch")

# --------------------------------------------------------------------------- #
# Allocation for the chosen risk level
# --------------------------------------------------------------------------- #
left, right = st.columns([1, 1.35], gap="large")
with left:
    st.subheader("Your portfolio")
    st.markdown(
        f"<span class='profile-chip' style='background:{color}'>{profile.label}</span> "
        f"&nbsp;{profile.description}", unsafe_allow_html=True)
    w = profile.weights
    donut = go.Figure(go.Pie(
        labels=w.index, values=w.values, hole=0.58, sort=False,
        marker=dict(colors=[ASSET_COLORS[a] for a in w.index], line=dict(color="white", width=2)),
        texttemplate="%{label}<br>%{percent:.1%}", hovertemplate="%{label}: %{percent:.2%}<extra></extra>",
    ))
    hedge_txt = (f"Put {profile.put_strike:.0%}<br>strike" if profile.put_enabled
                 else "No put")
    donut.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10), showlegend=False,
                        annotations=[dict(text=hedge_txt, showarrow=False, font=dict(size=14, color=INK))])
    st.plotly_chart(donut, width="stretch")
    first_year = initial * w
    st.dataframe(
        pd.DataFrame({"Weight": w.map(pct),
                      "Today's amount": first_year.map(usd),
                      "Expected return": stats.exp_ret.map(lambda x: pct(x, 2)),
                      "Volatility": stats.vol.map(pct),
                      "Beta": stats.beta.map(lambda x: f"{x:.2f}")}),
        width="stretch")
    st.markdown(f"<div class='note'>How it is built: {profile.rules}</div>", unsafe_allow_html=True)

with right:
    st.subheader("Compare the three risk levels")
    rows = {}
    for k, p in profiles.items():
        s = pstats[k]
        path = pm.deterministic_path(flows, s.exp_return)
        rows[profiles[k].label] = {
            "LMT / TXN / KO / UST": " / ".join(f"{x:.0%}" for x in p.weights.values),
            "Expected return / yr": pct(s.exp_return, 2),
            "Volatility / yr": pct(s.vol),
            "Worst fall 2016–26": pct(s.max_drawdown),
            "Max loss if S&P crashes": pct(-s.max_loss_sp_fall) if s.max_loss_sp_fall is not None else "no limit",
            "Put cost / yr": pct(s.put_cost, 2) if s.put_cost else "–",
            f"Expected value in {years} yr": usd(path[-1]),
        }
    comp = pd.DataFrame(rows)
    st.dataframe(comp, width="stretch", height=290)

    target, maxvol, maxdd = (wbi.mandate[k] for k in ("target_return", "max_vol", "max_drawdown"))
    checks = pd.DataFrame({
        "Check (from the Inputs sheet)": [
            f"Expected return ≥ {pct(target, 0)}", f"Volatility ≤ {pct(maxvol, 0)}",
            f"Worst fall ≤ {pct(maxdd, 0)}"],
        "Your portfolio": [pct(ps.exp_return, 2), pct(ps.vol), pct(-ps.max_drawdown)],
        "OK?": ["✔" if ps.exp_return >= target - 1e-6 else "✘",
                "✔" if ps.vol <= maxvol + 1e-6 else "✘",
                "✔" if -ps.max_drawdown <= maxdd + 1e-6 else "✘"],
    })
    st.markdown("**Against the workbook's mandate**")
    st.dataframe(checks, hide_index=True, width="stretch")
    st.markdown("<div class='note'>The mandate was set for the medium profile; small and high "
                "risk deliberately trade it off in opposite directions.</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Detail tabs
# --------------------------------------------------------------------------- #
st.divider()
tab_year, tab_stress, tab_hist, tab_how = st.tabs(
    ["Year by year", "Stress tests", "History 2016–2026", "How it's calculated"])

with tab_year:
    idx = np.arange(0, len(flows), 12)
    if idx[-1] != len(flows) - 1:
        idx = np.append(idx, len(flows) - 1)
    table = pd.DataFrame({
        "Year": (idx / 12).astype(int),
        "Total put in": contributed[idx],
        "Expected value": expected_path[idx],
        "Expected gain": expected_path[idx] - contributed[idx],
        "Bad case (5%)": bands[0][idx],
        "Typical (median)": bands[2][idx],
        "Good case (95%)": bands[4][idx],
        "Expected, today's money": expected_path[idx] * (1 + inflation) ** -(idx / 12),
    })
    st.dataframe(
        table.style.format({c: "${:,.0f}" for c in table.columns if c != "Year"}),
        hide_index=True, width="stretch")
    st.download_button("Download this table (CSV)", table.to_csv(index=False).encode(),
                       file_name=f"projection_{risk.lower()}_{years}y.csv", mime="text/csv")
    irr = pm.money_weighted_return(flows, p50)
    if not np.isnan(irr):
        st.markdown(f"<div class='note'>In the typical (median) outcome your money earns "
                    f"{pct(irr, 2)} a year, counting when each payment went in.</div>",
                    unsafe_allow_html=True)

with tab_stress:
    st.markdown("A sudden shock to today's portfolio, using the same method as the Risk sheet: "
                "stocks move with their beta, the Treasury with its duration and convexity, "
                "and the put pays if the S&P 500 ends below the strike.")
    scenarios = {
        "Rates up 1%": (0.0, 100), "Rates down 1%": (0.0, -100),
        "S&P 500 −10%": (-0.10, 0), "S&P 500 −20%": (-0.20, 0),
        "S&P 500 −40%": (-0.40, 0), "S&P 500 +15%": (0.15, 0),
    }
    with st.expander("Add your own scenario"):
        cc1, cc2 = st.columns(2)
        sp_custom = cc1.slider("S&P 500 move", -0.6, 0.4, -0.1, 0.05, format="%.2f")
        dy_custom = cc2.slider("Change in the 5Y yield (basis points)", -300, 300, 50, 25)
        scenarios["Your scenario"] = (sp_custom, dy_custom)

    value_now = max(initial, 1.0)
    res = {k: pm.stress_test(profiles[k], pstats[k], stats, scenarios) for k in profiles}
    stress = pd.DataFrame(res)
    stress.columns = [profiles[k].label for k in stress.columns]
    sfig = go.Figure()
    for k in profiles:
        sfig.add_trace(go.Bar(x=list(scenarios), y=list(res[k].values()),
                              name=profiles[k].label, marker_color=RISK_COLORS[k],
                              opacity=1.0 if k == risk else 0.45,
                              hovertemplate="%{x}: %{y:.1%}<extra>" + profiles[k].label + "</extra>"))
    sfig.update_layout(barmode="group", height=360, margin=dict(l=10, r=10, t=30, b=10),
                       plot_bgcolor="white", yaxis=dict(tickformat=".0%", gridcolor=GRID,
                                                       title="Change in portfolio value"),
                       legend=dict(orientation="h", y=1.08))
    st.plotly_chart(sfig, width="stretch")
    st.dataframe(pd.DataFrame({
        "Change": stress[profile.label].map(lambda x: pct(x, 1)),
        f"On {usd(value_now)} today": (stress[profile.label] * value_now).map(usd),
    }).rename_axis(f"{profile.label}"), width="stretch")

with tab_hist:
    st.markdown("How each allocation would have done on the workbook's weekly data "
                "(prices only, no dividends, put not included).")
    hist = pd.DataFrame({profiles[k].label: (1 + pstats[k].weekly_returns).cumprod() * 100
                         for k in profiles})
    hist["S&P 500"] = (1 + stats.returns["S&P 500"]).cumprod() * 100
    hfig = go.Figure()
    for k in profiles:
        lab = profiles[k].label
        hfig.add_trace(go.Scatter(x=hist.index, y=hist[lab], name=lab,
                                  line=dict(color=RISK_COLORS[k], width=3 if k == risk else 1.5)))
    hfig.add_trace(go.Scatter(x=hist.index, y=hist["S&P 500"], name="S&P 500",
                              line=dict(color=MUTED, width=1.5, dash="dash")))
    hfig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="white",
                       yaxis=dict(title="Growth of 100", gridcolor=GRID), xaxis=dict(gridcolor=GRID),
                       legend=dict(orientation="h", y=1.08), hovermode="x unified")
    st.plotly_chart(hfig, width="stretch")
    n_yrs = len(hist) / wbi.weeks_per_year
    st.dataframe(pd.DataFrame({
        "Return per year": (hist.iloc[-1] / 100) ** (1 / n_yrs) - 1,
        "Worst fall": [pstats[k].max_drawdown for k in profiles] +
                      [float((hist["S&P 500"] / hist["S&P 500"].cummax() - 1).min())],
    }).style.format("{:.1%}"), width="stretch")

with tab_how:
    st.markdown(f"""
**Expected return of each asset** = risk-free rate ({pct(wbi.rf)}) + beta × equity risk premium
({pct(wbi.erp)}), as in the workbook. Beta, volatility and correlations come from
{len(stats.returns)} weeks of returns on the Data sheet. The Treasury's weekly return is its
coupon carry plus the duration ({stats.duration:.2f}) and convexity ({stats.convexity:.1f})
effect of the change in the 5-year yield.

**Risk levels** change the portfolio itself:

- *Small* – the lowest-volatility mix with 40–60% in the Treasury and 5–30% per stock, plus a
  put at 90% of the S&P 500 so equity losses stop at about −10%.
- *Medium* – the workbook's own allocation (Solver, max Sharpe) and its put settings
  ({pct(wbi.put_strike, 0)} strike).
- *High* – the highest expected return with volatility capped at 20%, 0–10% Treasury,
  10–55% per stock and no put.

**The put** is priced with Black–Scholes each year on the stocks' beta exposure
(Risk sheet method). Its yearly cost = premium grown at the risk-free rate − expected payoff.

**Projection.** The expected line compounds the expected return monthly. The bands come from
{n_sims:,} Monte Carlo simulations: monthly lognormal returns for the portfolio and the S&P 500,
linked through the portfolio's beta. Where a put is held, the premium is paid at the start of each
year and the payoff received at year end if the S&P 500 is below the strike. Recurring payments
are added at the end of each period.

**Limits.** Expected returns are model estimates, not forecasts; there are no fees, taxes or
dividends beyond what CAPM implies, and the put is a model price, not a market quote.
This tool is for exploration and is not financial advice.
""")
