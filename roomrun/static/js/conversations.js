(() => {
  "use strict";

  const chat = document.querySelector("[data-chat]");
  const dialog = document.querySelector("[data-start-conversation-dialog]");
  document.querySelector("[data-open-start-conversation]")?.addEventListener("click", () => dialog?.showModal());
  document.querySelectorAll("[data-close-start-conversation]").forEach((button) => {
    button.addEventListener("click", () => dialog?.close());
  });
  dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  document.querySelectorAll("[data-delete-conversation]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm("Delete this conversation and all of its messages?")) {
        event.preventDefault();
      }
    });
  });

  if (!chat) return;

  const feed = document.querySelector("[data-message-feed]");
  const form = document.querySelector("[data-message-form]");
  const input = document.querySelector("[data-message-input]");
  const status = document.querySelector("[data-chat-status]");
  const conversationId = chat.dataset.conversationId;
  let socket;
  let typingTimer;

  const scrollToLatest = () => {
    if (feed) feed.scrollTop = feed.scrollHeight;
  };

  const escapeHtml = (value) => {
    const element = document.createElement("span");
    element.textContent = value;
    return element.innerHTML;
  };

  const appendMessage = (message) => {
    if (!feed) return;
    const mine = String(message.sender.id) === chat.dataset.userId;
    const time = new Intl.DateTimeFormat(document.documentElement.lang || "fr", {
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(message.created_at));
    feed.insertAdjacentHTML("beforeend", `
      <article class="chat-bubble ${mine ? "chat-bubble--mine" : ""}">
        ${mine ? "" : `<span class="chat-bubble__name">${escapeHtml(message.sender.full_name || "")}</span>`}
        <p>${escapeHtml(message.content).replace(/\n/g, "<br>")}</p>
        <time>${time}</time>
      </article>`);
    scrollToLatest();
  };

  const connect = () => {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/ws/communications/conversation/${conversationId}/`);
    socket.onopen = () => {
      chat.dataset.connected = "true";
      if (status) status.textContent = status.dataset.connectedText;
    };
    socket.onclose = () => {
      chat.dataset.connected = "false";
      if (status) status.textContent = status.dataset.disconnectedText;
    };
    socket.onerror = () => {
      if (status) status.textContent = status.dataset.disconnectedText;
    };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "message") appendMessage(payload);
      if (payload.type === "typing" && status) {
        status.textContent = payload.is_typing ? status.dataset.typingText : status.dataset.connectedText;
      }
      if (payload.type === "error" && status) status.textContent = payload.detail;
    };
  };

  form?.addEventListener("submit", (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content || socket?.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "message", content }));
    input.value = "";
    socket.send(JSON.stringify({ type: "typing", is_typing: false }));
  });

  input?.addEventListener("input", () => {
    if (socket?.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: "typing", is_typing: Boolean(input.value.trim()) }));
    window.clearTimeout(typingTimer);
    typingTimer = window.setTimeout(() => {
      socket.send(JSON.stringify({ type: "typing", is_typing: false }));
    }, 1200);
  });

  scrollToLatest();
  if (conversationId) connect();
})();
