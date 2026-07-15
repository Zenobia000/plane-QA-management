import { PlaneQAClient } from "@plane/qa-sdk";

import { optionString, type ParsedArguments } from "./arguments";

export interface CLIConfig {
  url: string;
  apiKey: string;
  workspace: string;
  project?: string;
}

export const resolveConfig = (options: ParsedArguments["options"], environment: NodeJS.ProcessEnv): CLIConfig => {
  const url = optionString(options, "url", environment.PLANE_URL);
  const apiKey = optionString(options, "api_key", environment.PLANE_API_KEY);
  const workspace = optionString(options, "workspace", environment.PLANE_WORKSPACE);
  const project = optionString(options, "project", environment.PLANE_PROJECT);
  if (!url) throw new Error("Plane URL is required through --url or PLANE_URL.");
  if (!apiKey) throw new Error("Plane API key is required through --api-key or PLANE_API_KEY.");
  if (!workspace) throw new Error("Workspace is required through --workspace or PLANE_WORKSPACE.");
  return { url, apiKey, workspace, project };
};

export type ClientFactory = (config: CLIConfig) => PlaneQAClient;

export const defaultClientFactory: ClientFactory = (config) =>
  new PlaneQAClient({ baseUrl: config.url, apiKey: config.apiKey });
