import { createInterface } from "node:readline/promises";

import { PlaneQAError } from "@plane/qa-sdk";

import { parseArguments } from "./arguments";
import { executeCommand } from "./commands";
import { defaultClientFactory, resolveConfig, type ClientFactory } from "./config";
import { HELP_TEXT } from "./help";

export interface CLIIO {
  stdout: (value: string) => void;
  stderr: (value: string) => void;
}

const destructiveCommands = new Set([
  "issue archive",
  "folder delete",
  "case archive",
  "case unlink-issue",
  "run close",
]);

const ttyConfirmation = async (operation: string): Promise<boolean> => {
  if (!process.stdin.isTTY || !process.stderr.isTTY) return false;
  const prompt = createInterface({ input: process.stdin, output: process.stderr });
  try {
    return (await prompt.question(`Confirm ${operation}? Type yes: `)).trim().toLowerCase() === "yes";
  } finally {
    prompt.close();
  }
};

const exitCodeForError = (error: unknown): number => {
  if (!(error instanceof PlaneQAError)) {
    return error instanceof Error && error.message.includes("requires explicit --yes") ? 7 : 2;
  }
  if (error.kind === "authentication") return 3;
  if (error.kind === "permission") return 4;
  if (error.kind === "not_found") return 5;
  if (error.kind === "conflict") return 6;
  if (error.kind === "network" || error.kind === "rate_limit" || error.kind === "server") return 8;
  return 1;
};

export const runCLI = async (options: {
  argv: string[];
  environment?: NodeJS.ProcessEnv;
  io?: CLIIO;
  createClient?: ClientFactory;
  confirm?: (operation: string) => Promise<boolean>;
}): Promise<number> => {
  const io = options.io ?? {
    stdout: (value) => process.stdout.write(value),
    stderr: (value) => process.stderr.write(value),
  };
  const args = parseArguments(options.argv);
  if (args.options.help === true || args.positionals.length === 0) {
    io.stdout(HELP_TEXT);
    return 0;
  }
  if (args.options.version === true) {
    io.stdout("0.1.0\n");
    return 0;
  }
  try {
    const operation = args.positionals.slice(0, 2).join(" ");
    if (
      destructiveCommands.has(operation) &&
      args.options.yes !== true &&
      args.options.dry_run !== true &&
      (await (options.confirm ?? ttyConfirmation)(operation))
    ) {
      args.options.yes = true;
    }
    const config = resolveConfig(args.options, options.environment ?? process.env);
    const client = (options.createClient ?? defaultClientFactory)(config);
    const result = await executeCommand(client, config, args);
    io.stdout(`${JSON.stringify(result ?? { ok: true }, null, 2)}\n`);
    return 0;
  } catch (error) {
    const code = exitCodeForError(error);
    const message = error instanceof Error ? error.message : "Unknown failure.";
    io.stderr(`${JSON.stringify({ error: { code, message } })}\n`);
    return code;
  }
};
