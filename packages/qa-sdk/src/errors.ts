export type PlaneQAErrorKind =
  | "authentication"
  | "permission"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limit"
  | "network"
  | "server"
  | "unknown";

export class PlaneQAError extends Error {
  readonly kind: PlaneQAErrorKind;
  readonly status?: number;
  readonly details?: unknown;
  readonly retryable: boolean;

  constructor(options: {
    message: string;
    kind: PlaneQAErrorKind;
    status?: number;
    details?: unknown;
    retryable?: boolean;
    cause?: unknown;
  }) {
    super(options.message, { cause: options.cause });
    this.name = "PlaneQAError";
    this.kind = options.kind;
    this.status = options.status;
    this.details = options.details;
    this.retryable = options.retryable ?? false;
  }
}

export const errorKindForStatus = (status: number): PlaneQAErrorKind => {
  if (status === 401) return "authentication";
  if (status === 403) return "permission";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 429) return "rate_limit";
  if (status >= 400 && status < 500) return "validation";
  if (status >= 500) return "server";
  return "unknown";
};
