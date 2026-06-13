import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import os
import re
import requests

@st.cache_data(ttl=1800)
def get_sentiment(ticker):
    try:
        stock = yf.Ticker(ticker)
        rec_df = stock.recommendations
        
        # 1. Analyse über die Analysten-Ratings (rec_df)
        if rec_df is not None and not rec_df.empty and 'toGrade' in rec_df.columns:
            recent = rec_df.tail(10)
            
            # Wir schauen uns die Ratings an
            grades = [str(g).upper() for g in recent['toGrade']]
            
            # Zähle, wie oft "STRONG BUY" vorkommt
            strong_buy_count = sum(1 for g in grades if "STRONG BUY" in g or "STRONG_BUY" in g)
            
            # Wenn sehr viele Strong Buys dabei sind -> 3 Bälle
            if strong_buy_count >= 3: 
                return "🟢🟢🟢"
            
            # Sonst Durchschnittsberechnung
            def score_grade(grade):
                if any(x in grade for x in ["STRONG BUY", "STRONG_BUY", "BUY", "OUTPERFORM"]): return 1
                if any(x in grade for x in ["HOLD", "NEUTRAL"]): return 3
                return 5
            
            avg = sum([score_grade(g) for g in grades]) / len(grades)
            
            if avg <= 1.5: return "🟢" # Normales Buy
            if avg <= 3.5: return "⚪"
            return "🔴"
            
        # 2. Fallback auf info (falls rec_df keine Details liefert)
        info = stock.info
        rec_key = info.get("recommendationKey", "").upper().replace("_", " ")
        
        if "STRONG BUY" in rec_key: return "🟢🟢🟢"
        if any(x in rec_key for x in ["BUY", "OUTPERFORM"]): return "🟢"
        return "⚪"
        
    except Exception:
        return "⚪"
    
def style_percentage(val):
    """Färbt Prozentwerte (Strings oder Floats) nach deiner Logik ein."""
    if not val:
        return ""
    
    try:
        if isinstance(val, str):
            clean_val = val.replace('%', '').replace('+', '').replace(' ', '')
            num = float(clean_val)
        else:
            num = float(val)
    except ValueError:
        return ""

    if num >= 11:
        return "color: #2ecc71; font-weight: bold;"       # Dunkelgrün (Sattes Grün)
    elif 0 < num < 11:
        return "color: #a3e4d7;"                         # Hellgrün / Mint
    elif -11 < num < 0:
        return "color: #f9e79f;"                         # Hellrot / Orange-Rot
    elif num <= -11:
        return "color: #e74c3c; font-weight: bold;"       # Dunkelrot (Kräftiges Rot)
    return ""

def style_tendency(val):
    """Stylt die neuen Symbol-Indikatoren in der Tabelle."""
    if not val or not isinstance(val, str):
        return ""
    
    if "🟢🟢🟢" in val or "🔴🔴🔴" in val:
        return "font-size: 1.1rem; text-align: center; font-weight: bold;"
    elif "🟢" in val or "🔴" in val:
        return "font-size: 1.1rem; text-align: center;"
    elif "⚪" in val:
        return "font-size: 1.1rem; text-align: center; opacity: 0.5;"
    return ""

# Setze den Seiten-Modus (wide ist für Tabellen immer besser!)
st.set_page_config(layout="wide")

# Sidebar-Optionen – hier entscheidet der User, was er sehen will
st.sidebar.header("Anzeige-Optionen")
mobile_mode = st.sidebar.toggle("Kompakt-Ansicht (Tablet)", value=False)

# Seitenkonfiguration
st.set_page_config(page_title="Analysten-Radar", layout="wide")

st.title("📊 Mein Analysten-Radar")
st.caption("Tägliche Aggregation von Analystenmeinungen mit dauerhafter Watchlist")

# Path für die Speicherdatei auf der Festplatte
WATCHLIST_FILE = "watchlist.json"

# Funktion: Watchlist von Festplatte laden
def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return ["NVDA", "IREN", "AAPL", "MSFT"]
    return ["NVDA", "IREN", "AAPL", "MSFT"]

# Funktion: Watchlist auf Festplatte speichern
def save_watchlist(watchlist):
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(watchlist, f)
    except Exception as e:
        st.sidebar.error(f"Fehler beim Speichern der Watchlist: {e}")

# Watchlist im Session State initialisieren
if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

# --- SIDEBAR: AKTIEN MANAGEMENT ---
st.sidebar.header("🔍 Watchlist verwalten")

new_ticker = st.sidebar.text_input("Aktien-Kürzel suchen (z.B. AMD, TSLA, BTC-USD):").strip().upper()

if st.sidebar.button("➕ Zur Watchlist hinzufügen"):
    if new_ticker:
        if new_ticker in st.session_state.watchlist:
            st.sidebar.warning(f"{new_ticker} ist bereits in deiner Watchlist.")
        else:
            with st.spinner(f"Prüfe {new_ticker} bei Yahoo Finance..."):
                try:
                    check_stock = yf.Ticker(new_ticker)
                    if "currentPrice" in check_stock.info or "regularMarketPrice" in check_stock.info:
                        st.session_state.watchlist.append(new_ticker)
                        save_watchlist(st.session_state.watchlist)
                        st.sidebar.success(f"📈 {new_ticker} erfolgreich hinzugefügt und gespeichert!")
                    else:
                        st.sidebar.error(f"Kürzel {new_ticker} gefunden, aber keine Kursdaten verfügbar.")
                except Exception:
                    st.sidebar.error(f"Kürzel '{new_ticker}' wurde nicht gefunden.")
    else:
        st.sidebar.error("Bitte gib zuerst ein Kürzel ein.")

st.sidebar.write("---")

# Watchlist bearbeiten (Löschen-Funktion)
old_watchlist = st.session_state.watchlist.copy()
updated_watchlist = st.sidebar.multiselect(
    "Aktuelle Watchlist (Kürzel abwählen zum Entfernen):",
    options=st.session_state.watchlist,
    default=st.session_state.watchlist
)

if updated_watchlist != old_watchlist:
    st.session_state.watchlist = updated_watchlist
    save_watchlist(st.session_state.watchlist)
    st.rerun()

# Auswahl für die Detailansicht
if st.session_state.watchlist:
    selected_ticker = st.sidebar.selectbox("Aktie für Detailansicht auswählen:", st.session_state.watchlist)
else:
    selected_ticker = None
    st.info("Deine Watchlist ist leer. Nutze die Suche in der Seitenleiste, um Aktien hinzuzufügen!")

# --- DATENABRUF (GECACHED) ---
@st.cache_data(ttl=3600)
def get_stock_info(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        return stock.info
    except Exception:
        return None

# --- HAUPTBEREICH: ANSICHTEN ---
view_mode = st.radio(
    "Ansicht wählen:",
    options=["📋 Gesamtübersicht (Watchlist)", "🔍 Detail-Analyse"],
    horizontal=True
)

st.write("---")

# --- FUNCTION: GLOBAL MARKET GAINERS ABRUFEN ---
@st.cache_data(ttl=1800)
def get_market_gainers():
    try:
        url = "https://finance.yahoo.com/markets/stocks/gainers/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            match = re.search(r'data-url="[^"]+DAY_GAINERS[^"]*".*?>({.*?})</script>', response.text)
            
            if match:
                json_data = json.loads(match.group(1))
                body_str = json_data.get("body", "{}")
                body_data = json.loads(body_str)
                
                records = body_data.get("finance", {}).get("result", [{}])[0].get("records", [])
                
                table_data = []
                for rec in records:
                    ticker = rec.get("ticker", "N/A")
                    company = rec.get("companyName", "N/A")
                    price = rec.get("regularMarketPrice", {}).get("raw", 0.0)
                    change_pct = rec.get("regularMarketChangePercent", {}).get("raw", 0.0)
                    
                    table_data.append({
                        "Ticker": ticker,
                        "Unternehmen": company,
                        "Kurs": f"{price:.2f} USD",
                        "Performance (Heute)": f"+{change_pct:.2f} %"
                    })
                
                if table_data:
                    return pd.DataFrame(table_data).head(5)
                    
    except Exception as e:
        print(f"JSON-Parsing-Fehler: {e}")
    return None

# ==========================================
# MODUS 1: GESAMTÜBERSICHT
# ==========================================
if view_mode == "📋 Gesamtübersicht (Watchlist)":
    
    col_watchlist, col_gainers = st.columns([13, 7])
    
    # --- LINKE SPALTE: WATCHLIST ---
    with col_watchlist:
        st.subheader("Deine Watchlist im Überblick")
        
        if not st.session_state.watchlist:
            st.info("Deine Watchlist ist noch leer. Füge links in der Seitenleiste ein paar Kürzel hinzu!")
        else:
            table_data = []
            with st.spinner("Lade Übersicht für deine Watchlist..."):
                for ticker in st.session_state.watchlist:
                    info = get_stock_info(ticker)
                    
                    if info:
                        company_name = info.get("longName", ticker)
                        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                        currency = info.get("currency", "USD")
                        target_mean = info.get("targetMeanPrice")
                        
                        if current_price and target_mean:
                            upside_pct = ((target_mean - current_price) / current_price) * 100
                            upside_str = f"{upside_pct:+.1f} %"
                        else:
                            upside_str = "N/A"
                            
                        target_str = f"{target_mean:.2f} {currency}" if target_mean else "N/A"
                        price_str = f"{current_price:.2f} {currency}" if current_price else "N/A"
                        
                        # --- EINHEITLICHER AUFRUF ---
                        trend_value = get_sentiment(ticker)
                        
                        table_data.append({
                            "Ticker": ticker,
                            "Unternehmen": company_name,
                            "Aktueller Kurs": price_str,
                            "Kursziel (Schnitt)": target_str,
                            "Potenzial (Upside)": upside_str,
                            "Analysten-Tendenz": trend_value
                        })
                    else:
                        table_data.append({
                            "Ticker": ticker,
                            "Unternehmen": f"Keine Daten ({ticker})",
                            "Aktueller Kurs": "N/A",
                            "Kursziel (Schnitt)": "N/A",
                            "Potenzial (Upside)": "N/A",
                            "Analysten-Tendenz": "⚪"
                        })
            
            # Erst das DataFrame erstellen
            df_overview = pd.DataFrame(table_data)
            
            # Konfiguration für die Tabelle definieren
            tendenz_config = {
                "Analysten-Tendenz": st.column_config.TextColumn(
                    "Tendenz",
                    help="🟢 🟢 🟢 Strong Buy | 🟢 Buy | ⚪ Hold | 🔴 Sell | 🔴 🔴 🔴 Strong Sell"
                )
            }

            # Entscheiden, welche Daten angezeigt werden
            if mobile_mode:
                df_to_show = df_overview[["Ticker", "Aktueller Kurs", "Potenzial (Upside)", "Analysten-Tendenz"]]
            else:
                df_to_show = df_overview

            # Die Tabelle EINMAL rendern
            st.dataframe(
                df_to_show,
                width="stretch",
                hide_index=True,
                column_config=tendenz_config
            )
            
            st.caption("💡 Tipp: Klicke oben auf 'Detail-Analyse', um die Charts anzusehen.")

    # --- RECHTE SPALTE: GLOBAL MARKET RUNNER-UPS ---
    with col_gainers:
        st.subheader("🚀 Top 5 Markt Runner-Ups")
        
        with st.spinner("Scrape aktuelle Wall-Street-Gewinner..."):
            df_gainers = get_market_gainers()
            
            if df_gainers is not None:
                gestylte_runners = df_gainers.style.map(
                    style_percentage, subset=["Performance (Heute)"]
                )
                st.dataframe(gestylte_runners, width="stretch", hide_index=True)
            else:
                st.info("Gewinner-Daten konnten aktuell nicht geladen werden.")

# ==========================================
# MODUS 2: DETAIL-ANALYSE
# ==========================================
else:
    if selected_ticker:
        info = get_stock_info(selected_ticker)
        stock = yf.Ticker(selected_ticker)
        
        if info and ("currentPrice" in info or "regularMarketPrice" in info):
            company_name = info.get("longName", selected_ticker)
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            currency = info.get("currency", "USD")
            
            st.header(f"{company_name} ({selected_ticker})")
            
            # --- RECHNUNGSFAKTOR FÜR EURO HOLEN ---
            try:
                exchange_rate_ticker = yf.Ticker("EURUSD=X")
                usd_per_eur = exchange_rate_ticker.info.get("regularMarketPrice", 1.08)
            except:
                usd_per_eur = 1.08

            # --- METRIKEN ---
            target_low = info.get("targetLowPrice")
            target_mean = info.get("targetMeanPrice")
            target_high = info.get("targetHighPrice")
            analyst_count = info.get("numberOfAnalystOpinions")
            
            current_price_eur = current_price / usd_per_eur if current_price else None
            target_mean_eur = target_mean / usd_per_eur if target_mean else None
            
            left_col, middle_col, right_col = st.columns(3)
            
            with left_col:
                if current_price:
                    st.metric(
                        label="Aktueller Kurs", 
                        value=f"{current_price:.2f} {currency}",
                        delta=f"({current_price_eur:.2f} EUR)" if current_price_eur else None,
                        delta_color="off"
                    )
                else:
                    st.metric(label="Aktueller Kurs", value="N/A")
            
            with middle_col:
                if target_mean:
                    st.metric(
                        label="Kursziel (Schnitt)", 
                        value=f"{target_mean:.2f} {currency}",
                        delta=f"({target_mean_eur:.2f} EUR)" if target_mean_eur else None,
                        delta_color="off"
                    )
                else:
                    st.metric(label="Kursziel (Schnitt)", value="N/A")
                    
            with right_col:
                if current_price and target_mean:
                    upside = ((target_mean - current_price) / current_price) * 100
                    st.metric(label="Potenzial (Upside)", value=f"{upside:+.1f} %")
                else:
                    st.metric(label="Potenzial (Upside)", value="N/A")
            
            st.write("---")
            
            # --- CHARTS & DETAILS ---
            left_col, right_col = st.columns(2)
            
            with left_col:
                st.subheader("🎯 Kursziel-Spanne")
                if target_low and target_mean and target_high:
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=[target_low, target_high],
                        y=["Ziel", "Ziel"],
                        mode="lines",
                        line=dict(color="rgba(150, 150, 150, 0.6)", width=4),
                        name="Kursziel-Spanne",
                        hovertemplate="<b>Kursziel-Spanne:</b> %{x:.2f} USD<extra></extra>",
                        showlegend=True
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=[target_low],
                        y=["Ziel"],
                        mode="markers",
                        marker=dict(size=14, color="#FF4B4B"),
                        name=f"Min. Ziel ({target_low:.2f})",
                        hovertemplate="<b>Min. Ziel:</b> %{x:.2f} USD<extra></extra>",
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=[target_mean],
                        y=["Ziel"],
                        mode="markers",
                        marker=dict(size=20, color="#FFD700"),
                        name=f"Schnitt ({target_mean:.2f})",
                        hovertemplate="<b>Schnitt:</b> %{x:.2f} USD<extra></extra>",
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=[target_high],
                        y=["Ziel"],
                        mode="markers",
                        marker=dict(size=14, color="#00D26A"),
                        name=f"Max. Ziel ({target_high:.2f})",
                        hovertemplate="<b>Max. Ziel:</b> %{x:.2f} USD<extra></extra>",
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=[current_price],
                        y=["Ziel"],
                        mode="markers",
                        marker=dict(size=16, color="#1F77B4", symbol="diamond"),
                        name=f"Aktueller Kurs ({current_price:.2f})",
                        hovertemplate="<b>Aktueller Kurs:</b> %{x:.2f} USD<extra></extra>",
                    ))
                    
                    fig.update_layout(
                        height=240, 
                        hovermode="x unified",
                        margin=dict(l=20, r=20, t=10, b=10),
                        legend=dict(
                            orientation="h",
                            yanchor="bottom",
                            y=-0.6,
                            xanchor="center",
                            x=0.5
                        ),
                        showlegend=True
                    )
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("Keine detaillierten Kursziel-Spanne-Daten für dieses Wertpapier verfügbar.")
            
            with right_col:
                st.subheader("📈 Aktueller Analysten-Konsensus")
                # Einheitlicher Aufruf
                st.write(f"### Stimmung: {get_sentiment(selected_ticker)}")
                
                # Versuch, die Tabelle anzuzeigen
                try:
                    rec_df = stock.recommendations
                    if rec_df is not None and not rec_df.empty:
                        st.write("Letzte Analysten-Einstufungen:")
                        st.dataframe(rec_df.head(5), width="stretch")
                    else:
                        st.info("Keine aktuellen Rating-Daten verfügbar.")
                except Exception:
                    st.warning("Detaillierte Ratings konnten aktuell nicht geladen werden.")