/** Client-side previews and drag-and-drop for property image uploads. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const page = document.querySelector('[data-images-page]');
    const input = document.getElementById('imageInput');
    const grid = document.getElementById('imageGrid');
    const count = document.getElementById('imageCount');
    const dropZone = document.getElementById('dropZone');
    if (!page || !input || !grid || !count || !dropZone) return;

    const existing = Number(page.dataset.existingImages || 0);
    const maxImages = 8;

    function setFiles(files) {
      const transfer = new DataTransfer();
      files.slice(0, maxImages - existing).forEach(function (file) {
        transfer.items.add(file);
      });
      input.files = transfer.files;
    }

    function appendFiles(files) {
      setFiles(Array.from(input.files).concat(files));
    }

    function renderPreviews() {
      grid.querySelectorAll('[data-new-image]').forEach(function (tile) {
        tile.remove();
      });
      const selectedFiles = Array.from(input.files).slice(0, maxImages - existing);
      selectedFiles.forEach(function (file, index) {
        const reader = new FileReader();
        reader.addEventListener('load', function () {
          const tile = document.createElement('div');
          tile.className = 'image-tile';
          tile.dataset.newImage = String(index);
          const image = document.createElement('img');
          image.src = String(reader.result);
          image.alt = file.name;
          const removeButton = document.createElement('button');
          removeButton.type = 'button';
          removeButton.className = 'remove-image';
          removeButton.setAttribute('aria-label', 'Remove image');
          removeButton.innerHTML = '<i class="ti ti-x"></i>';
          removeButton.addEventListener('click', function () {
            const files = Array.from(input.files);
            files.splice(index, 1);
            setFiles(files);
            renderPreviews();
          });
          tile.append(image, removeButton);
          grid.insertBefore(tile, grid.lastElementChild);
        });
        reader.readAsDataURL(file);
      });
      count.textContent = String(existing + selectedFiles.length) + '/8';
    }

    input.addEventListener('change', function (event) {
      const selectedFiles = Array.from(event.target.files);
      setFiles(selectedFiles);
      renderPreviews();
    });
    ['dragenter', 'dragover'].forEach(function (eventName) {
      dropZone.addEventListener(eventName, function (event) {
        event.preventDefault();
        dropZone.classList.add('dragover');
      });
    });
    ['dragleave', 'drop'].forEach(function (eventName) {
      dropZone.addEventListener(eventName, function (event) {
        event.preventDefault();
        dropZone.classList.remove('dragover');
      });
    });
    dropZone.addEventListener('drop', function (event) {
      appendFiles(Array.from(event.dataTransfer.files));
      renderPreviews();
    });
  });
})();
