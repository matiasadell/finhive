from __future__ import annotations

import pytest

from portfolio_intel.data.store import load_portfolio_data


@pytest.fixture(scope="session")
def use_cases_df():
    return load_portfolio_data().get_use_cases()


class FakeStructuredLLM:
    def __init__(self, response: dict):
        self._response = response

    def invoke(self, messages):
        return self._response


class FakeChatModel:
    def __init__(self, response: dict):
        self._response = response

    def with_structured_output(self, _cls):
        return FakeStructuredLLM(self._response)


def make_fake_get_chat_model(response: dict):
    def _fake_get_chat_model(*args, **kwargs):
        return FakeChatModel(response)

    return _fake_get_chat_model


@pytest.fixture
def fake_get_chat_model_factory():
    return make_fake_get_chat_model
