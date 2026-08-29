"""Tools de portfolio y riesgo: volatilidad, VaR, correlación, Sharpe ratio.

A diferencia de `macro_data.py`/`equity_data.py`, acá el cómputo es propio
(numpy/pandas) sobre precios históricos de yfinance, no solo un passthrough
a una API externa. Mismas reglas que el resto: funciones planas, type hints,
docstrings Google-style completos, sin parámetros con valor default (UC
Functions no los admite) — `tickers`/`weights` van como strings separados
por coma en vez de listas, por la misma razón.
"""

from __future__ import annotations

_TRADING_DAYS_PER_YEAR = 252


def _parse_tickers_and_weights(tickers: str, weights: str) -> tuple[list[str], list[float]]:
    """Parsea tickers/weights separados por coma y normaliza los weights a que sumen 1."""
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    weight_list = [float(w.strip()) for w in weights.split(",") if w.strip()]
    if len(ticker_list) != len(weight_list):
        raise ValueError(
            f"tickers ({len(ticker_list)}) y weights ({len(weight_list)}) "
            "tienen que tener la misma cantidad de elementos."
        )
    total = sum(weight_list)
    if total <= 0:
        raise ValueError("La suma de los weights tiene que ser positiva.")
    normalized = [w / total for w in weight_list]
    return ticker_list, normalized


def _portfolio_returns(tickers: str, weights: str, period: str):
    """Devuelve la serie de retornos diarios ponderados del portfolio."""
    import yfinance as yf

    ticker_list, weight_list = _parse_tickers_and_weights(tickers, weights)
    data = yf.download(ticker_list, period=period, progress=False, auto_adjust=True)["Close"]
    data = data.dropna()  # el día en curso puede no tener cierre todavía
    if data.empty or len(data) < 2:
        raise ValueError(f"No hay suficiente historial de precios para {ticker_list} en '{period}'.")
    if hasattr(data, "columns"):
        data = data[ticker_list]  # asegura el mismo orden que weight_list
    else:
        data = data.to_frame(ticker_list[0])
    returns = data.pct_change(fill_method=None).dropna()
    return returns.dot(weight_list)


def calculate_portfolio_volatility(tickers: str, weights: str, period: str) -> str:
    """Calcula la volatilidad anualizada de un portfolio ponderado.

    Args:
        tickers: tickers separados por coma (ej. "AAPL,MSFT,GOOGL").
        weights: pesos separados por coma, mismo orden que tickers (ej.
            "0.5,0.3,0.2"); se normalizan para sumar 1 si no lo hacen ya.
        period: ventana de historial de yfinance (ej. "6mo", "1y").

    Returns:
        Texto con la volatilidad diaria y anualizada del portfolio.
    """
    import numpy as np

    returns = _portfolio_returns(tickers, weights, period)
    daily_vol = returns.std()
    annual_vol = daily_vol * np.sqrt(_TRADING_DAYS_PER_YEAR)
    return (
        f"Portfolio {tickers} (weights {weights}): volatilidad diaria "
        f"{daily_vol:.4%}, volatilidad anualizada {annual_vol:.2%}."
    )


def calculate_portfolio_var(tickers: str, weights: str, period: str, confidence: float) -> str:
    """Calcula el Value at Risk (VaR) histórico de un portfolio ponderado.

    Usa simulación histórica: el VaR es el percentil de la distribución de
    retornos diarios observados, no un modelo paramétrico.

    Args:
        tickers: tickers separados por coma (ej. "AAPL,MSFT,GOOGL").
        weights: pesos separados por coma, mismo orden que tickers.
        period: ventana de historial de yfinance (ej. "6mo", "1y").
        confidence: nivel de confianza del VaR, entre 0 y 1 (ej. 0.95 para VaR
            al 95%).

    Returns:
        Texto con el VaR diario como porcentaje de pérdida potencial del
        valor del portfolio.
    """
    import numpy as np

    if not 0 < confidence < 1:
        raise ValueError("confidence tiene que estar entre 0 y 1 (ej. 0.95).")
    returns = _portfolio_returns(tickers, weights, period)
    var_pct = -np.percentile(returns, (1 - confidence) * 100)
    return (
        f"Portfolio {tickers} (weights {weights}): VaR diario al "
        f"{confidence:.0%} de confianza = {var_pct:.2%} — con {confidence:.0%} "
        f"de confianza, la pérdida diaria no debería superar ese porcentaje "
        f"del valor del portfolio (histórico, sobre el período '{period}')."
    )


def calculate_correlation_matrix(tickers: str, period: str) -> str:
    """Calcula la matriz de correlación de retornos diarios entre varios tickers.

    Útil para evaluar diversificación: correlaciones cercanas a 1 indican
    que los activos se mueven juntos (poca diversificación); cercanas a 0
    o negativas indican mejor diversificación.

    Args:
        tickers: tickers separados por coma (ej. "AAPL,MSFT,GOOGL").
        period: ventana de historial de yfinance (ej. "6mo", "1y").

    Returns:
        Texto con la matriz de correlación pareada.
    """
    import yfinance as yf

    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    if len(ticker_list) < 2:
        raise ValueError("Se necesitan al menos 2 tickers para calcular correlación.")
    data = yf.download(ticker_list, period=period, progress=False, auto_adjust=True)["Close"]
    data = data.dropna()
    if data.empty:
        raise ValueError(f"No hay suficiente historial de precios para {ticker_list} en '{period}'.")
    corr = data[ticker_list].pct_change(fill_method=None).dropna().corr()
    lines = [f"{t}: " + ", ".join(f"{c}={corr.loc[t, c]:.2f}" for c in ticker_list) for t in ticker_list]
    return f"Matriz de correlación ({period}):\n" + "\n".join(lines)


def calculate_sharpe_ratio(
    tickers: str, weights: str, period: str, risk_free_rate: float
) -> str:
    """Calcula el Sharpe ratio anualizado de un portfolio ponderado.

    Args:
        tickers: tickers separados por coma (ej. "AAPL,MSFT,GOOGL").
        weights: pesos separados por coma, mismo orden que tickers.
        period: ventana de historial de yfinance (ej. "6mo", "1y").
        risk_free_rate: tasa libre de riesgo anualizada, como decimal (ej.
            0.04 para 4%). Se puede obtener del sub-supervisor de Macro
            (serie FEDFUNDS de FRED) si no se conoce.

    Returns:
        Texto con el retorno anualizado, la volatilidad anualizada y el
        Sharpe ratio resultante.
    """
    import numpy as np

    returns = _portfolio_returns(tickers, weights, period)
    annual_return = returns.mean() * _TRADING_DAYS_PER_YEAR
    annual_vol = returns.std() * np.sqrt(_TRADING_DAYS_PER_YEAR)
    if annual_vol == 0:
        raise ValueError("Volatilidad cero — no se puede calcular Sharpe ratio.")
    sharpe = (annual_return - risk_free_rate) / annual_vol
    return (
        f"Portfolio {tickers} (weights {weights}): retorno anualizado "
        f"{annual_return:.2%}, volatilidad anualizada {annual_vol:.2%}, "
        f"Sharpe ratio = {sharpe:.2f} (risk-free rate {risk_free_rate:.2%})."
    )


# Aritmética simple para cálculos intermedios (ej. combinar métricas de dos
# portfolios, convertir unidades) — mismo rol que el math_agent de
# add/multiply/divide en el notebook de referencia del bootcamp.


def add_numbers(a: float, b: float) -> str:
    """Suma dos números.

    Args:
        a: primer número.
        b: segundo número.

    Returns:
        Texto con el resultado de a + b.
    """
    return f"{a} + {b} = {a + b}"


def multiply_numbers(a: float, b: float) -> str:
    """Multiplica dos números.

    Args:
        a: primer número.
        b: segundo número.

    Returns:
        Texto con el resultado de a * b.
    """
    return f"{a} * {b} = {a * b}"


def divide_numbers(a: float, b: float) -> str:
    """Divide dos números.

    Args:
        a: numerador.
        b: denominador (no puede ser cero).

    Returns:
        Texto con el resultado de a / b.
    """
    if b == 0:
        raise ValueError("No se puede dividir por cero.")
    return f"{a} / {b} = {a / b}"
