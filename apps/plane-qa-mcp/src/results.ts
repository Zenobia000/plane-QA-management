import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { PlaneQAError } from "@plane/qa-sdk";

const MAX_TEXT_LENGTH = 12_000;
const MAX_STRUCTURED_LENGTH = 100_000;

const safeMessage = (error: unknown): string => {
  if (error instanceof PlaneQAError) return `${error.kind}: ${error.message}`;
  return error instanceof Error ? error.message : "Unknown Plane QA tool failure.";
};

export const toolResult = (data: unknown, summary = "Plane QA operation completed."): CallToolResult => {
  const candidate = { data };
  const candidateText = JSON.stringify(candidate);
  const structuredContent =
    candidateText.length > MAX_STRUCTURED_LENGTH
      ? {
          truncated: true,
          byte_length: new TextEncoder().encode(candidateText).length,
          message: "Result exceeded the MCP response limit. Use pagination or narrower filters.",
        }
      : candidate;
  const serialized = JSON.stringify(structuredContent);
  const text =
    serialized.length > MAX_TEXT_LENGTH
      ? `${summary} Structured result omitted from text because it exceeds ${MAX_TEXT_LENGTH} characters.`
      : serialized;
  return {
    content: [{ type: "text", text }],
    structuredContent,
  };
};

export const toolError = (error: unknown): CallToolResult => ({
  content: [{ type: "text", text: safeMessage(error) }],
  isError: true,
});

export const safely =
  <TInput>(handler: (input: TInput) => Promise<CallToolResult>) =>
  async (input: TInput): Promise<CallToolResult> => {
    try {
      return await handler(input);
    } catch (error) {
      return toolError(error);
    }
  };
