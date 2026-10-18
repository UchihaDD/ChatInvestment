from __future__ import annotations

from datetime import datetime, timezone
import math
import time

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="ChatInvestment",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem; max-width: 1400px;}
div[data-testid="stMetric"] {background: rgba(120,120,120,.07); padding: .65rem; border-radius: .7rem;}
.small-note {font-size: .85rem; opacity: .8;}
</style>
""", unsafe_allow_html=True)

st.title("📈 ChatInvestment")
st.caption("Scanner informativo per azioni, ETF, crypto e mercati — dati gratuiti, non garantiti in tempo reale.")

# --- Universe ---
MARKETS = {
    "Nasdaq Composite": "^IXIC",
    "S&P 500": "^GSPC",
    "FTSE MIB": "FTSEMIB.MI",
    "Petrolio WTI": "CL=F",
    "Oro": "GC=F",
    "Gas naturale USA": "NG=F",
}

ETF_DEFAULTS = [
    "VWCE.DE", "SWDA.MI", "EIMI.MI", "CSPX.L",
    "VUAA.MI", "AGGH.MI", "IWDA.AS", "IUSQ.DE",
]
CRYPTO_DEFAULTS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD",
    "BNB-USD", "ADA-USD", "LINK-USD", "AVAX-USD",
]
WATCHLIST_DEFAULTS = ["CRDO", "NVTS", "AEHR", "TPRO", "ONDS", "FCEL"]

FALLBACK_SP500 = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","META","BRK-B","LLY","AVGO","JPM",
    "TSLA","WMT","XOM","UNH","V","MA","COST","ORCL","HD","PG","NFLX","ABBV",
    "CRM","BAC","CVX","KO","MRK","AMD","PEP","ADBE","TMO","LIN","CSCO","ACN",
    "MCD","WFC","QCOM","IBM","CAT","GE","AMGN","TXN","PM","ISRG","NOW","INTU",
    "DIS","GS","SPGI","UBER","AMAT","LOW","BKNG","BLK","AXP","NEE","HON","PFE",
]
FALLBACK_NASDAQ = [
    "AAPL","MSFT","NVDA","AMZN","META","AVGO","GOOGL","GOOG","TSLA","COST",
    "NFLX","AMD","PEP","ADBE","CSCO","TMUS","QCOM","INTU","AMGN","TXN","ISRG",
    "BKNG","HON","AMAT","LRCX","MU","ADI","PANW","KLAC","SBUX","GILD","MDLZ",
    "VRTX","REGN","SNPS","CDNS","MELI","CRWD","ORLY","CTAS","MAR","ABNB","FTNT",
]

@st.cache_data(ttl=900, show_spinner=False)
def get_history(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Download adjusted daily history. Cached for 15 minutes."""
    try:
        df = yf.Ticker(symbol).history(period=period, auto_adjust=True, actions=False)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        if "Close" not in df:
            return pd.DataFrame()
        df = df.dropna(subset=["Close"])
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_universe(kind: str) -> list[str]:
    """Try to load current index constituents, with a small fallback if unavailable."""
    try:
        if kind == "S&P 500":
            tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
            col = "Symbol"
            syms = tables[0][col].astype(str).str.replace(".", "-", regex=False).tolist()
            if len(syms) > 100:
                return syms
        elif kind == "Nasdaq-100":
            tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
            for table in tables:
                for col in ("Ticker", "Symbol"):
                    if col in table.columns:
                        syms = table[col].astype(str).tolist()
                        syms = [s for s in syms if s.isupper() and 1 <= len(s) <= 6 and s.isalpha()]
                        if len(syms) > 50:
                            return list(dict.fromkeys(syms))
    except Exception:
        pass
    return FALLBACK_SP500 if kind == "S&P 500" else FALLBACK_NASDAQ

def pct_change(close: pd.Series, bars: int) -> float:
    if len(close) <= bars or pd.isna(close.iloc[-bars-1]) or close.iloc[-bars-1] == 0:
        return np.nan
    return float((close.iloc[-1] / close.iloc[-bars-1] - 1) * 100)

def safe_info(symbol: str) -> dict:
    try:
        # Info can be slow or unavailable; do not let it stop price analysis.
        return yf.Ticker(symbol).get_info() or {}
    except Exception:
        return {}

def analyse_symbol(symbol: str, include_fundamentals: bool = False) -> dict | None:
    hist = get_history(symbol, "2y" if include_fundamentals else "1y")
    if hist.empty or len(hist) < 30:
        return None
    close = hist["Close"].dropna()
    price = float(close.iloc[-1])
    if not math.isfinite(price) or price <= 0:
        return None
    r1w, r1m, r3m, r6m, r12m = [pct_change(close, n) for n in (5, 21, 63, 126, 252)]
    ret = close.pct_change().dropna()
    vol = float(ret.tail(60).std() * np.sqrt(252) * 100) if len(ret) >= 20 else np.nan
    ma50 = float(close.tail(50).mean()) if len(close) >= 50 else np.nan
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else np.nan
    high52 = float(close.tail(min(252, len(close))).max())
    dist_high = float((price / high52 - 1) * 100) if high52 else np.nan
    row = {
        "Ticker": symbol,
        "Prezzo": price,
        "1 settimana %": r1w,
        "1 mese %": r1m,
        "3 mesi %": r3m,
        "6 mesi %": r6m,
        "12 mesi %": r12m,
        "Volatilità ann. %": vol,
        "Media 50g": ma50,
        "Media 200g": ma200,
        "Distanza max 52s %": dist_high,
        "Ultimo dato": str(close.index[-1].date()),
    }
    if include_fundamentals:
        info = safe_info(symbol)
        row.update({
            "P/E forward": info.get("forwardPE", np.nan),
            "EV/EBITDA": info.get("enterpriseToEbitda", np.nan),
            "Crescita ricavi %": (info.get("revenueGrowth", np.nan) * 100
                                  if pd.notna(info.get("revenueGrowth", np.nan)) else np.nan),
            "Margine netto %": (info.get("profitMargins", np.nan) * 100
                                if pd.notna(info.get("profitMargins", np.nan)) else np.nan),
            "ROE %": (info.get("returnOnEquity", np.nan) * 100
                      if pd.notna(info.get("returnOnEquity", np.nan)) else np.nan),
            "Debt/Equity": info.get("debtToEquity", np.nan),
            "Market cap": info.get("marketCap", np.nan),
            "Settore": info.get("sector", "n/d"),
        })
    return row

def rank_percentile(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().sum() < 2:
        return pd.Series(50.0, index=series.index)
    rank = values.rank(pct=True) * 100
    if not higher_is_better:
        rank = 100 - rank
    return rank.fillna(50.0)

def score_stocks(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["Punteggio momentum"] = (
        rank_percentile(out["3 mesi %"]) * .35 +
        rank_percentile(out["6 mesi %"]) * .35 +
        rank_percentile(out["12 mesi %"]) * .20 +
        rank_percentile(out["Volatilità ann. %"], False) * .10
    )
    out["Punteggio qualità"] = (
        rank_percentile(out["Crescita ricavi %"]) * .30 +
        rank_percentile(out["Margine netto %"]) * .25 +
        rank_percentile(out["ROE %"]) * .25 +
        rank_percentile(out["Debt/Equity"], False) * .20
    )
    out["Punteggio valore"] = (
        rank_percentile(out["P/E forward"], False) * .40 +
        rank_percentile(out["EV/EBITDA"], False) * .35 +
        rank_percentile(out["Distanza max 52s %"], False) * .25
    )
    out["Punteggio razzo"] = (
        rank_percentile(out["1 settimana %"]) * .15 +
        rank_percentile(out["1 mese %"]) * .25 +
        rank_percentile(out["3 mesi %"]) * .35 +
        rank_percentile(out["6 mesi %"]) * .15 +
        rank_percentile(out["Volatilità ann. %"], False) * .10
    )
    # Heuristic flags, not a fair-value estimate or a buy signal.
    out["Possibile sconto"] = (
        (out["Distanza max 52s %"] <= -20) &
        (out["P/E forward"].notna()) &
        (out["P/E forward"] > 0) &
        (out["Punteggio qualità"] >= 50)
    )
    out["Sotto media 200g"] = out["Prezzo"] < out["Media 200g"]
    out["Rischio elevato"] = (
        (out["Volatilità ann. %"] > 60) |
        (out["Debt/Equity"] > 250) |
        (out["Distanza max 52s %"] < -35)
    )
    return out.sort_values("Punteggio razzo", ascending=False)

def scan_many(symbols: list[str], include_fundamentals: bool, limit: int) -> pd.DataFrame:
    rows = []
    progress = st.progress(0, text="Avvio analisi…")
    unique = list(dict.fromkeys([str(s).strip().upper() for s in symbols if str(s).strip()]))[:limit]
    for i, symbol in enumerate(unique):
        result = analyse_symbol(symbol, include_fundamentals=include_fundamentals)
        if result:
            rows.append(result)
        progress.progress((i + 1) / max(len(unique), 1), text=f"Analisi {i+1}/{len(unique)}: {symbol}")
        # A small pause reduces bursts against the free data source.
        if i % 8 == 7:
            time.sleep(.2)
    progress.empty()
    df = pd.DataFrame(rows)
    return score_stocks(df) if include_fundamentals and not df.empty else df

def fmt_table(df: pd.DataFrame, money: bool = False) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if col == "Prezzo" or col.startswith("Media "):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(3)
        elif "%" in col or col.startswith("Punteggio"):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(1)
    return out

def show_market_dashboard():
    st.subheader("Andamento dei mercati")
    st.caption("Percentuali calcolate sui dati storici scaricati. Per i futures, il simbolo rappresenta il contratto continuo disponibile sulla fonte.")
    rows = []
    for name, symbol in MARKETS.items():
        h = get_history(symbol, "1y")
        if h.empty or len(h) < 2:
            rows.append({"Mercato": name, "Ticker": symbol, "Ultimo": np.nan,
                         "1 giorno %": np.nan, "1 settimana %": np.nan,
                         "1 mese %": np.nan, "3 mesi %": np.nan, "Ultimo dato": "non disponibile"})
            continue
        c = h["Close"].dropna()
        rows.append({
            "Mercato": name, "Ticker": symbol, "Ultimo": float(c.iloc[-1]),
            "1 giorno %": pct_change(c, 1), "1 settimana %": pct_change(c, 5),
            "1 mese %": pct_change(c, 21), "3 mesi %": pct_change(c, 63),
            "Ultimo dato": str(c.index[-1].date()),
        })
    st.dataframe(fmt_table(pd.DataFrame(rows)), use_container_width=True, hide_index=True)
    st.caption("Se un mercato appare non disponibile, il simbolo potrebbe non essere supportato dalla fonte gratuita in quel momento.")

def render_asset_page(asset_type: str, defaults: list[str]):
    st.subheader(f"Pagina {asset_type}")
    raw = st.text_area(
        "Ticker da analizzare (separati da virgola)",
        value=", ".join(defaults),
        height=90,
        key=f"tickers_{asset_type}",
        help="Puoi sostituire i simboli con quelli che vuoi monitorare. Esempi: VWCE.DE, BTC-USD.",
    )
    limit = st.slider("Numero massimo di strumenti", 4, 40, min(max(len(defaults), 4), 20), key=f"limit_{asset_type}")
    if st.button(f"Aggiorna {asset_type}", key=f"scan_{asset_type}", type="primary"):
        symbols = [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()]
        with st.spinner("Scarico lo storico…"):
            df = scan_many(symbols, include_fundamentals=False, limit=limit)
        if df.empty:
            st.warning("Nessun dato disponibile per i ticker inseriti. Controlla i simboli e riprova.")
        else:
            st.session_state[f"results_{asset_type}"] = df
    result = st.session_state.get(f"results_{asset_type}", pd.DataFrame())
    if not result.empty:
        cols = ["Ticker", "Prezzo", "1 settimana %", "1 mese %", "3 mesi %", "6 mesi %", "12 mesi %", "Volatilità ann. %", "Ultimo dato"]
        st.dataframe(fmt_table(result[[c for c in cols if c in result.columns]]), use_container_width=True, hide_index=True)
        st.download_button("Scarica CSV", result.to_csv(index=False).encode("utf-8"), f"chatinvestment_{asset_type.lower()}.csv", "text/csv")

# --- Sidebar ---
with st.sidebar:
    st.header("Impostazioni")
    universe = st.selectbox("Universo azionario", ["Watchlist", "S&P 500", "Nasdaq-100"])
    max_assets = st.slider("Numero massimo titoli da scansionare", 5, 100, 30, step=5)
    st.caption("La prima scansione di molti titoli può richiedere tempo. Parti da 20–30.")

tabs = st.tabs(["📈 Mercati", "🔎 Scanner azioni", "🚀 Prossimo razzo", "🏷️ Azioni a sconto", "📊 ETF", "₿ Crypto", "📌 Candidato", "🧪 Metodo", "📱 Guida iPhone"])

with tabs[0]:
    show_market_dashboard()
    if st.button("Ricarica dati mercati", key="reload_markets"):
        st.cache_data.clear()
        st.rerun()

# Build equity universe only when needed.
if universe == "Watchlist":
    equity_symbols = WATCHLIST_DEFAULTS
elif universe == "S&P 500":
    equity_symbols = get_universe("S&P 500")
else:
    equity_symbols = get_universe("Nasdaq-100")

with tabs[1]:
    st.subheader("Scanner azionario")
    st.write("Confronta momentum, qualità, valutazione e alcuni indicatori di rischio.")
    custom = st.text_input("Aggiungi ticker (facoltativo, separati da virgola)", value="")
    if st.button("Avvia scanner azioni", type="primary", key="start_equity"):
        symbols = equity_symbols + [x.strip() for x in custom.split(",") if x.strip()]
        with st.spinner("Analisi dei titoli: può richiedere qualche minuto…"):
            results = scan_many(symbols, True, max_assets)
        if results.empty:
            st.warning("Nessun risultato. Riprova più tardi o usa una watchlist più piccola.")
        else:
            st.session_state["equity_results"] = results
    df = st.session_state.get("equity_results", pd.DataFrame())
    if not df.empty:
        display_cols = ["Ticker", "Prezzo", "1 settimana %", "1 mese %", "3 mesi %", "6 mesi %", "12 mesi %",
                        "Punteggio momentum", "Punteggio qualità", "Punteggio valore", "Punteggio razzo",
                        "Possibile sconto", "Rischio elevato", "Ultimo dato"]
        st.dataframe(fmt_table(df[[c for c in display_cols if c in df.columns]]), use_container_width=True, hide_index=True)
        st.download_button("Scarica risultati scanner CSV", df.to_csv(index=False).encode("utf-8"), "chatinvestment_scanner.csv", "text/csv")

with tabs[2]:
    st.subheader("🚀 Modalità “Prossimo razzo”")
    st.write("Ordina i titoli per accelerazione recente e momentum su più orizzonti. Non prevede con certezza i futuri rialzi.")
    df = st.session_state.get("equity_results", pd.DataFrame())
    if df.empty:
        st.info("Prima avvia lo scanner nella scheda “Scanner azioni”.")
    else:
        n = st.slider("Quanti candidati mostrare", 3, min(20, len(df)), min(10, len(df)), key="rocket_n")
        cols = ["Ticker", "Prezzo", "1 settimana %", "1 mese %", "3 mesi %", "6 mesi %", "Volatilità ann. %", "Punteggio razzo", "Rischio elevato"]
        st.dataframe(fmt_table(df.sort_values("Punteggio razzo", ascending=False)[[c for c in cols if c in df.columns]].head(n)),
                     use_container_width=True, hide_index=True)
        st.warning("Un punteggio alto non equivale a una probabilità di rialzo. Titoli con momentum elevato possono invertire rapidamente.")

with tabs[3]:
    st.subheader("🏷️ Modalità “Azioni a sconto”")
    st.write("Euristica iniziale: titolo lontano dal massimo a 52 settimane, multiplo forward positivo e punteggio qualità almeno mediano.")
    df = st.session_state.get("equity_results", pd.DataFrame())
    if df.empty:
        st.info("Prima avvia lo scanner nella scheda “Scanner azioni”.")
    else:
        discounted = df[df["Possibile sconto"]].copy()
        if discounted.empty:
            st.info("Nessun titolo soddisfa tutti i criteri attuali. Non significa che non esistano opportunità.")
        else:
            cols = ["Ticker", "Prezzo", "Distanza max 52s %", "P/E forward", "EV/EBITDA",
                    "Crescita ricavi %", "Margine netto %", "ROE %", "Sotto media 200g", "Rischio elevato"]
            st.dataframe(fmt_table(discounted[[c for c in cols if c in discounted.columns]]),
                         use_container_width=True, hide_index=True)
        st.caption("Essere scesi dal massimo non prova che un titolo sia sottovalutato. Verificare debito, utili, prospettive e notizie.")

with tabs[4]:
    render_asset_page("ETF", ETF_DEFAULTS)

with tabs[5]:
    render_asset_page("Crypto", CRYPTO_DEFAULTS)
    st.warning("Le crypto possono subire oscillazioni estreme; lo storico non garantisce risultati futuri.")

with tabs[6]:
    st.subheader("Candidato: scheda di verifica")
    ticker = st.text_input("Ticker da esaminare", value="CRDO", key="candidate_ticker").strip().upper()
    if st.button("Analizza candidato", key="candidate_button", type="primary"):
        row = analyse_symbol(ticker, include_fundamentals=True)
        if not row:
            st.warning("Dati non disponibili per questo ticker.")
        else:
            st.session_state["candidate_result"] = row
    row = st.session_state.get("candidate_result")
    if row:
        c1, c2, c3 = st.columns(3)
        c1.metric("Prezzo ultimo dato", f'{row.get("Prezzo", np.nan):,.3f}')
        c2.metric("1 mese", f'{row.get("1 mese %", np.nan):.1f}%' if pd.notna(row.get("1 mese %")) else "n/d")
        c3.metric("Volatilità ann.", f'{row.get("Volatilità ann. %", np.nan):.1f}%' if pd.notna(row.get("Volatilità ann. %")) else "n/d")
        st.json({k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in row.items()})
        st.text_area("Domanda pronta per ChatGPT", value=(
            f"Analizza {ticker} con orizzonte 2–5 giorni e 1–4 settimane. "
            "Distingui prezzi verificati da ipotesi, valuta scenario rialzista/neutrale/ribassista, "
            "livello di invalidazione, rischi e rapporto rischio/rendimento. Non presentare stime come certezze."
        ), height=110)
    st.caption("Questa scheda non esegue ordini e non è una raccomandazione personalizzata.")

with tabs[7]:
    st.subheader("Metodo e limiti")
    st.markdown("""
- **Performance**: variazioni calcolate sul prezzo di chiusura storico disponibile.
- **Momentum**: confronta rendimenti su più finestre temporali.
- **Qualità e valore**: dipendono dai fondamentali che la fonte riesce a fornire; molti campi possono essere vuoti.
- **Prossimo razzo**: classifica euristica, non previsione statistica calibrata.
- **Azioni a sconto**: filtro preliminare, non calcolo del fair value.
- **Dati**: aggiornati quando vengono richiesti, con cache di circa 15 minuti per lo storico.
- **Affidabilità**: la fonte gratuita può ritardare, limitare richieste o restituire simboli non disponibili.
- **Nessun ordine automatico**: l'app è uno strumento di analisi, non collega il conto Fineco e non opera con leva.
""")
    st.caption("Prima di usare qualsiasi idea operativa, verifica quotazioni, spread, liquidità, notizie e costi direttamente presso il tuo intermediario.")

with tabs[8]:
    st.subheader("Aggiornare ChatInvestment da iPhone")
    st.markdown("""
1. Apri il repository GitHub collegato alla tua app.
2. Apri `app.py` e premi la matita **Edit**.
3. Prima di sostituire il codice, conserva una copia del file attuale in Note o in un file di testo.
4. Incolla il nuovo contenuto di `app.py` e salva con **Commit changes**.
5. Ripeti per `requirements.txt` e per gli altri file inclusi nel pacchetto, mantenendo i percorsi indicati.
6. Attendi che Streamlit termini il redeploy; poi apri l'app e prova prima la scheda Mercati e una watchlist piccola.
""")
    st.link_button("Apri repository GitHub", "https://github.com/UchihaDD/ChatInvestment")
    st.link_button("Apri app pubblicata", "https://chatinvestment-j4h8fgt8jx29p53tygykab.streamlit.app")

st.divider()
st.caption(f"ChatInvestment • sessione {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} • Solo analisi informativa.")
