from __future__ import annotations

from abc import ABC, abstractmethod


class LMRateLimitError(Exception):
    pass


class BaseLM(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        ...


class MockLM(BaseLM):
    def __init__(self, responses: list[str]) -> None:
        self._queue = list(responses)

    def complete(self, messages: list[dict]) -> str:
        if not self._queue:
            raise RuntimeError("MockLM response queue exhausted")
        return self._queue.pop(0)


class OpenAILM(BaseLM):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        self._model = model
        kwargs: dict = {"api_key": api_key}
        if base_url is not None:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def complete(self, messages: list[dict]) -> str:
        from openai import RateLimitError

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
            return resp.choices[0].message.content or ""
        except RateLimitError as e:
            raise LMRateLimitError(str(e)) from e
