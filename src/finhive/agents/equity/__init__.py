"""Sub-supervisor de Equity Research & Fundamentals (fundamentals, técnico, filings SEC).

RAG con RAPTOR sobre el texto completo de los 10-K/10-Q (ADR 0001) queda como
trabajo futuro — este slice cubre cotizaciones/fundamentals (yfinance) y
metadata + datos XBRL estructurados de filings (SEC EDGAR), sin parsear el
texto completo de los documentos todavía.
"""

from finhive.agents.equity.supervisor import build_equity_supervisor

__all__ = ["build_equity_supervisor"]
