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

  function linkify(escapedText) {
    return escapedText.replace(LINK_RE, function (match, urlMatch, phoneMatch) {
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
        return '<a href="tel:' + digits + '">' + phoneMatch + "</a>";
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
    ";color:#fff;padding:14px 16px;font-weight:600;display:flex;justify-content:space-between;align-items:center;}" +
    ".close{cursor:pointer;opacity:.85;font-size:18px;line-height:1;}" +
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
    ".inputRow input{flex:1;border:1px solid #ddd;border-radius:20px;padding:9px 14px;font-size:14px;outline:none;}" +
    ".inputRow button{background:" +
    ACCENT +
    ";color:#fff;border:none;border-radius:20px;padding:0 16px;font-size:14px;cursor:pointer;}" +
    ".inputRow button:disabled{opacity:.5;cursor:default;}";
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

  var headerTitleHtml = AVATAR_URL
    ? '<span class="titleRow"><img class="avatar" src="' + escHtml(AVATAR_URL) + '" alt="" onerror="this.remove()" />' + escHtml(BUSINESS_NAME) + "</span>"
    : "<span>" + escHtml(BUSINESS_NAME) + "</span>";

  var panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML =
    '<div class="header">' +
    headerTitleHtml +
    '<span class="close">✕</span></div>' +
    '<div class="messages"></div>' +
    '<div class="inputRow"><input type="text" placeholder="Type a message..." /><button>Send</button></div>';
  root.appendChild(panel);

  var messagesEl = panel.querySelector(".messages");
  var inputEl = panel.querySelector("input");
  var sendBtn = panel.querySelector("button");
  var closeBtn = panel.querySelector(".close");

  function addMessage(role, text) {
    var el = document.createElement("div");
    el.className = "msg " + role;
    el.innerHTML = linkify(escHtml(text));
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
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

  var sending = false;
  function sendMessage() {
    var text = inputEl.value.trim();
    if (!text || sending) return;
    addMessage("user", text);
    inputEl.value = "";
    sending = true;
    sendBtn.disabled = true;
    var typingEl = addTypingIndicator();

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
