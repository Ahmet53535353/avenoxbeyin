import { homedir } from "node:os";
import { mkdirSync, writeFileSync, appendFileSync, unlinkSync } from "node:fs";

const HOME = homedir();
const VAULT = `${HOME}/Brain`;
const BEYIN = `${VAULT}/.beyin`;
const BRIDGE = `${BEYIN}/hooks/bridge.py`;
const STATE_DIR = `${BEYIN}/.state`;
const LOG = `${HOME}/.cache/opencode-brain-plugin.log`;
const IDLE_DEBOUNCE_MS = 120000;

function log(...args) {
  try {
    appendFileSync(LOG, `[${new Date().toISOString()}] ${args.map(String).join(" ")}\n`);
  } catch {}
}

log("PLUGIN_MODULE_LOADED");

function runBridge(event, payload, capture) {
  mkdirSync(STATE_DIR, { recursive: true });
  const payloadFile = `${STATE_DIR}/bridge-in-${event}-${Date.now()}.json`;
  writeFileSync(payloadFile, JSON.stringify(payload));
  const cmd = ["python3", BRIDGE, "--provider", "opencode", "--event", event];
  const proc = Bun.spawn(cmd, {
    stdin: Bun.file(payloadFile),
    stdout: capture ? "pipe" : "ignore",
    stderr: "ignore",
  });
  const cleanup = () => {
    try {
      unlinkSync(payloadFile);
    } catch {}
  };
  if (capture) {
    return (async () => {
      const out = await Bun.readableStreamToText(proc.stdout);
      await proc.exited;
      cleanup();
      return out;
    })();
  }
  proc.exited.then(cleanup, cleanup);
  return Promise.resolve("");
}

function buildTranscript(messages) {
  const lines = [];
  for (const m of messages || []) {
    const role = m?.info?.role || m?.role;
    if (role !== "user" && role !== "assistant") continue;
    let text = "";
    const parts = Array.isArray(m.parts) ? m.parts : [];
    if (parts.length) {
      text = parts
        .filter((p) => p && (p.type === "text" || p.type === "reasoning"))
        .map((p) => p.text || "")
        .join("\n");
    } else if (typeof m.content === "string") {
      text = m.content;
    } else if (m.content && typeof m.content === "object") {
      text = JSON.stringify(m.content);
    }
    if (!text.trim()) continue;
    lines.push(JSON.stringify({ message: { role, content: text } }));
  }
  return lines.join("\n");
}

function extractSessionID(event) {
  return (
    event?.properties?.sessionID ||
    event?.sessionID ||
    event?.info?.sessionID ||
    event?.properties?.sessionId ||
    event?.properties?.session?.id ||
    event?.sessionId
  );
}

function extractCwd(event, fallback) {
  return (
    event?.properties?.info?.directory ||
    event?.properties?.directory ||
    event?.properties?.cwd ||
    event?.info?.cwd ||
    fallback
  );
}

export default async function OpencodeBrain(input) {
  const { client, directory } = input || {};
  const DEFAULT_CWD = directory || process.cwd();
  const contextStore = new Map();
  const cwdStore = new Map();
  const injected = new Set();
  const lastIdleFlush = new Map();

  async function populateContext(sessionID, cwd) {
    if (contextStore.has(sessionID)) return;
    try {
      const ctx = await runBridge(
        "start",
        {
          session_id: sessionID,
          cwd: cwd || DEFAULT_CWD,
          beyin_provider: "opencode",
          model: "",
        },
        true,
      );
      if (ctx && ctx.trim()) {
        contextStore.set(sessionID, ctx);
        log("start-context", sessionID, ctx.length, "chars");
      } else {
        log("start-context-empty", sessionID);
      }
    } catch (e) {
      log("populate-error", sessionID, e?.message || String(e));
    }
  }

  const READ_TRANSCRIPT = `${BEYIN}/read_transcript.py`;

  async function readTranscript(sessionID) {
    try {
      const proc = Bun.spawn(
        ["python3", READ_TRANSCRIPT, "--session", sessionID],
        { stdout: "pipe", stderr: "ignore" },
      );
      const out = await Bun.readableStreamToText(proc.stdout);
      await proc.exited;
      const msgs = [];
      for (const line of out.split("\n")) {
        const t = line.trim();
        if (!t) continue;
        try {
          msgs.push(JSON.parse(t));
        } catch {}
      }
      return msgs;
    } catch (e) {
      log("read-transcript-error", sessionID, e?.message || String(e));
      return [];
    }
  }

  async function flushSession(sessionID, reason) {
    if (!sessionID) return;
    try {
      const messages = await readTranscript(sessionID);
      log("flush-attempt", reason, sessionID, "msgs", messages.length);
      const transcript = buildTranscript(messages);
      if (!transcript) {
        log("flush-skip-empty", reason, sessionID, "msgs", messages?.length || 0);
        return;
      }
      mkdirSync(STATE_DIR, { recursive: true });
      const tmp = `${STATE_DIR}/transcript-${sessionID}.jsonl`;
      writeFileSync(tmp, transcript);
      await runBridge(
        reason === "precompact" ? "precompact" : "end",
        {
          session_id: sessionID,
          cwd: cwdStore.get(sessionID) || DEFAULT_CWD,
          transcript_path: tmp,
          beyin_provider: "opencode",
          model: "",
        },
        false,
      );
      log("flush-done", reason, sessionID, "launched");
    } catch (e) {
      log("flush-error", reason, sessionID, e?.message || String(e));
    }
  }

  return {
    event: async ({ event }) => {
      const rawType = event?.type || "";
      const type = rawType.toLowerCase();
      const sessionID = extractSessionID(event);
      const cwd = extractCwd(event, DEFAULT_CWD);
      if (/^(session\.(created|updated|idle|closed|destroyed|abort|compacted)|command\.|experimental\.)/.test(type)) {
        log("EVENT", type, sessionID || "-");
      }
      if (sessionID) cwdStore.set(sessionID, cwd);
      if (!sessionID) return;
      try {
        if (type === "session.created" || type === "session.updated") {
          await populateContext(sessionID, cwd);
        } else if (
          type === "session.closed" ||
          type === "session.destroyed" ||
          type === "session.abort" ||
          type === "session.compacted"
        ) {
          await flushSession(sessionID, "end");
        } else if (type === "session.idle") {
          const last = lastIdleFlush.get(sessionID) || 0;
          if (Date.now() - last < IDLE_DEBOUNCE_MS) {
            log("idle-skip", sessionID);
            return;
          }
          lastIdleFlush.set(sessionID, Date.now());
          await flushSession(sessionID, "end");
        }
      } catch (e) {
        log("event-error", type, sessionID, e?.message || String(e));
      }
    },

    "experimental.session.compacting": async ({ sessionID }, output) => {
      await flushSession(sessionID, "precompact");
      const ctx = contextStore.get(sessionID);
      if (ctx && ctx.trim()) {
        output.context = output.context || [];
        output.context.push(ctx);
      }
    },

    "experimental.chat.system.transform": async ({ sessionID }, output) => {
      if (!sessionID || injected.has(sessionID)) return;
      const ctx = contextStore.get(sessionID);
      if (ctx && ctx.trim()) {
        output.system = output.system || [];
        output.system.push(ctx);
        injected.add(sessionID);
        log("inject-context", sessionID, ctx.length, "chars");
      }
    },

    "command.execute.before": async ({ command, sessionID }, output) => {
      const name = (command || "").replace(/^\//, "");
      log("command.execute.before", name, sessionID || "-");
      if (name !== "beyin-bitir") return;
      await flushSession(sessionID, "end");
      output.parts = [
        {
          type: "text",
          text: "🧠 Oturum hafızası güncellendi: özet daily/ günlüğüne yazıldı (Codex ile).",
        },
      ];
    },

    config: async (config) => {
      log("CONFIG_HOOK");
      config.command = config.command || {};
      config.command["beyin-bitir"] = {
        description:
          "Beyin oturumunu kapat: mevcut oturumu Codex ile özetleyip 📥 daily günlüğüne flush et.",
        template:
          "Beyin oturumunu bitir. opencode-brain eklentisi oturum özetini zaten çıkardı; kullanıcıya kısa bir Türkçe onay ver.",
      };
    },
  };
}
