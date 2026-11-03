import { randomUUID } from "node:crypto";
import { z } from "zod";
import { username, password } from "@devone/contracts";
import { Secret } from "otpauth";
import { loadConfig, readPrivateJson } from "./config.js";
import { openDb, migrate, transaction, audit } from "./db.js";
import { hashPassword, encrypt } from "./crypto.js";

async function main() {
  const config = loadConfig(),
    db = openDb(config.databaseUrl);
  try {
    if (process.argv[2] === "migrate") {
      await migrate(db);
      process.stdout.write("Migration applied.\n");
      return;
    }
    if (process.argv[2] !== "bootstrap-admin" || !process.argv[3])
      throw new Error("Use migrate or bootstrap-admin PRIVATE_INPUT_JSON");
    const input = z
      .object({
        username,
        password,
        totpSecret: z.string().regex(/^[A-Z2-7]{32,128}$/),
      })
      .strict()
      .parse(readPrivateJson(process.argv[3]));
    Secret.fromBase32(input.totpSecret);
    const hash = await hashPassword(input.password);
    await transaction(db, async (tx) => {
      await tx.query("SELECT pg_advisory_xact_lock(6400003)");
      if ((await tx.query("SELECT 1 FROM users WHERE role='ADMIN'")).rowCount)
        throw new Error("Admin already exists; bootstrap refused");
      const id = randomUUID();
      await tx.query(
        `INSERT INTO users(id,username,password_hash,role,can_live,can_playback,can_download,totp_secret)
        VALUES($1,$2,$3,'ADMIN',true,true,true,$4)`,
        [
          id,
          input.username.toLowerCase(),
          hash,
          encrypt(input.totpSecret, config.encryptionKey),
        ],
      );
      await audit(tx, id, "ADMIN_BOOTSTRAP", id);
    });
    process.stdout.write(
      "Admin created; enroll the supplied secret in your authenticator and remove the private bootstrap input.\n",
    );
  } finally {
    await db.end();
  }
}
main().catch(() => {
  process.stderr.write(
    "Command failed. Check private input, database availability and migration state; values omitted.\n",
  );
  process.exitCode = 1;
});
