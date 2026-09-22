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
  let reconnectTimer;
  let manuallyClosed = false;

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
    const avatar = (url, initials, mine) => `
      <span class="grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-full ${mine ? "bg-primary text-white" : "bg-primary-soft text-primary"} text-[10px] font-semibold">
        ${url ? `<img class="h-full w-full object-cover" src="${escapeHtml(url)}" alt="">` : escapeHtml(initials || "")}
      </span>`;
    const senderAvatar = avatar(
      message.sender.profile_picture_url,
      (message.sender.full_name || "").split(" ").map((part) => part[0]).join("").slice(0, 2),
      false,
    );
    const currentUserAvatar = avatar(
      chat.dataset.userAvatarUrl,
      chat.dataset.userInitials,
      true,
    );
    const time = new Intl.DateTimeFormat(document.documentElement.lang || "fr", {
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(message.created_at));
    feed.insertAdjacentHTML("beforeend", `
      <div class="mb-4 flex items-end gap-2 ${mine ? "justify-end" : ""}">
        ${mine ? "" : senderAvatar}
        <article class="chat-bubble ${mine ? "chat-bubble--mine" : ""}">
          ${mine ? "" : `<span class="chat-bubble__name">${escapeHtml(message.sender.full_name || "")}</span>`}
          <p>${escapeHtml(message.content).replace(/\n/g, "<br>")}</p>
          <time>${time}</time>
        </article>
        ${mine ? currentUserAvatar : ""}
      </div>`);
    scrollToLatest();
  };

  const connect = () => {
    const scheme = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${scheme}://${window.location.host}/ws/communications/conversation/${conversationId}/`);
    socket.onopen = () => {
      window.clearTimeout(reconnectTimer);
      chat.dataset.connected = "true";
      if (status) status.textContent = status.dataset.connectedText;
    };
    socket.onclose = () => {
      chat.dataset.connected = "false";
      if (status) status.textContent = status.dataset.disconnectedText;
      if (!manuallyClosed) {
        reconnectTimer = window.setTimeout(connect, 2000);
      }
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
  window.addEventListener("beforeunload", () => {
    manuallyClosed = true;
    window.clearTimeout(reconnectTimer);
    socket?.close();
  });
})();
