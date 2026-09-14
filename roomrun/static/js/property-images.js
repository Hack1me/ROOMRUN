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
    let selectedFilesList = [];

    function setFiles(files) {
      const transfer = new DataTransfer();
      files.slice(0, maxImages - existing).forEach(function (file) {
        transfer.items.add(file);
      });
      input.files = transfer.files;
    }

    function addFiles(files) {
      selectedFilesList = selectedFilesList.concat(files).slice(0, maxImages - existing);
      setFiles(selectedFilesList);
      renderPreviews();
    }

    function renderPreviews() {
      grid.querySelectorAll('[data-new-image]').forEach(function (tile) {
        tile.remove();
      });
      selectedFilesList.forEach(function (file, index) {
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
            selectedFilesList.splice(index, 1);
            setFiles(selectedFilesList);
            renderPreviews();
          });
          tile.append(image, removeButton);
          const addTile = grid.querySelector('.add-tile');
          if (addTile) {
            grid.insertBefore(tile, addTile);
          } else {
            grid.appendChild(tile);
          }
        });
        reader.readAsDataURL(file);
      });
      count.textContent = String(existing + selectedFilesList.length) + '/8';
    }

    input.addEventListener('change', function (event) {
      const newFiles = Array.from(event.target.files);
      addFiles(newFiles);
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
      addFiles(Array.from(event.dataTransfer.files));
    });

    function getCSRFToken() {
      const cookieValue = document.cookie
        .split('; ')
        .find(function (row) { return row.startsWith('csrftoken='); });
      if (cookieValue) {
        return cookieValue.split('=')[1];
      }
      const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
      return csrfInput ? csrfInput.value : '';
    }

    function deleteImage(imageId, url) {
      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCSRFToken(),
          'X-Requested-With': 'XMLHttpRequest',
        },
        body: '',
      })
      .then(function (response) {
        if (response.ok) {
          window.location.reload();
        } else {
          return response.json().then(function (data) {
            alert(data.message || 'Unable to delete the image.');
          });
        }
      })
      .catch(function () {
        alert('Unable to delete the image.');
      });
    }

    document.querySelectorAll('[data-delete-image-id]').forEach(function (button) {
      button.addEventListener('click', function () {
        var imageId = button.getAttribute('data-delete-image-id');
        var url = button.getAttribute('data-delete-url');
        if (confirm('Are you sure you want to remove this image?')) {
          deleteImage(imageId, url);
        }
      });
    });
  });
})();
