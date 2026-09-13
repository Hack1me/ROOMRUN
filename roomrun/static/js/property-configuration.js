/** Interactions for step 2 of the property creation flow. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('[data-configuration-form]');
    const currency = form?.querySelector('select[name="default_currency"]');
    const summaryCurrency = document.getElementById('summaryCurrency');
    const summaryStatus = document.getElementById('summaryStatus');
    const actionInput = document.getElementById('configurationAction');

    currency?.addEventListener('change', function () {
      if (summaryCurrency) summaryCurrency.textContent = currency.value;
    });

    form?.querySelectorAll('input[name="status"]').forEach(function (input) {
      input.addEventListener('change', function () {
        if (!summaryStatus) return;
        summaryStatus.replaceChildren();
        const dot = document.createElement('span');
        dot.className = 'summary-status-dot summary-status-dot--' + input.value.toLowerCase();
        summaryStatus.append(dot, input.dataset.statusLabel || input.value);
      });
    });

    document.getElementById('backButton')?.addEventListener('click', function () {
      window.location.assign(form?.dataset.backUrl || window.location.href);
    });
    document.getElementById('saveButton')?.addEventListener('click', function () {
      if (actionInput) actionInput.value = 'save';
    });
    document.getElementById('continueButton')?.addEventListener('click', function () {
      if (actionInput) actionInput.value = 'continue';
    });
  });
})();
