from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from dataclasses import field
from io import BytesIO
from pathlib import Path
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from typing import Any
from typing import BinaryIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.storage import default_storage
from django.http import FileResponse
from django.template.loader import render_to_string
from pypdf import PdfReader
from pypdf import PdfWriter
from utils.enums import Orientation
from utils.enums import PageSize
from weasyprint import CSS
from weasyprint import HTML

if TYPE_CHECKING:
    from collections.abc import Iterable

# Maximum allowed PDF size (bytes). Override via settings if needed.
DEFAULT_MAX_PDF_SIZE = 50 * 1024 * 1024   # 50 MB


# Maximum allowed total input size (bytes) to prevent memory blow-ups.
DEFAULT_MAX_TOTAL_SIZE = 200 * 1024 * 1024  # 200 MB

_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")

## Constants
logger = logging.getLogger(__name__)

# Simple CSS length pattern (e.g., "2cm", "10mm", "0.5in", "20px", "0")
_CSS_LENGTH_SUFFIXES = ("cm", "mm", "in", "pt", "px", "%")


class PDFError(Exception):
    """Base exception for all PDF-related errors."""


class PDFGenerationError(PDFError):
    """Raised when PDF generation fails (e.g., template error, WeasyPrint crash)."""


class PDFStorageError(PDFError):
    """Raised when saving a generated PDF fails (e.g., storage backend error)."""


class PDFMergeError(PDFError):
    """Raised when merging multiple PDFs fails."""


class PDFConfigurationError(PDFError):
    """Raised when the PDF service is misconfigured (e.g., missing settings)."""








@dataclass(slots=True)
class PDFOptions:
    """
    Configuration used to generate a PDF document.
    """

    page_size: str = PageSize.A4.value
    orientation: str = Orientation.PORTRAIT.value

    margin_top: str = "2cm"
    margin_right: str = "2cm"
    margin_bottom: str = "2cm"
    margin_left: str = "2cm"

    print_background: bool = True

    filename: str = "document.pdf"

    metadata: dict[str, Any] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def filename_without_extension(self) -> str:
        """Return the filename without the `.pdf` extension."""
        return self.filename.removesuffix(".pdf")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate the options.

        Raises:
            PDFConfigurationError: If any option is invalid.
        """
        self._validate_page_size()
        self._validate_orientation()
        self._validate_margins()
        self._validate_filename()

    def _validate_page_size(self) -> None:
        valid = {size.value for size in PageSize}
        if self.page_size.upper() not in valid:
            msg = f"Unsupported page size: {self.page_size}"
            raise PDFConfigurationError(
                msg
            )

    def _validate_orientation(self) -> None:
        valid = {o.value for o in Orientation}
        if self.orientation.lower() not in valid:
            msg = f"Unsupported orientation: {self.orientation}"
            raise PDFConfigurationError(
                msg
            )

    def _validate_margins(self) -> None:
        for name in ("margin_top", "margin_right", "margin_bottom", "margin_left"):
            value = getattr(self, name)
            if not self._is_valid_css_length(value):
                msg = (
                    f"Invalid {name}: {value!r}. "
                    f"Expected a number followed by one of "
                    f"{_CSS_LENGTH_SUFFIXES} (e.g., '2cm', '10mm', '0')."
                )
                raise PDFConfigurationError(
                    msg
                )

    def _validate_filename(self) -> None:
        name = self.filename.strip()

        if not name:
            msg = "Filename cannot be empty."
            raise PDFConfigurationError(msg)

        if "/" in name or "\\" in name:
            msg_0 = "Filename must not contain path separators."
            raise PDFConfigurationError(
                msg_0
            )

        if ".." in name:
            msg_1 = "Filename must not contain relative path segments."
            raise PDFConfigurationError(
                msg_1
            )

        if not name.lower().endswith(".pdf"):
            msg_2 = "Filename must end with '.pdf'."
            raise PDFConfigurationError(
                msg_2
            )

    @staticmethod
    def _is_valid_css_length(value: str) -> bool:
        """Return True if the value looks like a CSS length or '0'."""
        if value == "0":
            return True
        if not isinstance(value, str):
            return False
        # Match "number + optional unit"
        for suffix in _CSS_LENGTH_SUFFIXES:
            if value.endswith(suffix):
                number = value[: -len(suffix)]
                try:
                    float(number)
                    return True  # noqa: TRY300
                except ValueError:
                    return False
        return False

    # -------------------------------------------------------------------------
    # Normalization (explicit, opt-in)
    # -------------------------------------------------------------------------

    def normalize_filename(self) -> None:
        """
        Ensure the filename ends with `.pdf` (mutates self).

        Call this explicitly if you want normalization, not validation.
        """
        if not self.filename.lower().endswith(".pdf"):
            self.filename = f"{self.filename}.pdf"


@dataclass(slots=True)
class PDFDocument:
    """
    Represents a PDF document before rendering.

    Exactly one of `template`, `html`, or `url` must be provided.
    The PDF is rendered from that source, using the given context
    and options.
    """

    template: str | None = None
    html: str | None = None
    url: str | None = None

    context: dict[str, Any] = field(default_factory=dict)
    options: PDFOptions = field(default_factory=PDFOptions)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate the document configuration.

        Raises:
            PDFConfigurationError: If the source or options are invalid.
        """
        self._validate_sources()
        self._validate_options()

    def _validate_sources(self) -> None:
        """Ensure exactly one source is provided."""
        sources = {
            "template": self.template,
            "html": self.html,
            "url": self.url,
        }
        provided = [name for name, value in sources.items() if value is not None]

        if not provided:
            msg = "A PDF document requires one of: template, html, or url."
            raise PDFConfigurationError(
                msg
            )

        if len(provided) > 1:
            msg_0 = (
                f"A PDF document must have only one source. "
                f"Got: {', '.join(provided)}."
            )
            raise PDFConfigurationError(
                msg_0
            )

    def _validate_options(self) -> None:
        """Delegate option validation to PDFOptions."""
        self.options.validate()

    # -------------------------------------------------------------------------
    # Convenience
    # -------------------------------------------------------------------------

    @property
    def source_type(self) -> str:
        """
        Return the type of the source: 'template', 'html', or 'url'.

        Assumes `validate()` has been called successfully.
        """
        if self.template is not None:
            return "template"
        if self.html is not None:
            return "html"
        if self.url is not None:
            return "url"
        msg = "No source defined on this PDFDocument."
        raise PDFConfigurationError(msg)


class PDFRenderer:
    """
    Convert PDF documents into PDF files using WeasyPrint.
    """

    def render(self, document: PDFDocument) -> BytesIO:
        """
        Render the given PDFDocument into an in-memory PDF file.

        Raises:
            PDFGenerationError: If rendering fails.
        """
        document.validate()

        try:
            pdf_file = BytesIO()
            source = self._build_source(document)

            source.write_pdf(
                target=pdf_file,
                stylesheets=[self._build_page_css(document)],
            )
            pdf_file.seek(0)
            return pdf_file  # noqa: TRY300

        except PDFGenerationError:
            # Already a domain exception — propagate as-is.
            raise
        except Exception as exc:
            logger.exception("PDF generation failed")
            msg = "Unable to generate PDF."
            raise PDFGenerationError(msg) from exc

    # -------------------------------------------------------------------------
    # Source building
    # -------------------------------------------------------------------------

    def _build_source(self, document: PDFDocument) -> HTML:
        """
        Build the WeasyPrint HTML source from the document.

        Priority is guaranteed by `document.validate()`: exactly one
        of template / html / url is set.
        """
        if document.url:
            # WeasyPrint fetches the URL directly.
            return HTML(url=document.url)

        html = self._build_html(document)
        return HTML(string=html, base_url=self._get_base_url())

    @staticmethod
    def _build_html(document: PDFDocument) -> str:
        """Return the HTML string for template/html sources."""
        if document.template:
            return render_to_string(document.template, document.context)

        if document.html:
            return document.html

        # Should never be reached thanks to document.validate().
        msg = "No valid HTML source was provided."
        raise PDFGenerationError(msg)

    # -------------------------------------------------------------------------
    # Stylesheets
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_page_css(document: PDFDocument) -> CSS:
        """
        Build the @page CSS from the document options.

        Values in `options` are validated by `PDFOptions.validate()`,
        which MUST reject anything that is not a strict page size,
        orientation, or CSS length. Otherwise this is an injection vector.
        """
        options = document.options

        css = f"""
            @page {{
                size: {options.page_size} {options.orientation};

                margin-top: {options.margin_top};
                margin-right: {options.margin_right};
                margin-bottom: {options.margin_bottom};
                margin-left: {options.margin_left};
            }}
        """
        return CSS(string=css)

    # -------------------------------------------------------------------------
    # Base URL
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_base_url() -> str:
        """
        Return the base URL used to resolve relative asset paths
        inside templates (images, CSS).

        Prefers MEDIA_ROOT (user uploads). Falls back to BASE_DIR.
        """
        media_root = getattr(settings, "MEDIA_ROOT", None)
        if media_root:
            return Path(media_root).as_uri()
        return Path(settings.BASE_DIR).as_uri()



class PDFStorage:
    """
    Handles persistence of generated PDF files.
    """

    def __init__(self, storage: Storage | None = None) -> None:
        # Allow injecting a different storage backend (S3, GCS, in-memory test).
        self._storage = storage or default_storage

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def save(self, pdf_file: BytesIO, path: str) -> str:
        """
        Save the PDF file to the given storage path.

        Args:
            pdf_file: In-memory PDF buffer.
            path: Relative path inside the storage backend.

        Returns:
            The actual path returned by the storage backend
            (may differ if a name collision occurred).

        Raises:
            PDFStorageError: If the path is invalid or saving fails.
        """
        self._validate_path(path)

        try:
            pdf_file.seek(0)
            content = self._read_content(pdf_file)
            saved_path = self._storage.save(path, content)
            logger.info("PDF saved to storage: %s", saved_path)
            return saved_path  # noqa: TRY300

        except PDFStorageError:
            raise
        except Exception as exc:
            logger.exception("Failed to save PDF to storage: %s", path)
            msg = f"Unable to save PDF: {path}"
            raise PDFStorageError(msg) from exc

    def save_to_field(
        self,
        pdf_file: BytesIO,
        field,
        filename: str,
        *,
        save: bool = True,
    ) -> str:
        """
        Save the PDF file into a Django FileField.

        Args:
            pdf_file: In-memory PDF buffer.
            field: The Django FileField (or ImageField) to save into.
            filename: The filename to use in the field.
            save: If True (default), calls `field.save(..., save=True)`
                  which also saves the parent model.

        Returns:
            The name of the file stored in the field.

        Raises:
            PDFStorageError: If the filename is invalid or saving fails.
        """
        self._validate_filename(filename)

        try:
            pdf_file.seek(0)
            content = self._read_content(pdf_file)

            field.save(filename, content, save=save)
            logger.info("PDF saved to field: %s", field.name)
            return field.name  # noqa: TRY300

        except PDFStorageError:
            raise
        except Exception as exc:
            logger.exception("Failed to save PDF to field: %s", filename)
            msg = f"Unable to save PDF to field: {filename}"
            raise PDFStorageError(
                msg
            ) from exc

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _read_content(pdf_file: BytesIO) -> ContentFile:
        """
        Read the buffer and return a ContentFile, enforcing the size limit.
        """
        data = pdf_file.read()

        max_size = DEFAULT_MAX_PDF_SIZE
        if len(data) > max_size:
            msg = f"PDF exceeds maximum allowed size ({max_size} bytes)."
            raise PDFStorageError(
                msg
            )

        return ContentFile(data)

    @staticmethod
    def _validate_path(path: str) -> None:
        """Reject empty paths, traversal, and absolute paths."""
        if not path or not path.strip():
            msg = "Storage path cannot be empty."
            raise PDFStorageError(msg)

        normalized = PurePosixPath(path)

        if normalized.is_absolute():
            msg_0 = "Storage path must be relative."
            raise PDFStorageError(msg_0)

        if ".." in normalized.parts:
            msg_1 = "Storage path must not contain '..'."
            raise PDFStorageError(msg_1)

    @staticmethod
    def _validate_filename(filename: str) -> None:
        """Reject empty filenames, traversal, and unsafe characters."""
        if not filename or not filename.strip():
            msg = "Filename cannot be empty."
            raise PDFStorageError(msg)

        if "/" in filename or "\\" in filename:
            msg_0 = "Filename must not contain path separators."
            raise PDFStorageError(
                msg_0
            )

        if ".." in filename:
            msg_1 = "Filename must not contain relative path segments."
            raise PDFStorageError(
                msg_1
            )

        # Allow letters, digits, dot, dash, underscore only.
        if not re.match(r"^[A-Za-z0-9._-]+$", filename):
            msg_2 = "Filename contains invalid characters."
            raise PDFStorageError(
                msg_2
            )


class PDFMerger:
    """
    Merge multiple PDF documents into a single PDF.
    """

    def __init__(self, *, max_total_size: int = DEFAULT_MAX_TOTAL_SIZE) -> None:
        self._max_total_size = max_total_size

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def merge(self, pdf_files: Iterable[BinaryIO]) -> BytesIO:
        """
        Merge the given PDF buffers into a single in-memory PDF.

        Args:
            pdf_files: An iterable of file-like objects containing PDF data.
                       Each must support `.seek()` and `.read()`.

        Returns:
            A BytesIO positioned at 0, containing the merged PDF.

        Raises:
            PDFMergeError: If no input is provided, the total size exceeds
                           the configured limit, or merging fails.
        """
        files = list(pdf_files)

        if not files:
            msg = "At least one PDF file is required to merge."
            raise PDFMergeError(msg)

        total_size = 0
        page_count = 0

        try:
            with PdfWriter() as writer:
                for index, pdf_file in enumerate(files):
                    self._validate_pdf_file(pdf_file, index)

                    pdf_file.seek(0)
                    data = pdf_file.read()
                    total_size += len(data)

                    if total_size > self._max_total_size:
                        msg_0 = (
                            f"Total input size exceeds "
                            f"{self._max_total_size} bytes."
                        )
                        raise PDFMergeError(  # noqa: TRY301
                            msg_0
                        )

                    reader = PdfReader(BytesIO(data))
                    for page in reader.pages:
                        writer.add_page(page)
                        page_count += 1

                output = BytesIO()
                writer.write(output)
                output.seek(0)

            logger.info("Merged %d PDFs into %d pages", len(files), page_count)
            return output  # noqa: TRY300

        except PDFMergeError:
            # Domain exception — propagate as-is.
            raise
        except Exception as exc:
            logger.exception("Failed to merge PDF documents")
            msg_1 = "Unable to merge PDF documents."
            raise PDFMergeError(msg_1) from exc

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_pdf_file(pdf_file: BinaryIO, index: int) -> None:
        """Ensure the object is file-like and supports seek/read."""
        if not hasattr(pdf_file, "seek") or not hasattr(pdf_file, "read"):
            msg = f"Item at index {index} is not a file-like object."
            raise PDFMergeError(
                msg
            )


class PDFResponse:
    """
    Helper to build an HTTP response serving a PDF file.
    """

    @staticmethod
    def create(
        pdf_file: BytesIO | BinaryIO,
        *,
        filename: str,
        download: bool = True,
        as_attachment: bool | None = None,   # alias optionnel
    ) -> FileResponse:
        """
        Build a FileResponse serving the given PDF buffer.

        Args:
            pdf_file: A file-like object containing PDF data.
            filename: The filename shown to the user.
            download: If True, the browser downloads the file.
                      If False, it tries to display it inline.
            as_attachment: Alias for `download`. Takes precedence if set.

        Returns:
            A FileResponse configured for PDF delivery.
        """
        # Allow overriding download via as_attachment for readability.
        if as_attachment is not None:
            download = as_attachment

        # Ensure filename is safe.
        filename = PDFResponse._sanitize_filename(filename)

        # Rewind buffer to guarantee full content is served.
        try:
            pdf_file.seek(0)
        except (AttributeError, OSError):
            msg = "pdf_file must support seek(0)."
            raise ValueError(msg)  # noqa: B904

        return FileResponse(
            pdf_file,
            as_attachment=download,
            filename=filename,
            content_type="application/pdf",
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        Ensure the filename is safe and ends with .pdf.
        """
        name = (filename or "").strip()

        if not name:
            name = "document.pdf"

        # Reject path separators and traversal.
        if "/" in name or "\\" in name or ".." in name:
            msg = "Invalid filename: path separators are not allowed."
            raise ValueError(msg)

        # Reject any other unusual character.
        if not _FILENAME_RE.match(name):
            msg = "Invalid filename: only letters, digits, '.', '-', '_' are allowed."
            raise ValueError(
                msg
            )

        # Ensure .pdf extension.
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"

        return name


class PDFService:
    """
    Main facade for PDF generation and management.

    Provides a simple API on top of:
      - PDFDocument: describes the source and options
      - PDFRenderer: renders to PDF
      - PDFStorage: persists to disk or a model field
      - PDFMerger: merges multiple PDFs
      - PDFResponse: builds an HTTP response
    """

    # Instances are shared across calls. Override at subclass level if needed.
    renderer = PDFRenderer()
    storage = PDFStorage()
    merger = PDFMerger()

    # -------------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------------

    @classmethod
    def generate(
        cls,
        *,
        template: str | None = None,
        context: dict[str, Any] | None = None,
        html: str | None = None,
        url: str | None = None,
        options: PDFOptions | None = None,
    ) -> BinaryIO:
        """
        Render a PDF from template, html, or url.

        Returns:
            An in-memory file-like object positioned at 0.
        """
        document = PDFDocument(
            template=template,
            context=context or {},
            html=html,
            url=url,
            options=options or PDFOptions(),
        )
        return cls.renderer.render(document)

    # -------------------------------------------------------------------------
    # Generation + persistence
    # -------------------------------------------------------------------------

    @classmethod
    def generate_and_save(  # noqa: PLR0913
        cls,
        *,
        path: str,
        template: str | None = None,
        context: dict[str, Any] | None = None,
        html: str | None = None,
        url: str | None = None,
        options: PDFOptions | None = None,
    ) -> str:
        """
        Render a PDF and save it to storage.

        Args:
            path: Relative path inside the storage backend (required).

        Returns:
            The actual path where the file was saved.
        """
        if not path:
            msg = "`path` is required for generate_and_save."
            raise ValueError(msg)

        pdf_file = cls.generate(
            template=template,
            context=context,
            html=html,
            url=url,
            options=options,
        )
        return cls.storage.save(pdf_file, path)

    @classmethod
    def generate_and_save_to_field(  # noqa: PLR0913
        cls,
        *,
        field,
        filename: str,
        template: str | None = None,
        context: dict[str, Any] | None = None,
        html: str | None = None,
        url: str | None = None,
        options: PDFOptions | None = None,
    ):
        """
        Render a PDF and save it into a Django FileField.

        Returns the field after saving (so callers can access `field.name`).
        """
        pdf_file = cls.generate(
            template=template,
            context=context,
            html=html,
            url=url,
            options=options,
        )
        cls.storage.save_to_field(pdf_file, field, filename)
        return field

    # -------------------------------------------------------------------------
    # Merge
    # -------------------------------------------------------------------------

    @classmethod
    def merge(cls, pdf_files: Iterable[BinaryIO]) -> BinaryIO:
        """Merge multiple PDF buffers into a single in-memory PDF."""
        return cls.merger.merge(pdf_files)

    # -------------------------------------------------------------------------
    # HTTP response
    # -------------------------------------------------------------------------

    @classmethod
    def http_response(
        cls,
        pdf_file: BinaryIO,
        *,
        filename: str,
        download: bool = True,
    ) -> FileResponse:
        """Build a FileResponse serving the given PDF buffer."""
        return PDFResponse.create(
            pdf_file,
            filename=filename,
            download=download,
        )

    # -------------------------------------------------------------------------
    # Convenience: generate + respond in one call
    # -------------------------------------------------------------------------

    @classmethod
    def generate_response(  # noqa: PLR0913
        cls,
        *,
        filename: str,
        download: bool = True,
        template: str | None = None,
        context: dict[str, Any] | None = None,
        html: str | None = None,
        url: str | None = None,
        options: PDFOptions | None = None,
    ) -> FileResponse:
        """
        Generate a PDF and return a FileResponse ready to send.

        This is the most common pattern for views:
            return PDFService.generate_response(
                template="invoices/pdf.html",
                context={"invoice": invoice},
                filename=f"invoice-{invoice.pk}.pdf",
            )
        """
        pdf_file = cls.generate(
            template=template,
            context=context,
            html=html,
            url=url,
            options=options,
        )
        return cls.http_response(
            pdf_file,
            filename=filename,
            download=download,
        )
