/** Password visibility toggle for the sign-in form. */
document.addEventListener('DOMContentLoaded', () => {
  const passwordInput = document.getElementById('password');
  const toggleButton = document.getElementById('togglePassword');

  if (toggleButton && passwordInput) {
    toggleButton.addEventListener('click', () => {
      const isPassword = passwordInput.type === 'password';
      passwordInput.type = isPassword ? 'text' : 'password';
      const icon = toggleButton.querySelector('i');
      if (icon) {
        icon.className = isPassword ? 'ti ti-eye-off text-lg' : 'ti ti-eye text-lg';
      }
      const showLabel = toggleButton.dataset.i18nShow || gettext('Show password');
      const hideLabel = toggleButton.dataset.i18nHide || gettext('Hide password');
      toggleButton.setAttribute('aria-label', isPassword ? hideLabel : showLabel);
    });
  }
});
