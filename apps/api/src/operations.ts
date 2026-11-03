import { lstat, readFile } from "node:fs/promises";
import { operationSnapshot, type OperationsStatus } from "@devone/contracts";

export async function readOperations(
  path = "/var/lib/devone-monitor/status.json",
  now = Date.now(),
): Promise<OperationsStatus> {
  try {
    const info = await lstat(path);
    if (
      !info.isFile() ||
      info.isSymbolicLink() ||
      (info.mode & 0o777) !== 0o600 ||
      info.uid !== process.getuid?.() ||
      info.size > 65536
    )
      return { available: false, reason: "unavailable" };
    const parsed = operationSnapshot.safeParse(
      JSON.parse(await readFile(path, "utf8")),
    );
    if (!parsed.success) return { available: false, reason: "unavailable" };
    const updated = Date.parse(parsed.data.updatedAt);
    if (now - updated > 180000 || updated - now > 60000)
      return { available: false, reason: "stale" };
    return { available: true, ...parsed.data };
  } catch {
    // No file paths, raw JSON, exception messages or configuration reach HTTP.
    return { available: false, reason: "unavailable" };
  }
}
