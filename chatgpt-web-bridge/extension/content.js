// content.js — 在 chatgpt.com 页面里真正驱动生图的部分。
//
// ⚠️ 选择器是最脆弱的一环：ChatGPT 改版会失效。本文件把所有 DOM 依赖收敛到顶部
//    SELECTORS 常量 + 几个 find* 函数，改版时只改这里。带 ❗TODO 的需对着真实 DOM 校准。
//
// 流程：收到 background 的 GENERATE → 填 prompt（如有参考图先附上）→ 点发送
//      → 等最后一条 assistant 消息里出现生成图 → 把图 URL/字节回传 background。

const SELECTORS = {
  // ❗TODO(DOM校准): 输入框。当前 chatgpt.com 是 ProseMirror contenteditable
  composer: [
    'div#prompt-textarea[contenteditable="true"]',
    'div.ProseMirror[contenteditable="true"]',
    'textarea#prompt-textarea',
    'textarea[data-testid="prompt-textarea"]',
  ],
  // ❗TODO(DOM校准): 发送按钮
  sendButton: [
    'button#composer-submit-button',
    'button[data-testid="send-button"]',
    'button[aria-label*="Send"]',
    'button[aria-label*="发送"]',
    'button.composer-submit-btn',
  ],
  // ❗TODO(DOM校准): 附件/上传图片的 file input（图生图用）
  fileInput: [
    'input[type="file"]',
  ],
  // ❗TODO(DOM校准): assistant 回复气泡
  assistantTurn: [
    'div[data-message-author-role="assistant"]',
    'article[data-testid^="conversation-turn"]',
  ],
  // 生成出来的图：oaiusercontent / files 域，或 alt 含 generated
  generatedImg: [
    'img[src*="oaiusercontent.com"]',
    'img[src*="/backend-api/"]',
    'img[alt*="Generated"]',
  ],
};

const GEN_TIMEOUT_MS = 300000; // 等生图 300s

// 步骤上报：把每个关键节点推给 background → 桥 /diag，便于定位卡点
function report(jobId, step, extra) {
  try {
    chrome.runtime.sendMessage({ type: "PROGRESS", jobId, step, extra: extra ? String(extra).slice(0, 140) : "" });
  } catch (e) { /* ignore */ }
}

function $first(selList, root = document) {
  for (const sel of selList) {
    const el = root.querySelector(sel);
    if (el) return el;
  }
  return null;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function describeEl(el) {
  if (!el) return "null";
  const r = el.getBoundingClientRect();
  const visible = r.width > 0 && r.height > 0;
  return `<${el.tagName.toLowerCase()} id=${el.id || "-"} class="${(el.className || "").toString().slice(0, 60)} ` +
         `visible=${visible} ${r.width | 0}x${r.height | 0} contenteditable=${el.getAttribute("contenteditable")}>`;
}

// 向 background 请求浏览器级输入（CDP）。失败时返回 {ok:false}
function cdpInput(text, enter) {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage({ type: "CDP_INPUT", text, enter }, (res) => {
        resolve(res || { ok: false, error: "no response" });
      });
    } catch (e) {
      resolve({ ok: false, error: String(e) });
    }
  });
}

// ---- 填入 prompt ----
async function setComposerText(text) {
  const r = await cdpInput(text, false);
  if (r.ok) return `CDP✓ ${r.info || ""}`;

  // 回落：合成 DOM 事件（多数情况下骗不过 ProseMirror，仅作保底）
  const el = $first(SELECTORS.composer);
  if (!el) {
    const diag = SELECTORS.composer.map((s) => `${s}=${!!document.querySelector(s)}`).join(" ");
    throw new Error(`找不到输入框 | ${diag}`);
  }
  el.focus();
  const dt = new DataTransfer();
  dt.setData("text/plain", text);
  el.dispatchEvent(new ClipboardEvent("paste", { bubbles: true, cancelable: true, clipboardData: dt }));
  await sleep(300);
  if (!(el.textContent || "").includes(text.slice(0, 10))) {
    el.textContent = text;
    el.dispatchEvent(new InputEvent("input", { bubbles: true, data: text, inputType: "insertText" }));
  }
  await sleep(200);
  return `DOM回落(CDP失败:${r.error || "?"}) ${describeEl(el)}`;
}

// ---- 附参考图（图生图，实验性）----
async function attachRefImages(refImages) {
  if (!refImages || !refImages.length) return;
  const input = $first(SELECTORS.fileInput);
  if (!input) throw new Error("找不到文件上传 input（图生图选择器需校准）");
  const dt = new DataTransfer();
  for (const ref of refImages) {
    const bin = atob(ref.b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    dt.items.add(new File([arr], ref.name || "ref.png", { type: ref.mime || "image/png" }));
  }
  input.files = dt.files;
  input.dispatchEvent(new Event("change", { bubbles: true }));
  await sleep(3000); // 等上传完成（粗略）
}

// ---- 点发送 ----
// .click() 在 React 受控组件上经常不触发 SyntheticEvent，要用真实 MouseEvent。
// 再不行就用 Enter 键（ChatGPT 默认 Enter 发送）。
async function clickSend() {
  // 主路径：CDP 浏览器级回车（页面 JS 无法分辨真人与之）
  const r = await cdpInput("", true);
  if (r.ok) {
    return {
      info: `CDP回车✓ ${r.info || ""}`,
      // 唯一可信的"发送成功"证据：对话流里 user 轮次真的多了一条
      sent: !!r.sent,
      userTurns: r.userTurns || "",
    };
  }
  // 回落：合成鼠标事件 + Enter
  const btn = $first(SELECTORS.sendButton);
  if (btn && !btn.disabled) {
    btn.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true, cancelable: true, view: window }));
    btn.dispatchEvent(new MouseEvent("mousedown", { bubbles: true, cancelable: true, view: window }));
    btn.dispatchEvent(new MouseEvent("mouseup", { bubbles: true, cancelable: true, view: window }));
    btn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, view: window }));
    await sleep(600);
  }
  const el = $first(SELECTORS.composer);
  if (el) {
    el.focus();
    el.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Enter", code: "Enter", keyCode: 13, which: 13,
      bubbles: true, cancelable: true, view: window,
    }));
    await sleep(800);
  }
  return { info: `DOM回落(CDP:${r.error || "?"}) ${btn ? describeEl(btn) : "无按钮"}`, sent: false, userTurns: "" };
}

// ---- 等生成图出现 ----
// 只认 assistant 角色，避免把用户自己发的消息当成回复
function assistantTurns() {
  const strict = [...document.querySelectorAll('div[data-message-author-role="assistant"]')];
  if (strict.length) return strict;
  return [...document.querySelectorAll('article[data-testid^="conversation-turn"]')]
    .filter((n) => n.querySelector('[data-message-author-role="assistant"]') ||
                   /assistant/i.test(n.getAttribute("data-turn") || ""));
}

function pickImage(turn) {
  // 严格：必须有明确的"生成图"特征。页面静态装饰图（images.openai.com/static-rsc、
  // SVG 占位、hero 图等）一律不认。
  const strict = [
    'img[src*="oaiusercontent.com"]',
    'img[src*="files.oaiusercontent"]',
    'img[src*="/backend-api/files/"]',
    'img[alt*="Generated image" i]',
    'img[alt*="生成的图片"]',
    'img[alt*="生成的图"]',
  ];
  for (const sel of strict) {
    const el = turn.querySelector(sel);
    if (el && el.src && el.naturalWidth > 64) return el;
  }
  return null;
}

// 页面快照：超时/异常时把真实状态带回来，别再靠猜
function probePage() {
  const role = (r) => document.querySelectorAll(`[data-message-author-role="${r}"]`).length;
  const turns = [...document.querySelectorAll("[data-message-author-role]")];
  const tail = turns.slice(-3).map((t) =>
    `${t.getAttribute("data-message-author-role")}:${(t.innerText || "").replace(/\s+/g, " ").slice(0, 70)}`);
  const imgs = [...document.querySelectorAll("img")]
    .filter((i) => /oaiusercontent|files\.oai|backend-api\/files|blob:/i.test(i.src || ""))
    .map((i) => `${i.naturalWidth}x${i.naturalHeight} ${String(i.src).slice(0, 55)}`);
  return {
    url: location.href,
    user: role("user"),
    assistant: role("assistant"),
    tail,
    imgs: imgs.slice(0, 6),
    imgCount: imgs.length,
    streaming: !!document.querySelector('.result-streaming, [data-testid*="stop-button"], button[data-testid="stop-button"]'),
  };
}

const GEN_IMG_RE = /oaiusercontent|files\.oai|backend-api\/files|blob:/i;

function waitForImage() {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    // 用「发送前已存在的 src 集合」做基线：ChatGPT 用虚拟列表，消息计数会漂移，
    // 靠数量判断会永远等不到（实测出现过 baseline=13 而当前=11）。
    const seenSrcs = new Set([...document.querySelectorAll("img")].map((i) => i.src));
    const seenIds = new Set(
      [...document.querySelectorAll('[data-message-author-role="assistant"]')]
        .map((n) => n.getAttribute("data-message-id") || "")
    );
    let lastProbe = null;

    const tick = () => {
      const fresh = [...document.querySelectorAll("img")]
        .filter((i) => i.src && !seenSrcs.has(i.src) && GEN_IMG_RE.test(i.src) && i.naturalWidth > 64);
      if (fresh.length) {
        const img = fresh[fresh.length - 1];
        resolve({ src: img.src, img });
        return;
      }

      // 新出现的 assistant 消息（用 message-id 认，不用数量）
      const freshTurns = [...document.querySelectorAll('[data-message-author-role="assistant"]')]
        .filter((n) => {
          const id = n.getAttribute("data-message-id");
          return id ? !seenIds.has(id) : false;
        });
      if (freshTurns.length) {
        const last = freshTurns[freshTurns.length - 1];
        const lastText = (last.innerText || "").replace(/\s+/g, " ").trim().slice(0, 300);
        if (/rate limit|too many|limit reached|额度|上限|稍后再试|try again later|can'?t generate|unable to generate|cannot generate|无法生成|不能生成/i.test(lastText)) {
          reject(new Error("网页版拒绝/限流：" + lastText.slice(0, 200)));
          return;
        }
      }

      if (Date.now() - t0 > GEN_TIMEOUT_MS) {
        lastProbe = probePage();
        reject(new Error(
          `超时 ${GEN_TIMEOUT_MS / 1000}s。页面快照: ` +
          `url=${lastProbe.url} user=${lastProbe.user} assistant=${lastProbe.assistant} ` +
          `streaming=${lastProbe.streaming} 候选图=${lastProbe.imgCount} ` +
          `imgs=${JSON.stringify(lastProbe.imgs)} tail=${JSON.stringify(lastProbe.tail)}`
        ));
        return;
      }
      setTimeout(tick, 1200);
    };
    tick();
  });
}

// ---- 尽量在页面内把图转成 base64（拿不到就回传 URL 让 background 取）----
async function tryFetchBytes(url) {
  try {
    const r = await fetch(url);
    const blob = await r.blob();
    const b64 = await new Promise((res, rej) => {
      const fr = new FileReader();
      fr.onload = () => res(String(fr.result).split(",")[1]);
      fr.onerror = rej;
      fr.readAsDataURL(blob);
    });
    return { b64, mime: blob.type || "image/png" };
  } catch (e) {
    return null;
  }
}

// ---- 兜底：用 canvas 把已渲染的 <img> 直接编码成 base64 ----
// blob: / 跨域 URL 在 service worker 里 fetch 会 Failed to fetch，
// 但图已经渲染在页面上，canvas 画一遍即可拿到字节（不需要再联网）。
function imgToBase64(img, diag) {
  try {
    const w = img.naturalWidth || img.width;
    const h = img.naturalHeight || img.height;
    if (!w || !h) { if (diag) diag.err = "no-size"; return null; }
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    c.getContext("2d").drawImage(img, 0, 0, w, h);
    const dataUrl = c.toDataURL("image/png"); // 跨域未授权会抛 SecurityError
    return { b64: dataUrl.split(",")[1], mime: "image/png" };
  } catch (e) {
    if (diag) diag.err = String((e && e.name) || e);
    return null;
  }
}

async function runJob(job) {
  const jid = job && job.jobId;
  report(jid, "start", `prompt=${String(job && job.prompt).slice(0, 40)} url=${location.href}`);
  try {
    const composerEl = await setComposerText(job.prompt);
    report(jid, "composer-filled", composerEl);
    // 二次确认：composer 文本是否真的进去了
    const el = $first(SELECTORS.composer);
    const realText = el ? (el.textContent || el.value || "").slice(0, 50) : "(null)";
    report(jid, "composer-check", `实际内容="${realText}"`);
    if (job.refImages && job.refImages.length) {
      await attachRefImages(job.refImages);
      await setComposerText(job.prompt);
    }
    await sleep(400);
    const send = await clickSend();
    report(jid, "send-clicked", String(send.info).slice(0, 140));
    // 真正的证据：对话流里 user 轮次是否 +1。没 +1 说明消息压根没发出去
    if (!send.sent) {
      throw new Error(`发送失败：回车与按钮兜底后仍未确认提交，userTurns=${send.userTurns}`);
    } else {
      report(jid, "send-verify", `✓ 已发出 userTurns=${send.userTurns}`);
    }
    const hit = await waitForImage();
    report(jid, "image-found", hit.src);
    const diag = {};
    const bytes = (await tryFetchBytes(hit.src)) || imgToBase64(hit.img, diag);
    report(jid, "bytes", bytes ? `got ${Math.round((bytes.b64 || "").length / 1024)}KB` : `失败 ${diag.err || "fetch+canvas"}`);
    return {
      imageUrl: hit.src,
      imageBase64: bytes ? bytes.b64 : null,
      mime: bytes ? bytes.mime : "image/png",
      convErr: bytes ? undefined : (diag.err || "fetch+canvas 均失败"),
    };
  } catch (e) {
    report(jid, "error", String(e && e.message || e));
    throw e;
  }
}

// 防重复注入：background 每次派发都会 executeScript 注入一次本文件。
// 先摘掉上一次注册的监听器再挂新的 —— 既保证同一条任务只执行一次，
// 又保证改了本文件后（无需重载扩展/刷新页面）新逻辑立即生效。
if (window.__chatgptImageBridgeListener) {
  try { chrome.runtime.onMessage.removeListener(window.__chatgptImageBridgeListener); } catch (e) { /* ignore */ }
}

const _bridgeHandler = (msg, sender, sendResponse) => {
  if (msg && msg.type === "GENERATE") {
    sendResponse({ ack: true }); // 立刻 ack，避免长任务卡住消息通道
    runJob(msg.job)
      .then((res) => {
        chrome.runtime.sendMessage({ type: "GENERATE_RESULT", jobId: msg.job.jobId, ok: true, ...res });
      })
      .catch((err) => {
        report(msg.job.jobId, "error", String(err && err.message || err));
        chrome.runtime.sendMessage({ type: "GENERATE_RESULT", jobId: msg.job.jobId, ok: false, error: String(err && err.message || err) });
      });
    return true;
  }
};
window.__chatgptImageBridgeListener = _bridgeHandler;
chrome.runtime.onMessage.addListener(_bridgeHandler);

// 报到：注入成功就告诉 background（诊断用，也顺便确认消息通道通）
try {
  chrome.runtime.sendMessage({ type: "CONTENT_READY", url: location.href, ts: Date.now() });
} catch (e) { /* SW 睡了也不影响后续 */ }

// 顺手把 SW 最近的错误捞出来上报（chrome://extensions 红按钮里的内容，这里能拿到）
try {
  chrome.storage.session.get("lastSwError").then((r) => {
    if (r && r.lastSwError) {
      report("-", "sw-error", `${r.lastSwError.msg} @ ${new Date(r.lastSwError.ts).toLocaleTimeString("zh-CN")}`);
    }
  });
} catch (e) { /* ignore */ }
