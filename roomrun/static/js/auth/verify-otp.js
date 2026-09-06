/**
 * OTP input management, timer, and form validation for the verification page.
 */
(function () {
  'use strict';

  const otpInputs = document.querySelectorAll('.form-otp');
  const otpCodeField = document.getElementById('otpCode');
  const otpForm = document.getElementById('otpForm');
  const verifyButton = document.getElementById('verifyButton');
  const resendButton = document.getElementById('resendButton');
  const errorMessage = document.getElementById('errorMessage');
  const timerElement = document.getElementById('timer');

  if (!otpInputs.length || !otpForm) return;

  otpInputs.forEach((input, index) => {
    input.addEventListener('input', (e) => {
      const value = e.target.value.replace(/\D/g, '');
      e.target.value = value.slice(0, 1);

      if (value) {
        e.target.classList.add('filled');
        if (index < otpInputs.length - 1) {
          otpInputs[index + 1].focus();
        }
      } else {
        e.target.classList.remove('filled');
      }

      updateVerifyButton();
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !input.value && index > 0) {
        otpInputs[index - 1].focus();
      }

      if (e.key === 'ArrowLeft' && index > 0) {
        otpInputs[index - 1].focus();
      }
      if (e.key === 'ArrowRight' && index < otpInputs.length - 1) {
        otpInputs[index + 1].focus();
      }
    });

    input.addEventListener('paste', (e) => {
      e.preventDefault();
      const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);

      pasted.split('').forEach((digit, i) => {
        if (otpInputs[i]) {
          otpInputs[i].value = digit;
          otpInputs[i].classList.add('filled');
        }
      });

      const lastIndex = Math.min(pasted.length, otpInputs.length) - 1;
      if (lastIndex >= 0) {
        otpInputs[lastIndex].focus();
      }

      updateVerifyButton();
    });
  });

  function updateVerifyButton() {
    const code = Array.from(otpInputs).map((i) => i.value).join('');
    verifyButton.disabled = code.length !== 6;

    if (otpCodeField) {
      otpCodeField.value = code;
    }
  }

  function getTimeoutSeconds() {
    const timeout = timerElement ? timerElement.dataset.timeoutSeconds : null;
    const parsed = parseInt(timeout, 10);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : 120;
  }

  let remainingSeconds = getTimeoutSeconds();
  let timerInterval;

  function updateTimer() {
    const minutes = Math.floor(remainingSeconds / 60).toString().padStart(2, '0');
    const seconds = (remainingSeconds % 60).toString().padStart(2, '0');
    if (timerElement) {
      timerElement.textContent = `${minutes}:${seconds}`;
    }
  }

  function startTimer() {
    clearInterval(timerInterval);
    remainingSeconds = getTimeoutSeconds();
    if (resendButton) {
      resendButton.disabled = true;
    }

    updateTimer();

    timerInterval = setInterval(() => {
      remainingSeconds--;
      updateTimer();

      if (remainingSeconds <= 0) {
        clearInterval(timerInterval);
        if (timerElement) {
          timerElement.textContent = '00:00';
          timerElement.classList.add('expired');
        }
        if (resendButton) {
          resendButton.disabled = false;
        }
      }
    }, 1000);
  }

  startTimer();

  otpForm.addEventListener('submit', (e) => {
    const code = Array.from(otpInputs).map((i) => i.value).join('');

    if (code.length !== 6) {
      e.preventDefault();
      if (errorMessage) {
        const i18nError = otpForm.dataset.i18nError || gettext('Please enter all 6 digits');
        errorMessage.textContent = i18nError;
      }
      return;
    }

    if (otpCodeField) {
      otpCodeField.value = code;
    }
  });

  function shakeInputs() {
    otpInputs.forEach((input) => {
      input.classList.add('shake');
      setTimeout(() => {
        input.classList.remove('shake');
      }, 350);
    });
  }

  if (otpInputs[0]) {
    otpInputs[0].focus();
  }
})();
