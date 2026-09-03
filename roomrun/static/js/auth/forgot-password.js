document.addEventListener('DOMContentLoaded', function () {
  const form = document.getElementById('forgotPasswordForm');
  if (!form) return;

  const button = document.getElementById('submitButton');
  if (!button) return;

  const spinner = button.querySelector('.spinner');
  const buttonText = button.querySelector('.button-text');
  const buttonIcon = button.querySelector('.button-icon');

  const labels = {
    sending: buttonText ? buttonText.textContent.trim() : '',
    send: buttonText ? buttonText.dataset.labelSend || buttonText.textContent.trim() : ''
  };

  form.addEventListener('submit', function () {
    button.disabled = true;
    if (spinner) spinner.classList.remove('hidden');
    if (buttonIcon) buttonIcon.classList.add('hidden');
    if (buttonText) buttonText.textContent = labels.sending || 'Sending...';
  });
});