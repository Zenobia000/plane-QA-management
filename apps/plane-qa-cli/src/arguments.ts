export interface ParsedArguments {
  positionals: string[];
  options: Record<string, boolean | string>;
}

const normalizeKey = (key: string) => key.replaceAll("-", "_");

export const parseArguments = (argv: string[]): ParsedArguments => {
  const positionals: string[] = [];
  const options: Record<string, boolean | string> = {};
  for (let index = 0; index < argv.length; index += 1) {
    const current = argv[index];
    if (!current.startsWith("--")) {
      positionals.push(current);
      continue;
    }
    const option = current.slice(2);
    const equals = option.indexOf("=");
    if (equals >= 0) {
      options[normalizeKey(option.slice(0, equals))] = option.slice(equals + 1);
      continue;
    }
    const next = argv[index + 1];
    if (next !== undefined && !next.startsWith("--")) {
      options[normalizeKey(option)] = next;
      index += 1;
    } else {
      options[normalizeKey(option)] = true;
    }
  }
  return { positionals, options };
};

export const optionString = (
  options: ParsedArguments["options"],
  name: string,
  fallback?: string
): string | undefined => {
  const value = options[name];
  return typeof value === "string" ? value : fallback;
};

export const requiredOption = (options: ParsedArguments["options"], name: string): string => {
  const value = optionString(options, name);
  if (!value) throw new Error(`--${name.replaceAll("_", "-")} is required.`);
  return value;
};

export const jsonOption = <T>(options: ParsedArguments["options"], name: string, fallback: T): T => {
  const value = optionString(options, name);
  if (value === undefined) return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    throw new Error(`--${name.replaceAll("_", "-")} must contain valid JSON.`);
  }
};

export const numberOption = (options: ParsedArguments["options"], name: string): number | undefined => {
  const value = optionString(options, name);
  if (value === undefined) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new Error(`--${name.replaceAll("_", "-")} must be a number.`);
  return parsed;
};

/**
 * A flag, whether written bare (`--leaf-only`) or with a value (`--leaf-only=false`).
 * Returns undefined when absent so callers can leave the server default in place.
 */
export const booleanOption = (options: ParsedArguments["options"], name: string): boolean | undefined => {
  const value = options[name];
  if (value === undefined) return undefined;
  if (typeof value === "boolean") return value;
  const normalized = value.trim().toLowerCase();
  if (["true", "1", "yes"].includes(normalized)) return true;
  if (["false", "0", "no"].includes(normalized)) return false;
  throw new Error(`--${name.replaceAll("_", "-")} must be a boolean.`);
};

/**
 * One of a closed set of values, rejected here rather than by the server.
 *
 * The server does reject an unknown value, but its error names the field and not the
 * alternatives, and the likely mistake for a small vocabulary is a near miss -- `NFR` or
 * `non-functional` for `quality` -- where knowing the three legal spellings is the whole
 * fix. Returns undefined when absent so callers leave the stored value alone.
 */
export const enumOption = <T extends string>(
  options: ParsedArguments["options"],
  name: string,
  allowed: readonly T[]
): T | undefined => {
  const value = optionString(options, name);
  if (value === undefined) return undefined;
  if (!(allowed as readonly string[]).includes(value)) {
    throw new Error(`--${name.replaceAll("_", "-")} must be one of: ${allowed.join(", ")}.`);
  }
  return value as T;
};

/**
 * A comma-separated selection from a closed set, returned in the wire form the filter takes.
 *
 * Checked for the same reason as `enumOption`, and more urgently: a filter given a value the
 * server does not recognise matches nothing, so a misspelt kind comes back as an empty list
 * that reads like a true answer. One bad member fails the whole flag rather than being
 * dropped, because silently narrowing a union is the same lie in smaller print.
 */
export const enumListOption = <T extends string>(
  options: ParsedArguments["options"],
  name: string,
  allowed: readonly T[]
): string | undefined => {
  const value = optionString(options, name);
  if (value === undefined) return undefined;
  const requested = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const unknown = requested.filter((item) => !(allowed as readonly string[]).includes(item));
  if (!requested.length || unknown.length) {
    throw new Error(`--${name.replaceAll("_", "-")} must be a comma-separated selection from: ${allowed.join(", ")}.`);
  }
  return requested.join(",");
};

export const commaListOption = (options: ParsedArguments["options"], name: string): string[] =>
  (optionString(options, name) ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
