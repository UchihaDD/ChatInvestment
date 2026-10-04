import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from datetime import datetime, timezone

st.set_page_config(page_title="Investment Scanner", page_icon="🔎", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 3rem; max-width: 1200px;}
h1 {font-size: 2rem !important;}
div[data-testid="stMetricValue"] {font-size: 1.35rem;}
@media (max-width: 700px) {
  .block-container {padding-left: .8rem; padding-right: .8rem;}
  h1 {font-size: 1.6rem !important;}
}
</style>
""", unsafe_allow_html=True)

st.title("🔎 Investment Scanner")
st.caption("V2 · scanner quantitativo gratuito · progettato per uso da iPhone")

PROFILES = {
    "1–3 mesi": {"m": .50, "g": .10, "v": .10, "q": .10, "risk": .20},
    "6–12 mesi": {"m": .30, "g": .25, "v": .15, "q": .20, "risk": .10},
    "3–5 anni": {"m": .10, "g": .30, "v": .20, "q": .30, "risk": .10},
    "Bilanciato": {"m": .25, "g": .25, "v": .15, "q": .25, "risk": .10},
}

DEFAULT_ETFS = ["VWCE.DE","SWDA.MI","EIMI.MI","CSPX.L","VUAA.MI","AGGH.MI","IWDA.AS","IUSQ.DE"]
DEFAULT_CRYPTO = ["BTC-USD","ETH-USD","SOL-USD","XRP-USD","BNB-USD","ADA-USD","LINK-USD","AVAX-USD"]

@st.cache_data(ttl=86400, show_spinner=False)
def sp500_universe():
    try:
        t = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        return t["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()
    except Exception:
        return ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","AVGO","TSLA","BRK-B","LLY","JPM","V","MA","XOM","COST","WMT","NFLX","ORCL","AMD","ADBE"]

@st.cache_data(ttl=86400, show_spinner=False)
def nasdaq100_universe():
    try:
        t = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")[4]
        col = [c for c in t.columns if str(c).lower() in ["ticker","ticker symbol","symbol"]]
        if col:
            return t[col[0]].astype(str).str.replace(".", "-", regex=False).tolist()
    except Exception:
        pass
    return ["AAPL","MSFT","NVDA","AMZN","META","AVGO","GOOGL","GOOG","TSLA","COST","NFLX","AMD","ADBE","QCOM","INTU","AMAT","MU","PANW","CRWD","PLTR"]

@st.cache_data(ttl=3600, show_spinner=False)
def crypto_universe():
    try:
        url="https://api.coingecko.com/api/v3/coins/markets"
        params={"vs_currency":"usd","order":"market_cap_desc","per_page":100,"page":1,"sparkline":"false"}
        r=requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data=r.json()
        return [f"{x['id']}" for x in data]
    except Exception:
        return ["bitcoin","ethereum","solana","ripple","binancecoin","cardano","chainlink","avalanche-2"]

def normalize(s, higher=True):
    s=pd.to_numeric(s, errors="coerce")
    if not higher: s=-s
    return s.rank(pct=True)*100

def safe(v):
    try:
        return float(v) if v is not None and not pd.isna(v) else np.nan
    except: return np.nan

@st.cache_data(ttl=1800, show_spinner=False)
def scan_ticker(symbol, period="2y"):
    try:
        tk=yf.Ticker(symbol)
        h=tk.history(period=period, auto_adjust=True)
        if h is None or h.empty or len(h)<70: return None
        c=h["Close"].dropna()
        if len(c)<70: return None
        def ret(n):
            return c.iloc[-1]/c.iloc[-n-1]-1 if len(c)>n else np.nan
        r1,r3,r6,r12=ret(21),ret(63),ret(126),ret(252)
        vol=float(c.pct_change().dropna().tail(60).std()*np.sqrt(252))
        ma50=float(c.tail(50).mean())
        ma200=float(c.tail(min(200,len(c))).mean())
        high=float(c.tail(min(252,len(c))).max())
        info=tk.get_info()
        return {
            "Ticker":symbol, "Prezzo":float(c.iloc[-1]),
            "R1M":r1*100,"R3M":r3*100,"R6M":r6*100,"R12M":r12*100,
            "Volatilità":vol*100,"Distanza 52W":(c.iloc[-1]/high-1)*100,
            "MA50":bool(c.iloc[-1]>ma50),"MA200":bool(c.iloc[-1]>ma200),
            "P/E Fwd":safe(info.get("forwardPE")),"EV/EBITDA":safe(info.get("enterpriseToEbitda")),
            "Crescita ricavi":safe(info.get("revenueGrowth"))*100 if safe(info.get("revenueGrowth"))==safe(info.get("revenueGrowth")) else np.nan,
            "Margine netto":safe(info.get("profitMargins"))*100 if safe(info.get("profitMargins"))==safe(info.get("profitMargins")) else np.nan,
            "ROE":safe(info.get("returnOnEquity"))*100 if safe(info.get("returnOnEquity"))==safe(info.get("returnOnEquity")) else np.nan,
            "Debt/Equity":safe(info.get("debtToEquity")),
            "FCF":safe(info.get("freeCashflow")),
            "Nome":info.get("shortName") or symbol,
            "Settore":info.get("sector") or "N/D",
            "Market Cap":safe(info.get("marketCap")),
        }
    except Exception:
        return None

def build_scores(df):
    df=df.copy()
    df["Momentum"]=(normalize(df.R3M)*.25+normalize(df.R6M)*.35+normalize(df.R12M)*.25+
                    normalize(df["Distanza 52W"])*.05+normalize(df.Volatilità,False)*.10)
    df["Growth"]=(normalize(df["Crescita ricavi"])*.55+normalize(df["Margine netto"])*.20+normalize(df.ROE)*.25)
    df["Value"]=(normalize(df["P/E Fwd"],False)*.35+normalize(df["EV/EBITDA"],False)*.35+normalize(df.FCF)*.30)
    df["Quality"]=(normalize(df.ROE)*.35+normalize(df["Margine netto"])*.35+normalize(df.Debt/Equity,False)*.30)
    # Risk score: higher means fewer obvious quantitative risk flags.
    risk=100.0
    risk = risk - np.where(df["Volatilità"]>60,20,0)
    risk = risk - np.where(df["Debt/Equity"]>250,20,0)
    risk = risk - np.where(df["Distanza 52W"]<-30,15,0)
    risk = risk - np.where((df["MA50"]==False)&(df["MA200"]==False),15,0)
    df["Risk discipline"]=np.clip(risk,0,100)
    p=st.session_state.get("profile","Bilanciato")
    w=PROFILES[p]
    df["Scanner Score"]=(df.Momentum*w["m"]+df.Growth*w["g"]+df.Value*w["v"]+
                         df.Quality*w["q"]+df["Risk discipline"]*w["risk"])
    return df.sort_values("Scanner Score",ascending=False,na_position="last").reset_index(drop=True)

with st.sidebar:
    st.header("Configurazione")
    profile=st.selectbox("Orizzonte",list(PROFILES.keys()),index=3)
    st.session_state["profile"]=profile
    universe=st.selectbox("Universo",[
        "S&P 500","Nasdaq-100","ETF selezionati","Crypto top 100","Watchlist personale"
    ])
    period=st.selectbox("Storico prezzi",["1y","2y","5y"],index=1)
    max_assets=st.slider("Numero massimo strumenti",10,100,50,step=10)
    if universe=="Watchlist personale":
        custom=st.text_area("Ticker separati da virgola","AAPL,MSFT,NVDA,AMZN,GOOGL,META,AVGO,TSLA")
    else:
        custom=""
    st.caption("Dati: fonti gratuite; disponibilità e qualità possono variare.")

tabs=st.tabs(["🔎 Scanner","📌 Candidato","🧪 Metodo","📱 Uso da iPhone"])

with tabs[0]:
    st.subheader(f"Scanner · {profile}")
    if universe=="S&P 500":
        symbols=sp500_universe()[:max_assets]
    elif universe=="Nasdaq-100":
        symbols=nasdaq100_universe()[:max_assets]
    elif universe=="ETF selezionati":
        symbols=DEFAULT_ETFS[:max_assets]
    elif universe=="Crypto top 100":
        # CoinGecko IDs need mapping to Yahoo symbols for this simple free V2.
        symbols=DEFAULT_CRYPTO[:max_assets]
    else:
        symbols=[x.strip().upper() for x in custom.replace("\n",",").split(",") if x.strip()][:max_assets]

    st.caption(f"Universo operativo: {len(symbols)} strumenti · premi il pulsante per aggiornare.")
    run=st.button("🚀 Avvia scansione",type="primary",use_container_width=True)

    if run:
        rows=[]
        bar=st.progress(0)
        for i,s in enumerate(symbols):
            row=scan_ticker(s,period)
            if row: rows.append(row)
            bar.progress((i+1)/len(symbols))
        bar.empty()
        if rows:
            df=build_scores(pd.DataFrame(rows))
            st.session_state["df"]=df
            st.session_state["scan_time"]=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        else:
            st.error("Nessun dato disponibile. Riprova o riduci l'universo.")

    if "df" in st.session_state:
        df=st.session_state["df"]
        c1,c2,c3=st.columns(3)
        c1.metric("Strumenti",len(df))
        c2.metric("Sopra MA50",int(df.MA50.sum()))
        c3.metric("Sopra MA200",int(df.MA200.sum()))
        st.caption(f"Ultima scansione: {st.session_state.get('scan_time','—')}")
        n=st.slider("Risultati",5,min(50,len(df)),min(20,len(df)))
        cols=["Ticker","Nome","Prezzo","R3M","R6M","R12M","Volatilità","P/E Fwd","Crescita ricavi","ROE","Momentum","Growth","Value","Quality","Risk discipline","Scanner Score"]
        out=df.head(n)[cols].copy()
        out.columns=["Ticker","Nome","Prezzo","3M %","6M %","12M %","Vol %","P/E","Ricavi %","ROE %","Momentum","Growth","Value","Quality","Risk","Scanner"]
        st.dataframe(out,use_container_width=True,hide_index=True)
        st.download_button("⬇️ Scarica CSV",df.to_csv(index=False).encode("utf-8-sig"),"investment_scanner_results.csv","text/csv")
        st.info("Lo score serve a ordinare i candidati all'interno della scansione. Non è una previsione di rendimento né una raccomandazione.")

with tabs[1]:
    st.subheader("📌 Candidato da approfondire")
    if "df" not in st.session_state:
        st.info("Esegui prima una scansione.")
    else:
        df=st.session_state["df"]
        choice=st.selectbox("Ticker",df.Ticker.tolist())
        row=df[df.Ticker==choice].iloc[0]
        st.markdown(f"### {row['Nome']} · `{choice}`")
        a,b,c=st.columns(3)
        a.metric("Scanner",f"{row['Scanner Score']:.1f}/100")
        b.metric("Momentum",f"{row['Momentum']:.1f}")
        c.metric("Quality",f"{row['Quality']:.1f}")
        st.write("**Perché è entrato nello screening**")
        reasons=[]
        if row.R12M>0: reasons.append(f"rendimento 12 mesi {row.R12M:.1f}%")
        if row.R6M>0: reasons.append(f"rendimento 6 mesi {row.R6M:.1f}%")
        if row.MA50: reasons.append("prezzo sopra MA50")
        if row.MA200: reasons.append("prezzo sopra MA200")
        if pd.notna(row["Crescita ricavi"]) and row["Crescita ricavi"]>0: reasons.append(f"crescita ricavi {row['Crescita ricavi']:.1f}%")
        st.write(" · ".join(reasons) if reasons else "Nessun segnale quantitativo forte disponibile.")
        st.write("**Rischi quantitativi da verificare**")
        risks=[]
        if row.Volatilità>60: risks.append("volatilità elevata")
        if pd.notna(row["Debt/Equity"]) and row["Debt/Equity"]>250: risks.append("Debt/Equity elevato")
        if row["Distanza 52W"]<-30: risks.append("molto distante dal massimo a 52 settimane")
        if not row.MA50 and not row.MA200: risks.append("sotto MA50 e MA200")
        st.write(" · ".join(risks) if risks else "Nessun flag quantitativo principale rilevato.")
        prompt=f"""Analizza {choice} come candidato di investimento per un orizzonte {profile}.
Usa informazioni aggiornate e fonti primarie quando possibile.
Dati dello scanner:
- Momentum: {row.Momentum:.1f}
- Growth: {row.Growth:.1f}
- Value: {row.Value:.1f}
- Quality: {row.Quality:.1f}
- Risk discipline: {row['Risk discipline']:.1f}
- 3M: {row.R3M:.1f}%, 6M: {row.R6M:.1f}%, 12M: {row.R12M:.1f}%
- P/E forward: {row['P/E Fwd']}
- Crescita ricavi: {row['Crescita ricavi']}%
- ROE: {row.ROE}%
- Debt/Equity: {row['Debt/Equity']}
Voglio: tesi, catalizzatori, cosa è già prezzato, rischi, dati contrari alla tesi e cosa monitorare nei prossimi mesi. Non dare certezze e separa fatti da interpretazioni."""
        st.markdown("### Prompt per la ricerca AI")
        st.code(prompt,language="text")
        st.caption("Copia questo prompt in ChatGPT per fare la fase qualitativa senza pagare API esterne.")

with tabs[2]:
    st.subheader("🧪 Come funziona V2")
    st.markdown("""
**1. Universo** → S&P 500 / Nasdaq-100 / ETF / watchlist.

**2. Quant** → momentum, crescita, value, quality e disciplina del rischio.

**3. Profilo temporale** → i pesi cambiano tra 1–3 mesi, 6–12 mesi, 3–5 anni e bilanciato.

**4. Ricerca qualitativa** → il software genera un prompt pronto per ChatGPT. Non finge di avere un LLM finanziato da un'API gratuita.

**5. Decisione** → lo scanner crea una lista di situazioni da studiare; la decisione rimane tua.
    """)
    st.warning("V2 non è ancora un backtest point-in-time professionale. Prima di usarla per capitale reale, la prossima fase deve validare il metodo su dati storici evitando look-ahead e survivorship bias.")

with tabs[3]:
    st.subheader("📱 Il tuo flusso quotidiano")
    st.markdown("""
### Una volta pubblicata
1. Apri il link dello scanner in Safari.
2. Premi **Condividi → Aggiungi alla schermata Home**.
3. Avrai un'icona come una normale app.
4. Scegli l'orizzonte.
5. Scegli l'universo.
6. Premi **Avvia scansione**.
7. Apri i candidati.
8. Copia il prompt AI in ChatGPT.
9. Approfondisci solo i candidati che superano il controllo qualitativo.

Non devi installare Python, usare terminale o avere un PC.
    """)

st.divider()
st.caption("Investment Scanner V2 · prototipo di ricerca quantitativa · nessun trading automatico · nessuna garanzia di rendimento.")
