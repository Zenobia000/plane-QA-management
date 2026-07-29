# @plane/i18n

Locale bundles live in `src/locales/<locale>/<namespace>.json`, loaded per
namespace at runtime with English as the fallback language.

## Which locales are translated

This project maintains real translations for **`en` and `zh-TW`** only.

The other seventeen locales carry the English string. That is what a user would
see anyway once i18next fell back, and writing it down as a copy keeps every
locale on the loading path that is actually exercised — no locale here has ever
shipped a missing namespace file, so the missing-file fallback is untested
ground. An English value in `de/testing.json` is therefore a deliberate state,
not an unfinished translation.

Values that stay in English inside a translated locale are also deliberate where
the term is notation rather than prose: `SLO`, the Gherkin keywords
`Given` / `When` / `Then`, and `build`. Any coverage metric that compares values
against English will report these as gaps. They are not.

## Adding a UI string

`sync:check` fails when a locale lacks a key English has, so a new string needs
to reach every locale file before CI passes. Add it to `en` and `zh-TW` by hand,
then propagate:

```bash
pnpm --filter @plane/i18n fill        # copy English into locales that lack the key
pnpm --filter @plane/i18n check:fill  # exit 1 if any locale is still missing one
```

`fill` never overwrites an existing value and never reorders keys, so a
translated locale only gains the lines it was missing.

## Checks

| Command          | What it enforces                                                  |
| ---------------- | ----------------------------------------------------------------- |
| `check:sync`     | every locale has every English key; no cross-namespace collisions |
| `check:fill`     | the same gap, reported as the fix that closes it                  |
| `generate:types` | key types used by `useTranslation`                                |
