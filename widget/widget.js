(function () {
  "use strict";

  var scriptTag = document.currentScript;
  var API_BASE = (scriptTag && scriptTag.getAttribute("data-api-base")) || "";
  var BUSINESS_NAME = (scriptTag && scriptTag.getAttribute("data-business-name")) || "Chat with us";
  var ACCENT = (scriptTag && scriptTag.getAttribute("data-color")) || "#4f46e5";
  var AVATAR_URL = (scriptTag && scriptTag.getAttribute("data-avatar-url")) || "";
  var GREETING =
    (scriptTag && scriptTag.getAttribute("data-greeting")) ||
    "Hi! I'm the AI assistant here — ask me anything or book an appointment.";
  var SUGGESTED_QUESTIONS = [];
  try {
    SUGGESTED_QUESTIONS = JSON.parse((scriptTag && scriptTag.getAttribute("data-suggested-questions")) || "[]");
  } catch (e) {
    SUGGESTED_QUESTIONS = [];
  }

  if (!API_BASE) {
    console.error("[ai-frontdesk widget] Missing data-api-base on the script tag.");
    return;
  }

  function escHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // Matches a URL or a phone-shaped number in one pass so neither can be re-processed
  // inside the other's replacement (a nested <a> would break click behavior).
  var LINK_RE = /(https?:\/\/[^\s<>"')]+)|(\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})/g;

  var TEXT_CONTEXT_RE = /\b(text|sms|txt)\b/i;

  function linkify(escapedText) {
    return escapedText.replace(LINK_RE, function (match, urlMatch, phoneMatch, offset, fullString) {
      if (urlMatch) {
        var trail = "";
        var trailMatch = urlMatch.match(/[.,;:!?)\]]+$/);
        var url = urlMatch;
        if (trailMatch) {
          trail = trailMatch[0];
          url = urlMatch.slice(0, -trail.length);
        }
        return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + url + "</a>" + trail;
      }
      if (phoneMatch) {
        var digits = phoneMatch.replace(/[^\d+]/g, "");
        if (digits.replace(/\D/g, "").length < 10) return match; // avoid false positives, e.g. short numbers
        // "text us at 555-..." should open Messages, not the dialer — check the words just
        // before the number for that intent, defaulting to a phone call otherwise.
        var precedingText = fullString.slice(Math.max(0, offset - 25), offset);
        var scheme = TEXT_CONTEXT_RE.test(precedingText) ? "sms" : "tel";
        return '<a href="' + scheme + ":" + digits + '">' + phoneMatch + "</a>";
      }
      return match;
    });
  }

  var SESSION_KEY = "ai_frontdesk_session_id";
  function getSessionId() {
    try {
      var id = localStorage.getItem(SESSION_KEY);
      if (!id) {
        id = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
        localStorage.setItem(SESSION_KEY, id);
      }
      return id;
    } catch (e) {
      return "sess_" + Math.random().toString(36).slice(2);
    }
  }
  var sessionId = getSessionId();

  var host = document.createElement("div");
  host.id = "ai-frontdesk-widget-host";
  document.body.appendChild(host);
  var root = host.attachShadow({ mode: "open" });

  var style = document.createElement("style");
  style.textContent =
    "*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}" +
    ".bubble{position:fixed;bottom:20px;right:20px;width:60px;height:60px;border-radius:50%;background:" +
    ACCENT +
    ";box-shadow:0 4px 14px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center;cursor:pointer;z-index:2147483000;transition:transform .15s ease;}" +
    ".bubble:hover{transform:scale(1.06);}" +
    ".bubble svg{width:28px;height:28px;fill:#fff;}" +
    ".bubble img{width:46px;height:46px;border-radius:50%;object-fit:cover;}" +
    ".header .avatar{width:26px;height:26px;border-radius:50%;object-fit:cover;margin-right:8px;vertical-align:middle;}" +
    ".header .titleRow{display:flex;align-items:center;}" +
    ".panel{position:fixed;bottom:92px;right:20px;width:340px;max-width:90vw;height:480px;max-height:70vh;background:#fff;border-radius:16px;box-shadow:0 8px 30px rgba(0,0,0,.25);display:none;flex-direction:column;overflow:hidden;z-index:2147483000;}" +
    ".panel.open{display:flex;}" +
    ".header{background:" +
    ACCENT +
    ";color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center;position:relative;}" +
    ".header.hero{flex-direction:column;align-items:center;justify-content:center;padding:20px 16px 14px;gap:5px;}" +
    ".header.hero .heroAvatar{width:52px;height:52px;border-radius:50%;object-fit:cover;border:3px solid rgba(255,255,255,.92);box-shadow:0 4px 14px rgba(0,0,0,.2);}" +
    ".header.hero .heroName{font-size:14.5px;font-weight:700;}" +
    ".header.hero .headerActions{position:absolute;top:10px;right:10px;margin:0;}" +
    ".headerActions{display:flex;align-items:center;margin:-8px -10px -8px 0;}" +
    ".close,.reset{cursor:pointer;opacity:.85;font-size:18px;line-height:1;display:flex;align-items:center;justify-content:center;width:36px;height:36px;}" +
    ".reset{font-size:16px;}" +
    ".messages{flex:1;overflow-y:auto;padding:12px;background:#f7f7f9;display:flex;flex-direction:column;gap:8px;}" +
    ".msg{max-width:80%;padding:8px 12px;border-radius:14px;font-size:14px;line-height:1.35;white-space:pre-wrap;}" +
    ".msg.user{align-self:flex-end;background:" +
    ACCENT +
    ";color:#fff;border-bottom-right-radius:4px;}" +
    ".msg.assistant{align-self:flex-start;background:#fff;color:#222;border:1px solid #e5e5ea;border-bottom-left-radius:4px;}" +
    ".msg a{color:" +
    ACCENT +
    ";font-weight:600;text-decoration:underline;word-break:break-all;}" +
    ".msg.user a{color:#fff;}" +
    ".msg.typing{align-self:flex-start;background:#fff;border:1px solid #e5e5ea;padding:11px 14px;}" +
    ".typing-dots{display:inline-flex;gap:4px;align-items:center;}" +
    ".typing-dots span{width:6px;height:6px;border-radius:50%;background:#9aa0a6;display:inline-block;animation:leadguardTypingBounce 1.2s infinite ease-in-out;}" +
    ".typing-dots span:nth-child(2){animation-delay:.15s;}" +
    ".typing-dots span:nth-child(3){animation-delay:.3s;}" +
    "@keyframes leadguardTypingBounce{0%,60%,100%{transform:translateY(0);opacity:.4;}30%{transform:translateY(-4px);opacity:1;}}" +
    ".inputRow{display:flex;border-top:1px solid #eee;padding:8px;gap:8px;}" +
    // font-size must be >=16px or iOS Safari auto-zooms the page on focus, which is jarring
    // inside an embedded widget — this isn't a style preference, it's a hard mobile threshold.
    ".inputRow input{flex:1;min-height:44px;border:1px solid #ddd;border-radius:22px;padding:9px 14px;font-size:16px;outline:none;}" +
    ".inputRow button{min-height:44px;min-width:44px;background:" +
    ACCENT +
    ";color:#fff;border:none;border-radius:22px;padding:0 18px;font-size:15px;cursor:pointer;}" +
    ".inputRow button:disabled{opacity:.5;cursor:default;}" +
    ".suggestions{position:fixed;bottom:90px;right:20px;z-index:2147482999;display:flex;flex-direction:column;align-items:flex-end;gap:8px;max-width:280px;}" +
    ".suggestions button{font-family:inherit;font-size:13px;text-align:left;background:#fff;border:1px solid #ddd;border-radius:14px;padding:9px 14px;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.12);transition:transform .1s ease,border-color .1s ease;}" +
    ".suggestions button:hover{border-color:" +
    ACCENT +
    ";transform:translateY(-1px);}";
  root.appendChild(style);

  var CHAT_ICON_SVG =
    '<svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.03 2 11c0 2.4 1.05 4.57 2.77 6.19-.13 1.32-.6 2.83-1.62 4.09a.5.5 0 00.5.72c2.13-.35 3.7-1.24 4.63-1.9A11.4 11.4 0 0012 21c5.52 0 10-4.03 10-9s-4.48-9-10-9z"/></svg>';

  var bubble = document.createElement("div");
  bubble.className = "bubble";
  if (AVATAR_URL) {
    bubble.innerHTML = '<img src="' + escHtml(AVATAR_URL) + '" alt="" />';
    bubble.querySelector("img").addEventListener("error", function () {
      bubble.innerHTML = CHAT_ICON_SVG;
    });
  } else {
    bubble.innerHTML = CHAT_ICON_SVG;
  }
  root.appendChild(bubble);

  var suggestionsEl = null;
  if (SUGGESTED_QUESTIONS.length) {
    suggestionsEl = document.createElement("div");
    suggestionsEl.className = "suggestions";
    SUGGESTED_QUESTIONS.slice(0, 3).forEach(function (q) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = q;
      btn.addEventListener("click", function () {
        openPanel();
        inputEl.value = q;
        sendMessage();
      });
      suggestionsEl.appendChild(btn);
    });
    root.appendChild(suggestionsEl);
  }

  // With an avatar configured, the header becomes a tall, centered "hero" card (avatar
  // top and center, name below) so visitors immediately see a face, not just a color bar.
  // Without one, it stays the compact single-line bar it always was.
  var headerIsHero = !!AVATAR_URL;
  var headerBodyHtml = headerIsHero
    ? '<img class="heroAvatar" src="' +
      escHtml(AVATAR_URL) +
      '" alt="" onerror="this.parentElement.classList.remove(\'hero\');this.remove();" />' +
      '<span class="heroName">' +
      escHtml(BUSINESS_NAME) +
      "</span>"
    : "<span>" + escHtml(BUSINESS_NAME) + "</span>";

  var panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML =
    '<div class="header' + (headerIsHero ? " hero" : "") + '">' +
    headerBodyHtml +
    '<span class="headerActions"><span class="reset" title="Start a new conversation">↺</span><span class="close">✕</span></span></div>' +
    '<div class="messages"></div>' +
    '<div class="inputRow"><input type="text" placeholder="Type a message..." /><button>Send</button></div>';
  root.appendChild(panel);

  var messagesEl = panel.querySelector(".messages");
  var inputEl = panel.querySelector("input");
  var sendBtn = panel.querySelector("button");
  var closeBtn = panel.querySelector(".close");
  var resetBtn = panel.querySelector(".reset");

  function addMessage(role, text) {
    var el = document.createElement("div");
    el.className = "msg " + role;
    messagesEl.appendChild(el);

    if (role !== "assistant") {
      el.innerHTML = linkify(escHtml(text));
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return el;
    }

    // Assistant replies reveal progressively instead of landing as one instant block,
    // and scroll anchors to the TOP of this message rather than scrollTop = scrollHeight
    // (the bottom) — a reply taller than the visible chat window previously landed with
    // its ending in view and its beginning already scrolled past, forcing the visitor to
    // scroll back up just to read it from the start. Anchoring once at the top and then
    // leaving scroll alone as the text fills in keeps the beginning in view throughout.
    el.scrollIntoView({ block: "start" });
    var words = text.split(/(\s+)/);
    var i = 0;
    var shown = "";
    (function reveal() {
      if (i < words.length) {
        shown += words[i];
        el.innerHTML = linkify(escHtml(shown));
        i++;
        setTimeout(reveal, 20);
      }
    })();
    return el;
  }

  function addTypingIndicator() {
    var el = document.createElement("div");
    el.className = "msg typing";
    el.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return el;
  }

  var greeted = false;
  function openPanel() {
    panel.classList.add("open");
    if (suggestionsEl) suggestionsEl.style.display = "none";
    if (!greeted) {
      addMessage("assistant", GREETING);
      greeted = true;
    }
    inputEl.focus();
  }
  bubble.addEventListener("click", function () {
    if (panel.classList.contains("open")) {
      panel.classList.remove("open");
    } else {
      openPanel();
    }
  });
  closeBtn.addEventListener("click", function () {
    panel.classList.remove("open");
  });
  resetBtn.addEventListener("click", function () {
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch (e) {}
    sessionId = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    try {
      localStorage.setItem(SESSION_KEY, sessionId);
    } catch (e) {}
    messagesEl.innerHTML = "";
    greeted = false;
    addMessage("assistant", GREETING);
    greeted = true;
  });

  // Opt-in only (?record=1 on the page this widget is embedded in — never present on a
  // real client's own site, only on our own demo pages in recording mode). Without this,
  // the sent question and the "typing..." indicator appear in the exact same instant,
  // which reads as rushed on a screen recording — a real visitor doesn't need or want
  // the delay, so this never touches normal response latency.
  var RECORD_MODE_SEND_PAUSE_MS = /[?&]record=1(&|$)/.test(window.location.search) ? 1100 : 0;

  var sending = false;
  function sendMessage() {
    var text = inputEl.value.trim();
    if (!text || sending) return;
    addMessage("user", text);
    inputEl.value = "";
    sending = true;
    sendBtn.disabled = true;

    setTimeout(function () {
      var typingEl = addTypingIndicator();
      doSend(text, typingEl);
    }, RECORD_MODE_SEND_PAUSE_MS);
  }

  function doSend(text, typingEl) {
    fetch(API_BASE.replace(/\/$/, "") + "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: text }),
    })
      .then(function (res) {
        if (!res.ok) throw new Error("Request failed");
        return res.json();
      })
      .then(function (data) {
        typingEl.remove();
        addMessage("assistant", data.reply || "Sorry, something went wrong.");
      })
      .catch(function () {
        typingEl.remove();
        addMessage("assistant", "Sorry, I couldn't reach the server. Please try again in a moment.");
      })
      .finally(function () {
        sending = false;
        sendBtn.disabled = false;
      });
  }

  sendBtn.addEventListener("click", sendMessage);
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter") sendMessage();
  });
})();
