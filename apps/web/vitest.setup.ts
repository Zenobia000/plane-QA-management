/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { vi } from "vitest";

/**
 * `t()` returns the key it was given, for every spec.
 *
 * Left to itself, whether a render sees a key or English depends on whether the
 * async locale bundle resolved first -- a race that had two spec files in this
 * repository asserting opposite things about the same component. Pinning it here
 * makes the choice explicit and identical everywhere.
 *
 * Returning the key is also the only honest contract available: ICU interpolation
 * does not run under vitest at all, so copy resolved here would prove nothing
 * about the browser. What a static render can prove is that a component reaches
 * for the right key.
 */
vi.mock("@plane/i18n", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@plane/i18n")>()),
  useTranslation: () => ({
    t: (key: string) => key,
    currentLocale: "en",
    changeLanguage: vi.fn(),
    languages: [],
  }),
}));
