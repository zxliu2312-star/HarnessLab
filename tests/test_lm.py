import pytest
from harness.lm import MockLM, LMRateLimitError, BaseLM, OpenAILM


def test_mock_lm_returns_in_order():
    lm = MockLM(["resp1", "resp2"])
    assert lm.complete([]) == "resp1"
    assert lm.complete([]) == "resp2"


def test_mock_lm_exhausted_raises():
    lm = MockLM(["only_one"])
    lm.complete([])
    with pytest.raises(RuntimeError, match="MockLM response queue exhausted"):
        lm.complete([])


def test_base_lm_is_abstract():
    with pytest.raises(TypeError):
        BaseLM()


def test_openailm_is_subclass():
    assert issubclass(OpenAILM, BaseLM)


def test_lm_rate_limit_error_is_exception():
    err = LMRateLimitError("too many requests")
    assert isinstance(err, Exception)
    assert "too many requests" in str(err)


def test_mock_lm_accepts_messages():
    lm = MockLM(["hello"])
    result = lm.complete([{"role": "user", "content": "hi"}])
    assert result == "hello"
