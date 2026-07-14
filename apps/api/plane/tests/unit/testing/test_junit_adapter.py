# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from django.core.exceptions import ValidationError

from plane.testing import parse_junit_xml


def test_junit_adapter_maps_results_and_durations():
    results = parse_junit_xml(
        """<testsuite><testcase classname="checkout" name="accepts card" time="0.125" />
        <testcase classname="checkout" name="declines fraud"><failure type="AssertionError">wrong status</failure></testcase>
        <testcase classname="checkout" name="optional"><skipped message="not configured" /></testcase></testsuite>"""
    )
    assert [item["status"] for item in results] == ["passed", "failed", "skipped"]
    assert results[0]["external_id"] == "checkout::accepts card"
    assert results[0]["duration_ms"] == 125
    assert results[1]["actual_result"]["text"] == "wrong status"


def test_junit_adapter_rejects_dtd_and_empty_suites():
    with pytest.raises(ValidationError):
        parse_junit_xml('<!DOCTYPE foo [<!ENTITY x "x">]><testsuite />')
    with pytest.raises(ValidationError):
        parse_junit_xml("<testsuite />")
