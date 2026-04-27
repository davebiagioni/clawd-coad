// clawd web frontend: SSE client + markdown/KaTeX rendering.

const log = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

const KATEX_OPTS = {
  delimiters: [
    { left: "$$", right: "$$", display: true },
    { left: "$", right: "$", display: false },
    { left: "\\(", right: "\\)", display: false },
    { left: "\\[", right: "\\]", display: true },
  ],
  throwOnError: false,
};

// Disable raw HTML in markdown so untrusted model output can't inject tags;
// DOMPurify is a second line of defense around the rendered string.
marked.setOptions({ breaks: true });
marked.use({
  hooks: {
    preprocess(md) {
      return md;
    },
  },
});

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function scrollToBottom() {
  window.scrollTo({ top: document.body.scrollHeight });
}

function renderAssistant(node, text) {
  const dirty = marked.parse(text);
  const clean = window.DOMPurify
    ? DOMPurify.sanitize(dirty, { USE_PROFILES: { html: true, mathMl: true, svg: true } })
    : dirty;
  // eslint-disable-next-line no-unsanitized/property
  node.innerHTML = clean;
  if (window.renderMathInElement) {
    renderMathInElement(node, KATEX_OPTS);
  }
}

function addUser(text) {
  const node = el("div", "msg user");
  node.textContent = text;
  log.appendChild(node);
  scrollToBottom();
}

function addAssistant() {
  const node = el("div", "msg assistant");
  log.appendChild(node);
  return node;
}

function addToolCall(name, args) {
  const node = el("div", "tool-call");
  node.textContent = `${name}(${JSON.stringify(args)})`;
  log.appendChild(node);
  scrollToBottom();
}

function addToolOutput(text) {
  const trimmed = (text || "").replace(/\s+$/, "");
  const node = el("pre", "tool-output");
  if (!trimmed) {
    node.classList.add("empty");
    node.textContent = "(no output)";
  } else {
    node.textContent = trimmed;
    if (/^diff --git|^--- .*\n\+\+\+ /m.test(trimmed.slice(0, 300))) {
      node.classList.add("diff");
    }
  }
  log.appendChild(node);
  scrollToBottom();
}

function addSpinner(text) {
  const node = el("div", "spinner", text);
  log.appendChild(node);
  scrollToBottom();
  return node;
}

async function loadHistory() {
  const res = await fetch("/api/history");
  if (!res.ok) return;
  const items = await res.json();
  for (const item of items) {
    if (item.kind === "user") addUser(item.text);
    else if (item.kind === "assistant") {
      const node = addAssistant();
      renderAssistant(node, item.text);
    } else if (item.kind === "tool_call") addToolCall(item.name, item.args);
    else if (item.kind === "tool_output") addToolOutput(item.text);
  }
  scrollToBottom();
}

async function refreshInfo() {
  try {
    const res = await fetch("/api/info");
    if (!res.ok) return;
    const info = await res.json();
    document.getElementById("provider").textContent = info.provider;
    document.getElementById("model").textContent = info.model;
    document.getElementById("branch").textContent = info.branch;
    const cost = info.cost_usd ? `$${info.cost_usd.toFixed(4)}` : "$0";
    document.getElementById("cost").textContent = `${info.tokens} tok · ${cost}`;
  } catch {}
}

// SSE-over-POST: native EventSource doesn't support POST bodies, so we read the
// streaming response with fetch + a manual parser.
async function streamChat(text, onEvent) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok || !res.body) throw new Error(`chat failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Per the SSE spec, events are separated by \r\n\r\n, \n\n, or \r\r.
    // sse_starlette emits CRLF; normalize so we only have to scan for \n\n.
    buf = (buf + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");

    let idx;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let event = "message";
      const dataLines = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      if (dataLines.length === 0) continue;
      let data = {};
      try {
        data = JSON.parse(dataLines.join("\n"));
      } catch {}
      onEvent(event, data);
    }
  }
}

async function send(text) {
  addUser(text);
  let assistantNode = null;
  let buffer = "";
  let spinner = addSpinner("thinking");

  const finishSpinner = () => {
    if (spinner) {
      spinner.remove();
      spinner = null;
    }
  };

  try {
    await streamChat(text, (event, data) => {
      if (event === "token") {
        finishSpinner();
        if (!assistantNode) assistantNode = addAssistant();
        buffer += data.text || "";
        renderAssistant(assistantNode, buffer);
        scrollToBottom();
      } else if (event === "tool_start") {
        finishSpinner();
        assistantNode = null;
        buffer = "";
        addToolCall(data.name, data.args || {});
        spinner = addSpinner(`running ${data.name}`);
      } else if (event === "tool_end") {
        finishSpinner();
        addToolOutput(data.output || "");
        spinner = addSpinner("thinking");
      } else if (event === "done") {
        finishSpinner();
      }
    });
  } catch (err) {
    finishSpinner();
    const node = el("div", "msg");
    node.style.color = "var(--err)";
    node.textContent = `error: ${err.message}`;
    log.appendChild(node);
  } finally {
    finishSpinner();
    refreshInfo();
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendBtn.disabled = true;
  try {
    await send(text);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

(async () => {
  await refreshInfo();
  await loadHistory();
})();
