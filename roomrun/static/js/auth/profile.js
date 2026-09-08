/**
 * Profile page AJAX interactions.
 */
(function () {
  'use strict';

  const form = document.getElementById('profile-form');
  const messageContainer = document.getElementById('profile-message-container');

  if (!form || !messageContainer) {
    return;
  }

  function showAlert(message, type) {
    const alertEl = document.createElement('div');
    alertEl.className = 'rr-alert mb-4 flex items-start justify-between gap-3 rounded-card border px-4 py-3 text-sm';

    if (type === 'success') {
      alertEl.classList.add('rr-alert-success');
      alertEl.setAttribute('role', 'status');
      alertEl.setAttribute('aria-live', 'polite');
    } else if (type === 'error') {
      alertEl.classList.add('rr-alert-error');
      alertEl.setAttribute('role', 'alert');
    } else {
      alertEl.classList.add('rr-alert-warning');
      alertEl.setAttribute('role', 'alert');
    }

    const textNode = document.createElement('span');
    textNode.textContent = message;
    alertEl.appendChild(textNode);

    const closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'shrink-0 text-current/70 hover:text-current';
    closeButton.innerHTML = '&times;';
    closeButton.setAttribute('aria-label', 'Close');
    closeButton.addEventListener('click', function () {
      alertEl.remove();
    });
    alertEl.appendChild(closeButton);

    messageContainer.prepend(alertEl);

    if (type === 'success') {
      setTimeout(function () {
        alertEl.remove();
      }, 5000);
    }
  }

  function showFieldErrors(errors) {
    Object.entries(errors).forEach(function (entries) {
      const field = entries[0];
      const messages = entries[1];
      if (Array.isArray(messages)) {
        messages.forEach(function (msg) {
          showAlert(msg, 'error');
        });
      } else {
        showAlert(messages, 'error');
      }
    });
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();

    const formData = new FormData(form);

    fetch(window.location.href, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    })
      .then(function (response) {
        return response.json().then(function (data) {
          return { status: response.status, data: data };
        });
      })
      .then(function (_ref) {
        var status = _ref.status;
        var data = _ref.data;

        messageContainer.innerHTML = '';

        if (data.success) {
          showAlert(data.message || 'Profil mis à jour.', 'success');

          if (data.user_data) {
            var fullName = [data.user_data.first_name, data.user_data.last_name]
              .filter(Boolean)
              .join(' ')
              .trim();
            if (fullName) {
              var displayNameEl = document.getElementById('display-name');
              if (displayNameEl) {
                displayNameEl.textContent = fullName;
              }
            }
          }

          document.dispatchEvent(new CustomEvent('profile:updated', { detail: data }));
        } else {
          if (data.errors) {
            showFieldErrors(data.errors);
          } else {
            showAlert('Une erreur inattendue est survenue.', 'error');
          }
          messageContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      })
      .catch(function () {
        messageContainer.innerHTML = '';
        showAlert('Erreur de communication avec le serveur. Veuillez réessayer.', 'error');
      });
  });
})();
