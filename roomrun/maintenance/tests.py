from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from maintenance.forms import MultipleImageField
from PIL import Image


class MultipleImageFieldTests(SimpleTestCase):
    def test_accepts_a_valid_png_photo(self):
        # A valid 1x1 PNG; ImageField validates the actual image bytes.
        image_bytes = BytesIO()
        Image.new("RGB", (1, 1), "white").save(image_bytes, format="PNG")
        photo = SimpleUploadedFile(
            "issue.png", image_bytes.getvalue(), content_type="image/png"
        )

        cleaned = MultipleImageField(required=False).clean([photo])

        assert len(cleaned) == 1

    def test_rejects_a_non_image_upload(self):
        upload = SimpleUploadedFile(
            "unsafe.txt", b"not an image", content_type="text/plain"
        )

        with self.assertRaisesMessage(Exception, "valid image"):
            MultipleImageField(required=False).clean([upload])
