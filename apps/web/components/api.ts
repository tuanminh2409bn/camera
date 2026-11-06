import type { Auth, ApiError } from "@devone/contracts";
export class RequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}
export async function request<T>(
  path: string,
  auth: Auth | null = null,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    cache: "no-store",
    credentials: "same-origin",
    headers: {
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(auth ? { "X-CSRF-Token": auth.csrfToken } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let message = "Dịch vụ chưa khả dụng. Vui lòng thử lại.";
    try {
      const data = (await response.json()) as ApiError;
      if (data.error?.message) message = data.error.message;
    } catch {}
    throw new RequestError(message, response.status);
  }
  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
}
export const messageOf = (error: unknown) =>
  error instanceof Error ? error.message : "Không thể thực hiện yêu cầu.";
