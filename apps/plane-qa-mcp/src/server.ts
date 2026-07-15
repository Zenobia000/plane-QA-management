#!/usr/bin/env node

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { PlaneQAClient } from "@plane/qa-sdk";

import { createPlaneQAServer } from "./create-server";

const baseUrl = process.env.PLANE_URL?.trim();
const apiKey = process.env.PLANE_API_KEY?.trim();
if (!baseUrl || !apiKey) {
  process.stderr.write("PLANE_URL and PLANE_API_KEY are required.\n");
  process.exitCode = 2;
} else {
  const server = createPlaneQAServer(new PlaneQAClient({ baseUrl, apiKey }));
  const shutdown = async () => {
    await server.close();
    process.exit(0);
  };
  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
  await server.connect(new StdioServerTransport());
}
