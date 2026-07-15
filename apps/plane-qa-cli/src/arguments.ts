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

export const commaListOption = (options: ParsedArguments["options"], name: string): string[] =>
  (optionString(options, name) ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
