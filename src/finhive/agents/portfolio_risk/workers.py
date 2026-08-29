"""Workers ReAct del dominio Portfolio & Risk: allocation, riesgo, cálculo.

Mismo patrón que `finhive.agents.macro.workers`. A diferencia de macro/equity,
las tools de este dominio no solo consultan APIs externas: calculan
volatilidad/VaR/correlación/Sharpe con numpy/pandas sobre precios de
yfinance (`finhive.tools.portfolio_math`).
"""

from __future__ import annotations

from langchain.agents import create_agent
from langchain_core.tools import tool

from finhive.config.settings import get_chat_model
from finhive.tools.portfolio_math import (
    add_numbers,
    calculate_correlation_matrix,
    calculate_portfolio_var,
    calculate_portfolio_volatility,
    calculate_sharpe_ratio,
    divide_numbers,
    multiply_numbers,
)
from finhive.tools.wrappers import safe_tool


def _portfolio_tools() -> list:
    return [
        tool(safe_tool(calculate_portfolio_volatility)),
        tool(safe_tool(calculate_portfolio_var)),
        tool(safe_tool(calculate_correlation_matrix)),
        tool(safe_tool(calculate_sharpe_ratio)),
        tool(safe_tool(add_numbers)),
        tool(safe_tool(multiply_numbers)),
        tool(safe_tool(divide_numbers)),
    ]


def build_portfolio_risk_workers() -> dict:
    """Construye los 3 workers ReAct del dominio Portfolio & Risk.

    Returns:
        dict con los agentes compilados, con clave = nombre del worker.
    """
    tools = _portfolio_tools()
    llm = get_chat_model("worker")

    allocation_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista especializado en composición y diversificación "
            "de portfolios. Usá calculate_correlation_matrix para evaluar qué "
            "tan diversificado está un conjunto de activos (correlaciones "
            "cercanas a 1 = poca diversificación). Tickers y weights van "
            "separados por coma, en el mismo orden (ej. tickers='AAPL,MSFT', "
            "weights='0.5,0.5'). Respondé solo con lo que calculaste — no "
            "inventes cifras ni recomiendes qué comprar o vender."
        ),
        name="allocation_worker",
    )

    risk_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista de riesgo especializado en volatilidad y Value "
            "at Risk (VaR) de portfolios. Usá calculate_portfolio_volatility "
            "y calculate_portfolio_var. Tickers y weights van separados por "
            "coma, en el mismo orden. Respondé solo con lo que calculaste — "
            "no inventes cifras ni recomiendes qué comprar o vender."
        ),
        name="risk_worker",
    )

    math_worker = create_agent(
        model=llm,
        tools=tools,
        system_prompt=(
            "Sos un analista cuantitativo especializado en retorno "
            "ajustado por riesgo. Usá calculate_sharpe_ratio para el Sharpe "
            "ratio de un portfolio (necesita una tasa libre de riesgo — si no "
            "te la dan, usá 0.04 como aproximación razonable de la tasa de "
            "fondos federales). Usá add_numbers/multiply_numbers/"
            "divide_numbers para cualquier cálculo intermedio que necesites. "
            "Respondé solo con lo que calculaste — no inventes cifras."
        ),
        name="math_worker",
    )

    return {
        "allocation_worker": allocation_worker,
        "risk_worker": risk_worker,
        "math_worker": math_worker,
    }
