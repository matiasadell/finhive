"""Ingesta de filings de SEC EDGAR para el índice de Vector Search (ADR 0017).

Reusa la resolución de CIK ya escrita en `finhive.tools.equity_data`
(`ticker_to_cik`, `SEC_SUBMISSIONS_URL`) en vez de duplicarla -- solo agrega
lo que faltaba ahí: el campo `primaryDocument` de la respuesta de
`submissions/CIK{cik}.json` (ya venía en esa respuesta, `search_sec_filings`
simplemente no lo usaba) para armar la URL real del documento del filing, no
solo su metadata.
"""

from __future__ import annotations

import re

import requests
from bs4 import BeautifulSoup

from finhive.tools.equity_data import SEC_SUBMISSIONS_URL, sec_headers, ticker_to_cik

_SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_no_zeros}/{accession_no_dashes}/{document}"


def fetch_filing_text(ticker: str, form_type: str) -> dict:
    """Descarga el texto plano del filing más reciente de un tipo dado.

    Args:
        ticker: símbolo bursátil (ej. "AAPL").
        form_type: tipo de filing (ej. "10-K").

    Returns:
        Dict con `ticker`, `form_type`, `accession_number`, `filing_date` y
        `text` (el documento primario del filing, sin HTML).

    Raises:
        ValueError: si no se encuentra ningún filing de ese tipo.
    """
    cik = ticker_to_cik(ticker)
    response = requests.get(
        SEC_SUBMISSIONS_URL.format(cik=cik), headers=sec_headers(), timeout=15
    )
    response.raise_for_status()
    recent = response.json()["filings"]["recent"]

    match = None
    for form, date, acc, doc in zip(
        recent["form"], recent["filingDate"], recent["accessionNumber"], recent["primaryDocument"]
    ):
        if form == form_type:
            match = (date, acc, doc)
            break
    if match is None:
        raise ValueError(f"No se encontró ningún filing '{form_type}' para '{ticker}'.")
    filing_date, accession_number, primary_document = match

    doc_url = _SEC_ARCHIVES_URL.format(
        cik_no_zeros=str(int(cik)),
        accession_no_dashes=accession_number.replace("-", ""),
        document=primary_document,
    )
    doc_response = requests.get(doc_url, headers=sec_headers(), timeout=30)
    doc_response.raise_for_status()

    soup = BeautifulSoup(doc_response.text, "html.parser")
    # El documento primario es inline XBRL (iXBRL): además del texto narrativo
    # visible, incrusta un bloque `<ix:header>` con las definiciones de
    # contexto/unit XBRL (fechas, member names, URIs de namespace -- miles de
    # caracteres de metadata, no del reporte) y `<ix:hidden>` con hechos
    # etiquetados que no se muestran nunca. Sin esto, `get_text()` mezcla esa
    # metadata con la primera parte del documento y arruina los primeros
    # chunks (confirmado en AAPL: ~14KB de basura antes del texto real).
    for tag in soup(["script", "style", "ix:header", "ix:hidden"]):
        tag.decompose()
    for tag in soup.find_all(style=lambda v: v and "display:none" in v.replace(" ", "")):
        tag.decompose()
    text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n")).strip()

    return {
        "ticker": ticker.upper(),
        "form_type": form_type,
        "accession_number": accession_number,
        "filing_date": filing_date,
        "text": text,
    }


def chunk_text(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Trocea texto en chunks de tamaño fijo con solapamiento.

    Sin parsing de secciones (ver ADR 0017): el HTML de un 10-K varía mucho
    de formato entre empresas, parsear "Item 1A" de forma estructural es
    frágil. La búsqueda semántica encuentra los chunks relevantes igual.

    Args:
        text: texto plano completo a trocear.
        chunk_size: cantidad de caracteres por chunk.
        overlap: caracteres de solapamiento entre chunks consecutivos.

    Returns:
        Lista de chunks de texto, sin chunks vacíos o solo de espacios.
    """
    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
    return chunks
