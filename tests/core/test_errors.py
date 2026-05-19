import pytest
from h2t_ops.core.errors import (
    H2TError, UsageError, ConfigError, AuthError,
    ProviderError, NotFoundError, NetworkError, exit_code_for, EXIT_CODES,
)


@pytest.mark.parametrize("exc_cls,code", [
    (ProviderError, 1), (UsageError, 2), (ConfigError, 3),
    (AuthError, 4), (NotFoundError, 5), (NetworkError, 6),
])
def test_exit_code_for_each_type(exc_cls, code):
    assert exit_code_for(exc_cls("x")) == code


def test_exit_code_for_unknown_is_one():
    assert exit_code_for(ValueError("x")) == 1


def test_all_typed_errors_subclass_h2terror():
    for c in (UsageError, ConfigError, AuthError, ProviderError, NotFoundError, NetworkError):
        assert issubclass(c, H2TError)


def test_exit_codes_table_complete():
    assert EXIT_CODES == {"ok": 0, "provider": 1, "usage": 2,
                          "config": 3, "auth": 4, "not_found": 5, "network": 6}


def test_all_subclass_kinds_are_in_exit_codes():
    for cls in (UsageError, ConfigError, AuthError, ProviderError, NotFoundError, NetworkError):
        assert cls.kind in EXIT_CODES, f"{cls.__name__}.kind={cls.kind!r} missing from EXIT_CODES"


def test_hint_stored_and_defaults_none():
    e = UsageError("bad arg", hint="run h2t-ops --help")
    assert e.hint == "run h2t-ops --help"
    assert str(e) == "bad arg"
    assert UsageError("x").hint is None
