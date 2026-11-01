"""JSON canonico RFC 8785 para `feature_vector_hash`."""

import hashlib

import pytest

from vectra_contracts.canonical import canonicalize, sha256_hex


def test_keys_sorted_by_utf16_and_no_spaces():
    assert canonicalize({"b": 1, "a": [True, None, "x"]}) == b'{"a":[true,null,"x"],"b":1}'
    # U+20AC sorts before U+1F600 by UTF-16 code units, unlike by code point in some cases.
    assert canonicalize({"\U0001f600": 1, "דּ": 2}).decode().index("\U0001f600") < canonicalize({"\U0001f600": 1, "דּ": 2}).decode().index("דּ")


def test_string_escapes_rfc8785():
    assert canonicalize("€$\u000f\nA'B\"\\") == '"€$\\u000f\\nA\'B\\"\\\\"'.encode()


def test_floats_and_big_ints_rejected():
    with pytest.raises(TypeError):
        canonicalize(1.5)
    with pytest.raises(ValueError):
        canonicalize(2**53)
    with pytest.raises(TypeError):
        canonicalize(object())


def test_sha256_matches_literal():
    assert sha256_hex({"a": 1}) == hashlib.sha256(b'{"a":1}').hexdigest()
