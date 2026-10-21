# Portfolio planner (Streamlit)

Dashboard built on `Portfolio_Analysis_Simple.xlsm`. Enter an amount, optional recurring
payments, an investment length and a risk level; it projects the portfolio's value and return.

## Run it
    pip install -r requirements.txt
    streamlit run app.py

Keep `Portfolio_Analysis_Simple.xlsm` next to `app.py` (or upload another version in the
sidebar under "More settings"). The app reads prices, weights, rates and put settings straight
from the workbook, so updating the workbook updates the dashboard.

## Files
- `app.py` – the dashboard
- `portfolio_model.py` – the calculations (mirrors the workbook, plus risk profiles and Monte Carlo)
- `.streamlit/config.toml` – colours
