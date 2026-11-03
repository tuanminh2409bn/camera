CREATE TABLE users (
  id uuid PRIMARY KEY,
  username text NOT NULL UNIQUE CHECK (length(username) BETWEEN 3 AND 64),
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('ADMIN','VIEWER')),
  is_active boolean NOT NULL DEFAULT true,
  can_live boolean NOT NULL DEFAULT false,
  can_playback boolean NOT NULL DEFAULT false,
  can_download boolean NOT NULL DEFAULT false,
  max_live_sessions integer NOT NULL DEFAULT 2 CHECK (max_live_sessions BETWEEN 1 AND 10),
  totp_secret text,
  last_totp_step bigint NOT NULL DEFAULT -1,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (role <> 'ADMIN' OR totp_secret IS NOT NULL)
);
CREATE TABLE login_sessions (
  id uuid PRIMARY KEY,
  token_hash text NOT NULL UNIQUE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz
);
CREATE INDEX login_sessions_user_idx ON login_sessions(user_id);
CREATE TABLE media_sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  login_id uuid NOT NULL REFERENCES login_sessions(id) ON DELETE CASCADE,
  state text NOT NULL CHECK (state IN ('STARTING','ACTIVE','REVOKING')),
  native_location text,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL
);
CREATE INDEX media_sessions_login_idx ON media_sessions(login_id);
CREATE TABLE playback_sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  login_id uuid NOT NULL REFERENCES login_sessions(id) ON DELETE CASCADE,
  start_at timestamptz NOT NULL,
  duration_seconds integer NOT NULL CHECK (duration_seconds BETWEEN 1 AND 300),
  is_download boolean NOT NULL,
  expires_at timestamptz NOT NULL,
  streaming boolean NOT NULL DEFAULT false
);
CREATE INDEX playback_sessions_login_idx ON playback_sessions(login_id);
CREATE TABLE audit_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  actor_id uuid REFERENCES users(id) ON DELETE SET NULL,
  action text NOT NULL,
  target_id uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_created_idx ON audit_events(created_at);
CREATE TABLE auth_limits (
  key text PRIMARY KEY,
  attempts integer NOT NULL,
  resets_at timestamptz NOT NULL
);
CREATE TABLE recording_intent (
  id integer PRIMARY KEY CHECK (id = 1),
  desired boolean NOT NULL,
  revision bigint NOT NULL DEFAULT 0,
  actor_id uuid REFERENCES users(id) ON DELETE SET NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO recording_intent(id,desired) VALUES(1,true);
