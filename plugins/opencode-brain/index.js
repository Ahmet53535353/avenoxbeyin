import { homedir } from "node:os";
import { mkdirSync, writeFileSync, appendFileSync, unlinkSync } from "node:fs";

function getVaultDir(inputDirectory: string | undefined): string {
  // Prefer CLAUDE_PROJECT_DIR (set by OpenCode when running in a project)
  // Fall back to input directory, then ~/Brain
  return process.env.CLAUDE_PROJECT_DIR || inputDirectory || `${homedir()}/Brain`;
}

function log(...args: unknown[]) {
  try {
    appendFileSync(
      `${homedir()}/.cache/opencode-brain-plugin.log`,
      `[${new Date().toISOString()}] ${args.map(String).join(" ")}\n`,
    );
  } catch {}
}

log("PLUGIN_MODULE_LOADED");

function runBridge(vaultDir: string, event: string, payload: Record<string, unknown>, capture: boolean) {
  const stateDir = `${vaultDir}/.claude/scripts/.state`;
  mkdirSync(stateDir, { recursive: true });
  const payloadFile = `${stateDir}/bridge-in-${event}-${Date.now()}.json`;
  writeFileSync(payloadFile, JSON.stringify(payload));
  const bridge = `${vaultDir}/.claude/scripts/bridge.py`;
  const cmd = ["python3", bridge, "--provider", "opencode", "--event", event];
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

function buildTranscript(messages: unknown[]) {
  const lines = [];
  for (const m of messages || []) {
    const role = (m as Record<string, unknown>)?.info?.role as string || (m as Record<string, unknown>)?.role as string;
    if (role !== "user" && role !== "assistant") continue;
    let text = "";
    const parts = Array.isArray((m as Record<string, unknown>).parts) ? (m as Record<string, unknown>).parts as unknown[] : [];
    if (parts.length) {
      text = parts
        .filter((p) => p && ((p as Record<string, unknown>).type === "text" || (p as Record<string, unknown>).type === "reasoning"))
        .map((p) => (p as Record<string, unknown>).text as string || "")
        .join("\n");
    } else if (typeof (m as Record<string, unknown>).content === "string") {
      text = (m as Record<string, unknown>).content as string;
    } else if ((m as Record<string, unknown>).content && typeof (m as Record<string, unknown>).content === "object") {
      text = JSON.stringify((m as Record<string, unknown>).content);
    }
    if (!text.trim()) continue;
    lines.push(JSON.stringify({ message: { role, content: text } }));
  }
  return lines.join("\n");
}

function extractSessionID(event: Record<string, unknown>): string | undefined {
  return (
    (event.properties as Record<string, unknown>)?.sessionID as string ||
    event.sessionID as string ||
    (event.info as Record<string, unknown>)?.sessionID as string ||
    (event.properties as Record<string, unknown>)?.sessionId as string ||
    (event.properties as Record<string, unknown>)?.session?.id as string ||
    event.sessionId as string
  );
}

function extractCwd(event: Record<string, unknown>, fallback: string): string {
  return (
    (event.properties as Record<string, unknown>)?.info?.directory as string ||
    (event.properties as Record<string, unknown>)?.directory as string ||
    (event.properties as Record<string, unknown>)?.cwd as string ||
    (event.info as Record<string, unknown>)?.cwd as string ||
    fallback
  );
}

export default async function OpencodeBrain(input: { client?: unknown; directory?: string } = {}) {
  const { directory } = input;
  const DEFAULT_CWD = directory || process.cwd();
  const VAULT_DIR = getVaultDir(directory);
  const READ_TRANSCRIPT = `${VAULT_DIR}/.claude/scripts/read_transcript.py`;

  const contextStore = new Map<string, string>();
  const cwdStore = new Map<string, string>();
  const injected = new Set<string>();
  const lastIdleFlush = new Map<string, number>();
  const IDLE_DEBOUNCE_MS = 120000;

  async function populateContext(sessionID: string, cwd: string) {
    if (contextStore.has(sessionID)) return;
    try {
      const ctx = await runBridge(
        VAULT_DIR,
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

  async function readTranscript(sessionID: string) {
    try {
      const proc = Bun.spawn(["python3", READ_TRANSCRIPT, "--session", sessionID], {
        stdout: "pipe",
        stderr: "ignore",
      });
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

  async function flushSession(sessionID: string, reason: string) {
    if (!sessionID) return;
    try {
      const messages = await readTranscript(sessionID);
      log("flush-attempt", reason, sessionID, "msgs", messages.length);
      const transcript = buildTranscript(messages);
      if (!transcript) {
        log("flush-skip-empty", reason, sessionID, "msgs", messages?.length || 0);
        return;
      }
      const stateDir = `${VAULT_DIR}/.claude/scripts/.state`;
      mkdirSync(stateDir, { recursive: true });
      const tmp = `${stateDir}/transcript-${sessionID}.jsonl`;
      writeFileSync(tmp, transcript);
      await runBridge(
        VAULT_DIR,
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
    event: async ({ event }: { event: Record<string, unknown> }) => {
      const rawType = (event?.type as string) || "";
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

    "experimental.session.compacting": async ({ sessionID }: { sessionID: string }, output: Record<string, unknown>) => {
      await flushSession(sessionID, "precompact");
      const ctx = contextStore.get(sessionID);
      if (ctx && ctx.trim()) {
        output.context = output.context || [];
        (output.context as unknown[]).push(ctx);
      }
    },

    "experimental.chat.system.transform": async ({ sessionID }: { sessionID: string }, output: Record<string, unknown>) => {
      if (!sessionID || injected.has(sessionID)) return;
      const ctx = contextStore.get(sessionID);
      if (ctx && ctx.trim()) {
        output.system = output.system || [];
        (output.system as unknown[]).push(ctx);
        injected.add(sessionID);
        log("inject-context", sessionID, ctx.length, "chars");
      }
    },

    "command.execute.before": async ({ command, sessionID }: { command: string; sessionID: string }, output: Record<string, unknown>) => {
      const name = (command || "").replace(/^\//, "");
      log("command.execute.before", name, sessionID || "-");
      if (name !== "beyin-bitir") return;
      await flushSession(sessionID, "end");
      output.parts = [
        {
          type: "text",
          text: "🧠 Oturum hafızası güncellendi: özet daily/ günlüğüne yazıldı.",
        },
      ];
    },

    config: async (config: Record<string, unknown>) => {
      log("CONFIG_HOOK");
      config.command = config.command || {};
      config.command["beyin-bitir"] = {
        description: "Beyin oturumunu kapat: mevcut oturumu özetleyip 📥 daily günlüğüne flush et.",
        template: "Beyin oturumunu bitir. opencode-brain eklentisi oturum özetini zaten çıkardı; kullanıcıya kısa bir Türkçe onay ver.",
      };
    },
  };
}