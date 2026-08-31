"""Tools de equity research: cotizaciones/fundamentals (yfinance) y filings/
datos financieros estructurados (SEC EDGAR).

Mismo patrón que `macro_data.py`: funciones planas, type hints, docstrings
Google-style completos (fuente de verdad para el registro en Unity Catalog),
sin parámetros con valor default (UC Functions no los admite).

`sec_headers`, `ticker_to_cik` y `SEC_SUBMISSIONS_URL` son públicos (sin `_`)
porque `finhive.rag.ingest` (ADR 0017) los reusa para bajar el texto completo
de un filing en vez de duplicar la resolución de CIK.
"""

from __future__ import annotations

import requests

from finhive.config.settings import (
    EQUITY_FILINGS_INDEX,
    VECTOR_SEARCH_ENDPOINT,
    get_databricks_host,
    get_databricks_token,
    get_sec_edgar_user_agent,
)

_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_SEC_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"

_cik_cache: dict[str, str] | None = None


def sec_headers() -> dict[str, str]:
    return {"User-Agent": get_sec_edgar_user_agent()}


def ticker_to_cik(ticker: str) -> str:
    """Resuelve un ticker a su CIK (Central Index Key) de 10 dígitos, cacheado."""
    global _cik_cache
    if _cik_cache is None:
        response = requests.get(_SEC_TICKERS_URL, headers=sec_headers(), timeout=15)
        response.raise_for_status()
        _cik_cache = {
            row["ticker"].upper(): str(row["cik_str"]).zfill(10)
            for row in response.json().values()
        }
    cik = _cik_cache.get(ticker.upper())
    if cik is None:
        raise ValueError(f"No se encontró CIK de SEC EDGAR para el ticker '{ticker}'.")
    return cik


def get_stock_quote(ticker: str) -> str:
    """Devuelve la cotización actual de una acción.

    Args:
        ticker: símbolo bursátil (ej. "AAPL", "MSFT", "GOOGL").

    Returns:
        Texto con precio actual, market cap y volumen.
    """
    import yfinance as yf

    info = yf.Ticker(ticker).info
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    return (
        f"{ticker}: precio actual {price} {info.get('currency', 'USD')}, "
        f"market cap {info.get('marketCap')}, volumen {info.get('volume')}."
    )


def get_stock_fundamentals(ticker: str) -> str:
    """Devuelve métricas fundamentales clave de una acción.

    Args:
        ticker: símbolo bursátil (ej. "AAPL", "MSFT", "GOOGL").

    Returns:
        Texto con P/E, EPS, dividend yield, sector e industria.
    """
    import yfinance as yf

    info = yf.Ticker(ticker).info
    return (
        f"{ticker} ({info.get('longName', ticker)}): "
        f"P/E trailing {info.get('trailingPE')}, EPS trailing {info.get('trailingEps')}, "
        f"dividend yield {info.get('dividendYield')}, "
        f"sector {info.get('sector')}, industria {info.get('industry')}."
    )


def get_stock_price_history(ticker: str, period: str) -> str:
    """Devuelve el historial de precios de cierre de una acción.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").
        period: ventana de tiempo de yfinance (valores válidos: "5d", "1mo",
            "3mo", "6mo", "1y", "ytd").

    Returns:
        Texto con una línea "{fecha}: {cierre}" por día de trading.
    """
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period=period).dropna(subset=["Close"])
    if hist.empty:
        return f"No hay historial de precios disponible para '{ticker}' en el período '{period}'."
    lines = [f"{idx.date()}: {row['Close']:.2f}" for idx, row in hist.iterrows()]
    return f"Historial de cierre de {ticker} ({period}):\n" + "\n".join(lines)


def calculate_sma(ticker: str, window: int) -> str:
    """Calcula la media móvil simple (SMA) de una acción y la compara con el precio actual.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").
        window: cantidad de días para la media móvil (ej. 20, 50, 200).

    Returns:
        Texto con el valor de la SMA, el precio actual, y si está por
        encima o por debajo (señal de tendencia alcista/bajista simple).
    """
    import yfinance as yf

    hist = yf.Ticker(ticker).history(period=f"{window * 2}d")
    closes = hist["Close"].dropna()  # el día en curso puede no tener cierre todavía
    if len(closes) < window:
        return f"No hay suficiente historial para calcular una SMA de {window} días para '{ticker}'."
    sma = closes.tail(window).mean()
    current = closes.iloc[-1]
    trend = "por encima de" if current > sma else "por debajo de"
    return (
        f"{ticker}: SMA({window}) = {sma:.2f}, precio actual = {current:.2f} "
        f"— el precio está {trend} la media móvil de {window} días."
    )


def search_sec_filings(ticker: str, form_type: str) -> str:
    """Busca los filings más recientes de una empresa en SEC EDGAR.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").
        form_type: tipo de filing a buscar (ej. "10-K" para el reporte anual,
            "10-Q" para el trimestral).

    Returns:
        Texto con hasta 5 filings recientes del tipo pedido: fecha y accession
        number (identificador único del filing en EDGAR).
    """
    cik = ticker_to_cik(ticker)
    response = requests.get(
        SEC_SUBMISSIONS_URL.format(cik=cik), headers=sec_headers(), timeout=15
    )
    response.raise_for_status()
    recent = response.json()["filings"]["recent"]
    matches = [
        (form, date, acc)
        for form, date, acc in zip(recent["form"], recent["filingDate"], recent["accessionNumber"])
        if form == form_type
    ][:5]
    if not matches:
        return f"No se encontraron filings de tipo '{form_type}' para '{ticker}'."
    lines = [f"{date}: {form} (accession {acc})" for form, date, acc in matches]
    return f"Filings recientes de {ticker} ({form_type}):\n" + "\n".join(lines)


def get_sec_company_facts(ticker: str, concept: str) -> str:
    """Devuelve el historial de un concepto financiero XBRL de SEC EDGAR.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").
        concept: tag XBRL us-gaap (ej. "NetIncomeLoss", "Assets",
            "EarningsPerShareDiluted"). Para ingresos, ojo: muchas empresas
            migraron del tag genérico "Revenues" a
            "RevenueFromContractWithCustomerExcludingAssessedTax" (ASC 606)
            desde ~2018 — si "Revenues" devuelve solo años viejos, probar con
            ese tag alternativo.

    Returns:
        Texto con los últimos 5 valores anuales (10-K) reportados para ese
        concepto, más recientes primero.
    """
    cik = ticker_to_cik(ticker)
    response = requests.get(
        _SEC_CONCEPT_URL.format(cik=cik, concept=concept), headers=sec_headers(), timeout=15
    )
    response.raise_for_status()
    units = response.json().get("units", {})
    values = units.get("USD") or next(iter(units.values()), [])
    annual = [v for v in values if v.get("form") == "10-K"]
    if not annual:
        return f"No se encontraron valores anuales de '{concept}' para '{ticker}'."
    seen_years: set[str] = set()
    lines = []
    for v in reversed(annual):
        if v["end"] in seen_years:
            continue
        seen_years.add(v["end"])
        lines.append(f"{v['end']}: {v['val']}")
        if len(lines) >= 5:
            break
    return f"{concept} de {ticker} (últimos años, USD):\n" + "\n".join(lines)


def search_filing_content(ticker: str, query: str) -> str:
    """Busca contenido narrativo (riesgos, estrategia, MD&A) dentro del 10-K de una empresa.

    A diferencia de `get_sec_company_facts` (datos numéricos XBRL) o
    `search_sec_filings` (metadata: fecha y accession number), esta función
    devuelve extractos reales del texto del filing más relevantes para la
    pregunta. Cobertura limitada por ahora: solo el último 10-K de AAPL y
    MSFT (prueba de concepto de RAG, ver ADR 0017), no cualquier ticker.

    Args:
        ticker: símbolo bursátil (por ahora solo "AAPL" o "MSFT").
        query: pregunta o tema a buscar dentro del filing (ej. "riesgos de
            cadena de suministro", "estrategia de inteligencia artificial").

    Returns:
        Texto con hasta 3 extractos del 10-K más relevantes para la búsqueda,
        con atribución al ticker de origen.
    """
    from databricks.ai_search.client import VectorSearchClient

    client = VectorSearchClient(
        workspace_url=get_databricks_host(),
        personal_access_token=get_databricks_token(),
        disable_notice=True,
    )
    index = client.get_index(endpoint_name=VECTOR_SEARCH_ENDPOINT, index_name=EQUITY_FILINGS_INDEX)
    results = index.similarity_search(
        columns=["ticker", "chunk_text"],
        query_text=query,
        filters={"ticker": ticker.upper()},
        num_results=3,
    )
    rows = results.get("result", {}).get("data_array", [])
    if not rows:
        return f"No se encontró contenido del 10-K de '{ticker}' relacionado con '{query}'."
    extracts = [f"Extracto del 10-K de {row[0]}:\n{row[1]}" for row in rows]
    return "\n\n---\n\n".join(extracts)
