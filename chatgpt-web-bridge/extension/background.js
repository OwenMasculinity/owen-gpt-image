// background.js — service worker：本地桥 <-> chatgpt.com 标签页 的调度中枢
//
// 流程：长轮询 server 的 /poll 拿任务 → 找/建 chatgpt.com 标签 → 把任务交给 content.js
//       → content.js 生完图通过 runtime 消息回传 → 这里取图片字节 → POST /result。
//
// MV3 service worker 随时可能被杀，所以：
//   1. 用 chrome.alarms 每 20s 唤醒一次，重启轮询循环；
//   2. 当前任务存在 storage.session，SW 重启后不会重复派发；
//   3. content.js 用 runtime.sendMessage 回传结果，这个动作本身会唤醒被杀的 SW。

// 全局错误捕获：写到 storage，桥 /diag 能看到（避免只在 chrome://extensions 红按钮里显示）
self.addEventListener("error", (e) => {
  try {
    chrome.storage.session.set({ lastSwError: { msg: e.message, file: e.filename, line: e.lineno, ts: Date.now() } });
  } catch (_) { /* ignore */ }
});
self.addEventListener("unhandledrejection", (e) => {
  try {
    const r = e && e.reason;
    chrome.storage.session.set({ lastSwError: { msg: String((r && r.message) || r), ts: Date.now() } });
  } catch (_) { /* ignore */ }
});

const DEFAULT_BRIDGE = "http://127.0.0.1:8765";

async function bridgeBase() {
  const { bridgeUrl } = await chrome.storage.local.get("bridgeUrl");
  return (bridgeUrl || DEFAULT_BRIDGE).replace(/\/+$/, "");
}

let polling = false;

async function pollLoop() {
  if (polling) return;
  polling = true;
  try {
    // 有正在处理的任务就先不抢新活
    const { activeJob } = await chrome.storage.session.get("activeJob");
    if (activeJob) {
      polling = false;
      return;
    }
    const base = await bridgeBase();
    let resp;
    try {
      resp = await fetch(base + "/poll", { method: "GET" });
    } catch (e) {
      // 桥没开，安静退出，等下次 alarm 再试
      polling = false;
      return;
    }
    if (resp.status === 204) {
      polling = false;
      // 立刻再轮询，保持 SW 温热
      setTimeout(() => pollLoop(), 50);
      return;
    }
    if (!resp.ok) {
      polling = false;
      return;
    }
    const job = await resp.json();
    // 桥下发的「自我重载」指令：让改动过的 background.js 热更新，无需人工点 chrome://extensions
    if (job && job.reload) {
      polling = false;
      chrome.runtime.reload();
      return;
    }
    await chrome.storage.session.set({ activeJob: job });
    polling = false;
    dispatchJob(job).catch((e) => reportError(job.jobId, String(e)));
  } catch (e) {
    polling = false;
  }
}

// ============ CDP：浏览器级真实输入 ============
// 合成 DOM 事件（ClipboardEvent / execCommand / MouseEvent）都骗不过 ProseMirror 的内部
// state —— 表现就是"DOM 里有字、发送按钮却隐藏/点了没反应"。
// CDP 的 Input.* 走浏览器输入管线，页面 JS 完全无法区分真人与之，后台标签页同样生效。
const _cdpAttached = new Set();

function cdp(tabId, method, params) {
  return new Promise((resolve, reject) => {
    chrome.debugger.sendCommand({ tabId }, method, params, (r) => {
      const err = chrome.runtime.lastError;
      if (err) reject(new Error(`${method}: ${err.message}`));
      else resolve(r);
    });
  });
}

async function cdpAttach(tabId) {
  if (_cdpAttached.has(tabId)) return;
  await new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, "1.3", () => {
      const err = chrome.runtime.lastError;
      // 已被自己 attach 过也返回错误，这里当成功处理
      err && !/already|Another/i.test(err.message) ? reject(new Error(err.message)) : resolve();
    });
  });
  _cdpAttached.add(tabId);
}

async function cdpDetach(tabId) {
  if (!_cdpAttached.has(tabId) || tabId == null) return;
  try {
    await new Promise((resolve) => chrome.debugger.detach({ tabId }, resolve));
  } catch (e) { /* ignore */ }
  _cdpAttached.delete(tabId);
}

chrome.debugger.onDetach.addListener((src) => {
  if (src && src.tabId != null) _cdpAttached.delete(src.tabId);
});

const FOCUS_COMPOSER_JS = `(() => {
  const el = document.querySelector('#prompt-textarea[contenteditable="true"]')
          || document.querySelector('div.ProseMirror[contenteditable="true"]')
          || document.querySelector('textarea#prompt-textarea');
  if (!el) return 'no-composer';
  el.scrollIntoView({block:'center'});
  el.focus();
  return 'ok ' + document.activeElement.id;
})()`;

const READ_COMPOSER_JS = `(() => {
  const el = document.querySelector('#prompt-textarea') || document.querySelector('div.ProseMirror');
  return el ? (el.textContent || el.value || '').trim() : 'null';
})()`;

const COUNT_USER_TURNS_JS = `document.querySelectorAll('[data-message-author-role="user"]').length`;

const SEND_BUTTON_POINT_JS = `(() => {
  const selectors = ['button#composer-submit-button', 'button[data-testid="send-button"]',
    'button[aria-label="发送"]', 'button[aria-label="Send"]', 'button.composer-submit-btn'];
  for (const selector of selectors) {
    const button = document.querySelector(selector);
    if (!button || button.disabled) continue;
    const rect = button.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      return {x: rect.x + rect.width / 2, y: rect.y + rect.height / 2};
    }
  }
  return null;
})()`;

function cdpEvaluate(tabId, expression) {
  return cdp(tabId, "Runtime.evaluate", { expression, returnByValue: true, awaitPromise: false })
    .then((r) => (r && r.result ? r.result.value : null));
}

async function doCdpInput(tabId, msg) {
  await cdpAttach(tabId);
  const out = { ok: true, steps: [] };

  // 1) 聚焦输入框
  const focus = await cdpEvaluate(tabId, FOCUS_COMPOSER_JS);
  out.steps.push(`focus=${focus}`);
  if (focus === "no-composer") return { ok: false, error: "CDP: 找不到输入框" };

  // 2) 插入文本（整段一次 insertText，等价于粘贴，ProseMirror 原生接管）
  if (msg.text) {
    await cdp(tabId, "Input.insertText", { text: msg.text });
    await new Promise((r) => setTimeout(r, 400));
    const got = await cdpEvaluate(tabId, READ_COMPOSER_JS);
    out.steps.push(`len=${String(got || "").length}`);
    out.text = String(got || "");
    if (!got || !String(got).includes(String(msg.text).slice(0, 8))) {
      return { ok: false, error: `CDP 插入后输入框仍为空/不匹配（读到 ${String(got).slice(0, 40)}）` };
    }
  }

  // 3) 回车发送（浏览器级按键，React 的 onKeyDown 正常收到）
  if (msg.enter) {
    const before = await cdpEvaluate(tabId, COUNT_USER_TURNS_JS);
    const beforeText = await cdpEvaluate(tabId, READ_COMPOSER_JS);
    const key = { key: "Enter", code: "Enter", windowsVirtualKeyCode: 13, nativeVirtualKeyCode: 13 };
    await cdp(tabId, "Input.dispatchKeyEvent", { type: "rawKeyDown", ...key });
    await cdp(tabId, "Input.dispatchKeyEvent", { type: "char", text: "\r", ...key });
    await cdp(tabId, "Input.dispatchKeyEvent", { type: "keyUp", ...key });
    await new Promise((r) => setTimeout(r, 1200));
    let after = await cdpEvaluate(tabId, COUNT_USER_TURNS_JS);
    let remaining = await cdpEvaluate(tabId, READ_COMPOSER_JS);
    // Some composer versions ignore Enter (including IME/Grammarly setups).
    // Retry only while the original draft is still present and no new user turn
    // has appeared; never click a second time after an accepted submission.
    if (Number(after) <= Number(before) && remaining && remaining === beforeText) {
      const point = await cdpEvaluate(tabId, SEND_BUTTON_POINT_JS);
      if (point) {
        await cdp(tabId, "Input.dispatchMouseEvent", {type: "mousePressed", ...point, button: "left", clickCount: 1});
        await cdp(tabId, "Input.dispatchMouseEvent", {type: "mouseReleased", ...point, button: "left", clickCount: 1});
        await new Promise((r) => setTimeout(r, 1500));
        after = await cdpEvaluate(tabId, COUNT_USER_TURNS_JS);
        remaining = await cdpEvaluate(tabId, READ_COMPOSER_JS);
        out.steps.push("发送按钮点击兜底");
      }
    }
    out.steps.push(`userTurns ${before}->${after} composer残留=${String(remaining || "").length}`);
    out.sent = Number(after) > Number(before) || (Boolean(beforeText) && remaining === "");
    out.userTurns = `${before}->${after}`;
  }
  out.info = out.steps.join(" | ");
  return out;
}

async function reloadTabFresh(tabId) {
  try {
    await chrome.tabs.reload(tabId, {});
  } catch (e) { return; }
  await new Promise((resolve) => {
    const listener = (id, info) => {
      if (id === tabId && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 3000); // 等 React 把消息列表渲染完
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(resolve, 25000); // 兜底
  });
}

async function describeTabs() {
  try {
    const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*", "https://chat.openai.com/*"] });
    return tabs.map((t) => `[${t.id}]${t.active ? "*" : " "}${t.discarded ? "Z" : " "}w${t.windowId} ${String(t.url).slice(0, 60)} title=${String(t.title || "").slice(0, 24)}`);
  } catch (e) {
    return ["query失败: " + String(e)];
  }
}

async function ensureChatGptTab() {
  // 1) 优先：最近报到过 content.js 的标签（说明脚本已在跑、页面可用）
  let readyTabId = null;
  try {
    const { lastContentReady } = await chrome.storage.session.get("lastContentReady");
    if (lastContentReady && lastContentReady.tabId != null) readyTabId = lastContentReady.tabId;
  } catch (e) { /* ignore */ }

  const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*", "https://chat.openai.com/*"] });

  if (readyTabId != null) {
    const hit = tabs.find((t) => t.id === readyTabId);
    if (hit) return hit;
  }

  // 2) 其次：加载完成、且真的能注入的标签（排除 "showing error page" 这类死标签）
  //    优先当前激活的标签 —— 它才是用户真正在看、且处于未节流状态的那个
  const cand = tabs.filter((t) => t.status === "complete" && /^https:\/\/(chatgpt\.com|chat\.openai\.com)\//.test(t.url || ""));

  // 候选打分：必须同时满足「有 composer」和「消息列表已渲染」。
  // 刚由首页 SPA 导航过来的新会话页 URL 是 /c/xxx 但 user 消息为 0、composer 聚焦不到，
  // 在那儿发送会被静默丢弃（实测 userTurns 0->0）。
  const scored = [];
  for (const t of cand) {
    try {
      const res = await chrome.scripting.executeScript({
        target: { tabId: t.id },
        func: () => ({
          u: document.querySelectorAll('[data-message-author-role="user"]').length,
          c: !!document.querySelector('#prompt-textarea[contenteditable="true"]'),
          url: location.href,
        }),
      });
      const v = res && res[0] && res[0].result;
      if (v) scored.push({ t, u: v.u, c: v.c, conv: /\/c\/[0-9a-f-]{8,}/i.test(v.url || "") });
    } catch (e) { /* 死标签，跳过 */ }
  }
  const best = scored
    .filter((s) => s.c)
    .sort((a, b) => (Number(b.u > 0) - Number(a.u > 0)) ||
                    (Number(b.conv) - Number(a.conv)) ||
                    (Number(b.t.active) - Number(a.t.active)));
  if (best.length) return best[0].t;

  // 2b) 没会话页就用首页（会新建会话，成功率略低）
  for (const t of cand.sort((a, b) => Number(b.active) - Number(a.active))) {
    try {
      await chrome.scripting.executeScript({ target: { tabId: t.id }, func: () => 1 });
      return t;
    } catch (e) { /* 死标签/受限页，跳过 */ }
  }

  // 3) 最后：新建一个
  const tab = await chrome.tabs.create({ url: "https://chatgpt.com/", active: false });
  await new Promise((resolve) => {
    const listener = (tabId, info) => {
      if (tabId === tab.id && info.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
    setTimeout(resolve, 15000); // 兜底
  });
  return tab;
}

async function dispatchJob(job) {
  const tab = await ensureChatGptTab();
  // 把目标标签/窗口提到前台：既是让用户亲眼看到发生了什么，
  // 也避免后台标签被 Chrome 节流导致页面不推进。
  try {
    await chrome.tabs.update(tab.id, { active: true });
    if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true });
  } catch (e) { /* ignore */ }
  // 强制重载一次：SPA 半初始化状态（URL 已是 /c/xxx 但消息列表没渲染）会导致发送被静默丢弃。
  // 刷新后页面是干净完整状态，composer 与消息列表都可用。
  await progressToBridge({ jobId: job.jobId, step: "reload-tab", extra: `id=${tab.id}` });
  await reloadTabFresh(tab.id);
  await progressToBridge({ jobId: job.jobId, step: "tab-picked", extra: `id=${tab.id} active=${tab.active} ${String(tab.url).slice(0, 70)}` });
  await progressToBridge({ jobId: job.jobId, step: "all-tabs", extra: (await describeTabs()).join(" ;; ") });
  // content.js 是声明式注入，但保险起见再注入一次（幂等）
  let execErr = "";
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
  } catch (e) { execErr = String((e && e.message) || e); }
  // 重试几次 sendMessage，给页面留出 ready 时间
  let sendErr = "";
  for (let i = 0; i < 5; i++) {
    try {
      await chrome.tabs.sendMessage(tab.id, { type: "GENERATE", job });
      return; // 派发成功；结果走 runtime 消息回来
    } catch (e) {
      sendErr = String((e && e.message) || e);
      await new Promise((r) => setTimeout(r, 1500));
    }
  }
  // 带上标签页真实状态，便于定位（登录页？还在 loading？注入被拒？）
  let info = null;
  try { info = await chrome.tabs.get(tab.id); } catch (e) { /* ignore */ }
  let ready = null;
  try { ready = (await chrome.storage.session.get("lastContentReady")).lastContentReady; } catch (e) { /* ignore */ }
  const diag = [
    `tabId=${tab.id}`,
    `url=${info && info.url}`,
    `status=${info && info.status}`,
    execErr ? `exec=${execErr}` : "exec=ok",
    sendErr ? `send=${sendErr}` : "send=?",
    ready ? `ready=${ready.url}@${new Date(ready.ts).toLocaleTimeString("zh-CN")}` : "ready=从未报到",
  ].join(" ");
  await reportError(job.jobId, `content.js 未就绪 | ${diag}`);
}

// content.js 生完图回传
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "CDP_INPUT") {
    // 浏览器级真实输入：绕过 React/ProseMirror 对合成事件的拦截
    doCdpInput(sender.tab && sender.tab.id, msg)
      .then((r) => sendResponse(r))
      .catch((e) => sendResponse({ ok: false, error: String((e && e.message) || e) }));
    return true; // 异步
  }
  if (msg && msg.type === "PROGRESS") {
    progressToBridge(msg).catch(() => {});
    sendResponse({ ack: true });
    return false;
  }
  if (msg && msg.type === "CONTENT_READY") {
    chrome.storage.session.set({
      lastContentReady: { url: msg.url, ts: msg.ts, tabId: sender.tab && sender.tab.id },
    }).catch(() => {});
    sendResponse({ ack: true });
    return false;
  }
  if (msg && msg.type === "GENERATE_RESULT") {
    handleResult(msg).finally(() => sendResponse({ ack: true }));
    return true; // 异步
  }
});

async function handleResult(msg) {
  const { jobId, ok, imageUrl, imageBase64, mime, error } = msg;
  try {
    if (!ok) {
      await reportError(jobId, error || "content.js 报告失败");
      return;
    }
    let b64 = imageBase64;
    let m = mime || "image/png";
    if (!b64 && imageUrl) {
      const r = await fetch(imageUrl); // SW 有 oaiusercontent host 权限
      const blob = await r.blob();
      m = blob.type || m;
      b64 = await blobToBase64(blob);
    }
    if (!b64) {
      await reportError(jobId, "没拿到图片字节，imageUrl=" + String(imageUrl || "").slice(0, 100));
      return;
    }
    await postResult({ jobId, ok: true, imageBase64: b64, mime: m });
  } catch (e) {
    await reportError(jobId, `取图片字节失败: ${e} | src=${String(imageUrl || "").slice(0, 90)} | canvas=${msg.convErr || "n/a"}`);
  } finally {
    for (const id of [..._cdpAttached]) await cdpDetach(id); // 收掉调试条，避免常驻
    await chrome.storage.session.remove("activeJob");
    setTimeout(() => pollLoop(), 50);
  }
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result).split(",")[1]);
    fr.onerror = reject;
    fr.readAsDataURL(blob);
  });
}

async function postResult(payload) {
  const base = await bridgeBase();
  try {
    await fetch(base + "/result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch (e) { /* 桥可能已关，忽略 */ }
}

// 步骤时间线上报（排查卡在哪一步）
async function progressToBridge(msg) {
  const base = await bridgeBase();
  try {
    await fetch(base + "/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: msg.jobId, step: msg.step, extra: msg.extra || "" }),
    });
  } catch (e) { /* ignore */ }
}

async function reportError(jobId, error) {
  for (const id of [..._cdpAttached]) await cdpDetach(id);
  await chrome.storage.session.remove("activeJob");
  await postResult({ jobId, ok: false, error });
  setTimeout(() => pollLoop(), 50);
}

// 保活 + 启动
chrome.alarms.create("keepalive", { periodInMinutes: 0.34 }); // ~20s
chrome.alarms.onAlarm.addListener(() => pollLoop());
chrome.runtime.onStartup.addListener(() => pollLoop());
chrome.runtime.onInstalled.addListener(() => pollLoop());
pollLoop();
