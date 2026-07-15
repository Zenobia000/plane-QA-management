#!/usr/bin/env node

import { runCLI } from "./run";

process.exitCode = await runCLI({ argv: process.argv.slice(2) });
