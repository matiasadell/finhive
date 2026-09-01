"""Fixtures compartidas por `tests/unit/` y `tests/integration/`."""

from __future__ import annotations

import pytest

from portfolio_intel.data.store import load_portfolio_data


@pytest.fixture(scope="session")
def use_cases_df():
    """El dataset sintético completo, joined -- ver `data/sample_docs/README.md`.

    `scope="session"`: el join es el mismo para todos los tests, recomputarlo
    por test solo agrega tiempo sin agregar señal.
    """
    return load_portfolio_data().get_use_cases()


class FakeStructuredLLM:
    """Devuelve una respuesta canned a `.invoke(messages)`, sin llamar ningún modelo real."""

    def __init__(self, response: dict):
        self._response = response

    def invoke(self, messages):
        return self._response


class FakeChatModel:
    """Stub de `ChatDatabricks` -- alcanza para nodos que solo hacen
    `get_chat_model(...).with_structured_output(cls).invoke(messages)`
    (guardrails, el router del supervisor). No simula tool-calling real de un
    agente ReAct -- eso necesitaría un fake mucho más completo del protocolo
    de tool-calling de LangChain, y lo que de verdad hace falta verificar acá
    (ver `prompts/constraints_environment.md`) es el control de flujo del
    grafo (`Command(goto=...)`), no el comportamiento interno de
    `create_agent`.
    """

    def __init__(self, response: dict):
        self._response = response

    def with_structured_output(self, _cls):
        return FakeStructuredLLM(self._response)


def make_fake_get_chat_model(response: dict):
    """Factory de un reemplazo de `get_chat_model` que ignora sus argumentos."""

    def _fake_get_chat_model(*args, **kwargs):
        return FakeChatModel(response)

    return _fake_get_chat_model


@pytest.fixture
def fake_get_chat_model_factory():
    """Expone `make_fake_get_chat_model` como fixture -- así los tests de
    `tests/integration/` no tienen que importar `tests.conftest` como
    paquete (frágil sin `tests/__init__.py`)."""
    return make_fake_get_chat_model
