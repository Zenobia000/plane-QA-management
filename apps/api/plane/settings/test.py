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

# The API-key throttle counts against a shared cache keyed only by the token, so a
# suite that exercises the public API repeatedly throttles itself: running the
# contract/api directory alone produced 57 failures on HTTP 429, all of them
# infrastructure rather than behaviour. Rate limiting is a deployment concern and
# has its own coverage; here it only makes results depend on how many tests ran
# before this one.
API_KEY_RATE_LIMIT = "10000/minute"

# An in-memory, per-process cache keeps throttle counters from surviving between
# runs on a reused database.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "plane-test-cache",
    }
}
