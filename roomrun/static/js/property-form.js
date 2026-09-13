/** Interactions for step 1 of the property creation flow. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const form = document.querySelector('[data-property-form]');
    const description = form?.querySelector('[data-description-input]');
    const characterCount = document.getElementById('characterCount');
    const actionInput = document.getElementById('propertyAction');

    function updateCharacterCount() {
      if (description && characterCount) {
        characterCount.textContent = String(description.value.length) + '/500';
      }
    }

    description?.addEventListener('input', updateCharacterCount);
    updateCharacterCount();
    document.getElementById('saveButton')?.addEventListener('click', function () {
      if (actionInput) actionInput.value = 'save';
    });
    document.getElementById('continueButton')?.addEventListener('click', function () {
      if (actionInput) actionInput.value = 'continue';
    });
    document.getElementById('cancelButton')?.addEventListener('click', function () {
      window.location.assign(form?.dataset.cancelUrl || window.location.href);
    });
  });
})();
