# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Test Settings"""

from .common import *  # noqa

DEBUG = True

# Send it in a dummy outbox
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

INSTALLED_APPS.append(  # noqa
    "plane.tests"
)

# An in-memory, per-process cache keeps throttle counters from surviving between
# runs on a reused database. Production rates stay in force so the suite exercises
# the real limits; the _isolate_throttle_counters fixture in plane/tests/conftest.py
# resets each test's budget so they are spent within a test, never across the suite.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plane-test-cache",
    }
}
