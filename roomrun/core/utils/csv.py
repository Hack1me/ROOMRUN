from __future__ import annotations

import csv
import logging
import re
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from io import BytesIO
from io import StringIO
from pathlib import PurePosixPath
from typing import Any
from typing import BinaryIO

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.core.files.storage import default_storage
from django.http import FileResponse
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# Maximum allowed CSV size (bytes).
DEFAULT_MAX_CSV_SIZE = 50 * 1024 * 1024  # 50 MB

# Allowed characters for filenames.
_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class CSVError(Exception):
    """Base exception for CSV services."""


class CSVGenerationError(CSVError):
    """Raised when CSV generation fails."""


class CSVStorageError(CSVError):
    """Raised when CSV storage fails."""


class CSVConfigurationError(CSVError):
    """Raised when CSV configuration is invalid."""



# Valid CSV quoting modes (from the stdlib).
VALID_QUOTING_MODES = {
    csv.QUOTE_MINIMAL,
    csv.QUOTE_ALL,
    csv.QUOTE_NONNUMERIC,
    csv.QUOTE_NONE,
}


@dataclass(slots=True)
class CSVOptions:
    """
    Configuration used to generate CSV files.
    """

    delimiter: str = ","
    quotechar: str = '"'
    quoting: int = csv.QUOTE_MINIMAL

    encoding: str = "utf-8-sig"

    lineterminator: str = "\r\n"

    filename: str = "export.csv"

    metadata: dict[str, Any] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def filename_without_extension(self) -> str:
        """Return the filename without the `.csv` extension."""
        return self.filename.removesuffix(".csv")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate the options.

        Raises:
            CSVConfigurationError: If any option is invalid.
        """
        self._validate_delimiter()
        self._validate_quotechar()
        self._validate_quoting()
        self._validate_encoding()
        self._validate_lineterminator()
        self._validate_filename()

    def _validate_delimiter(self) -> None:
        if len(self.delimiter) != 1:
            msg = _("CSV delimiter must contain exactly one character.")
            raise CSVConfigurationError(
                msg
            )

    def _validate_quotechar(self) -> None:
        if len(self.quotechar) != 1:
            msg = _("CSV quotechar must contain exactly one character.")
            raise CSVConfigurationError(
                msg
            )

    def _validate_quoting(self) -> None:
        if self.quoting not in VALID_QUOTING_MODES:
            msg = (
                _("Invalid quoting mode: %(quoting)s. Must be one of csv.QUOTE_* constants.")  # noqa: E501
                % {"quoting": self.quoting}
            )
            raise CSVConfigurationError(
                msg
            )

    def _validate_encoding(self) -> None:
        if not self.encoding:
            msg = _("Encoding cannot be empty.")
            raise CSVConfigurationError(msg)

        # Try to look up the codec to catch typos early.
        try:
            "".encode(self.encoding)
        except LookupError:
            msg_0 = _("Unknown encoding: %(encoding)s") % {"encoding": self.encoding}
            raise CSVConfigurationError(
                msg_0
            ) from None

    def _validate_lineterminator(self) -> None:
        if not self.lineterminator:
            msg = _("Line terminator cannot be empty.")
            raise CSVConfigurationError(msg)

    def _validate_filename(self) -> None:
        name = self.filename.strip()

        if not name:
            msg = _("Filename cannot be empty.")
            raise CSVConfigurationError(msg)

        if "/" in name or "\\" in name:
            msg_0 = _("Filename must not contain path separators.")
            raise CSVConfigurationError(
                msg_0
            )

        if ".." in name:
            msg_1 = _("Filename must not contain relative path segments.")
            raise CSVConfigurationError(
                msg_1
            )

        if not name.lower().endswith(".csv"):
            msg_2 = _("Filename must end with '.csv'.")
            raise CSVConfigurationError(
                msg_2
            )

    # -------------------------------------------------------------------------
    # Normalization (explicit, opt-in)
    # -------------------------------------------------------------------------

    def normalize_filename(self) -> None:
        """
        Ensure the filename ends with `.csv` (mutates self).

        Call this explicitly if you want normalization, not validation.
        """
        if not self.filename.lower().endswith(".csv"):
            self.filename = f"{self.filename}.csv"


@dataclass(slots=True)
class CSVDocument:
    """
    Represents a CSV document before rendering.

    Rows can be provided as:
      - Sequences:  [["Alice", 30], ["Bob", 25]]
      - Mappings:   [{"name": "Alice", "age": 30}, ...]

    When using mappings, keys must match the declared headers.
    """

    headers: list[str] = field(default_factory=list)
    rows: Iterable[Sequence[Any] | Mapping[str, Any]] = field(default_factory=list)
    options: CSVOptions = field(default_factory=CSVOptions)

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def row_count(self) -> int:
        """
        Return the number of rows.

        Forces evaluation of the iterable (converts to list).
        """
        if not isinstance(self.rows, list):
            self.rows = list(self.rows)
        return len(self.rows)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate the document.

        Raises:
            CSVConfigurationError: If headers, rows, or options are invalid.
        """
        self._validate_headers()
        self._validate_rows()
        self.options.validate()

    def _validate_headers(self) -> None:
        if not self.headers:
            msg = _("CSV document requires at least one header.")
            raise CSVConfigurationError(
                msg
            )

        if len(set(self.headers)) != len(self.headers):
            msg = _("CSV headers must be unique.")
            raise CSVConfigurationError(
                msg
            )

        if any(not h or not str(h).strip() for h in self.headers):
            msg = _("CSV headers cannot be empty.")
            raise CSVConfigurationError(
                msg
            )

    def _validate_rows(self) -> None:
        # Evaluate the iterable once so we can iterate safely.
        if not isinstance(self.rows, list):
            self.rows = list(self.rows)

        expected = len(self.headers)

        for index, row in enumerate(self.rows):
            if isinstance(row, Mapping):
                self._validate_mapping_row(row, index)
            elif isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
                self._validate_sequence_row(row, expected, index)
            else:
                msg = (
                    _("Row %(index)s has unsupported type (%(type_name)s). Expected a sequence or mapping.")  # noqa: E501
                    % {"index": index, "type_name": type(row).__name__}
                )
                raise CSVConfigurationError(
                    msg
                )

    def _validate_mapping_row(self, row: Mapping[str, Any], index: int) -> None:
        row_keys = set(row.keys())
        expected_keys = set(self.headers)

        if row_keys != expected_keys:
            missing = expected_keys - row_keys
            extra = row_keys - expected_keys
            parts = []
            if missing:
                parts.append(_("missing keys: %(keys)s") % {"keys": ", ".join(sorted(missing))})  # noqa: E501
            if extra:
                parts.append(_("unexpected keys: %(keys)s") % {"keys": ", ".join(sorted(extra))})  # noqa: E501
            msg = _("Row %(index)s keys do not match headers (%(parts)s).") % {
                "index": index,
                "parts": ", ".join(parts),
            }
            raise CSVConfigurationError(
                msg
            )

    def _validate_sequence_row(
        self,
        row: Sequence[Any],
        expected: int,
        index: int,
    ) -> None:
        if len(row) != expected:
            msg = (
                _("Row %(index)s has %(row_count)s values, but %(expected)s headers were declared.")  # noqa: E501
                % {"index": index, "row_count": len(row), "expected": expected}
            )
            raise CSVConfigurationError(
                msg
            )


class CSVRenderer:
    """
    Converts CSV documents into CSV files (in-memory).

    Supports rows as sequences (positional) or mappings (keyed by header).
    """

    def render(self, document: CSVDocument) -> BytesIO:
        """
        Render the given CSVDocument into an in-memory CSV file.

        Args:
            document: The document to render.

        Returns:
            A BytesIO positioned at 0 containing the encoded CSV.

        Raises:
            CSVGenerationError: If rendering fails.
        """
        document.validate()

        try:
            buffer = StringIO(newline="")
            writer = csv.writer(
                buffer,
                delimiter=document.options.delimiter,
                quotechar=document.options.quotechar,
                quoting=document.options.quoting,
                lineterminator=document.options.lineterminator,
            )

            # Write the header row.
            writer.writerow(document.headers)

            # Write each data row, normalizing to a list of strings.
            for index, row in enumerate(document.rows):
                try:
                    writer.writerow(
                        self._normalize_row(row, document.headers)
                    )
                except Exception as exc:
                    msg = _("Failed to render row %(index)s.") % {"index": index}
                    raise CSVGenerationError(
                        msg
                    ) from exc

            content = buffer.getvalue()
            output = BytesIO(content.encode(document.options.encoding))
            output.seek(0)

            logger.info(
                "CSV rendered | rows=%d | encoding=%s",
                len(document.rows) if isinstance(document.rows, list) else -1,
                document.options.encoding,
            )

        except CSVGenerationError:
            raise
        except Exception as exc:
            logger.exception("CSV generation failed")
            msg = _("Unable to generate CSV file.")
            raise CSVGenerationError(
                msg
            ) from exc
        else:
            return output

    # -------------------------------------------------------------------------
    # Row normalization
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_row(
        row: Sequence[Any] | Mapping[str, Any],
        headers: list[str],
    ) -> list[str]:
        """
        Convert a row (sequence or mapping) into a list of string values
        in the exact order of the headers.

        Mapping rows are reordered to match `headers`.
        None values become empty strings.
        """
        if isinstance(row, Mapping):
            values = [row.get(header) for header in headers]
        else:
            values = list(row)

        return [CSVRenderer._stringify(value) for value in values]

    @staticmethod
    def _stringify(value: Any) -> str:
        """Convert a value to a CSV-safe string."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)


class CSVStorage:
    """
    Handles persistence of generated CSV files.
    """

    def __init__(self, storage: Storage | None = None) -> None:
        # Allow injecting a different storage backend for tests.
        self._storage = storage or default_storage

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def save(self, csv_file: BytesIO, path: str) -> str:
        """
        Save the CSV file to the given storage path.

        Args:
            csv_file: In-memory CSV buffer.
            path: Relative path inside the storage backend.

        Returns:
            The actual path returned by the storage backend
            (may differ if a name collision occurred).

        Raises:
            CSVStorageError: If the path is invalid or saving fails.
        """
        self._validate_path(path)

        try:
            csv_file.seek(0)
            content = self._read_content(csv_file)
            saved_path = self._storage.save(path, content)

        except CSVStorageError:
            raise
        except Exception as exc:
            logger.exception("Failed to save CSV: %s", path)
            msg = _("Unable to save CSV: %(path)s") % {"path": path}
            raise CSVStorageError(msg) from exc
        else:
            logger.info("CSV saved to storage: %s", saved_path)
            return saved_path

    def save_to_field(
        self,
        csv_file: BytesIO,
        field,
        filename: str,
        *,
        save: bool = True,
    ) -> str:
        """
        Save the CSV file into a Django FileField.

        Args:
            csv_file: In-memory CSV buffer.
            field: The Django FileField to save into.
            filename: The filename to use in the field.
            save: If True, calls `field.save(..., save=True)` which also
                  saves the parent model.

        Returns:
            The name of the file stored in the field.

        Raises:
            CSVStorageError: If the filename is invalid or saving fails.
        """
        self._validate_filename(filename)

        try:
            csv_file.seek(0)
            content = self._read_content(csv_file)

            field.save(filename, content, save=save)

        except CSVStorageError:
            raise
        except Exception as exc:
            logger.exception("Failed to save CSV to field: %s", filename)
            msg = _("Unable to save CSV to field: %(filename)s") % {"filename": filename}  # noqa: E501
            raise CSVStorageError(
                msg
            ) from exc
        else:
            logger.info("CSV saved to field: %s", field.name)
            return field.name

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _read_content(csv_file: BytesIO) -> ContentFile:
        """Read the buffer and enforce the size limit."""
        data = csv_file.read()

        if len(data) > DEFAULT_MAX_CSV_SIZE:
            msg = (
                _("CSV exceeds maximum allowed size (%(max_size)s bytes).")
                % {"max_size": DEFAULT_MAX_CSV_SIZE}
            )
            raise CSVStorageError(
                msg
            )

        return ContentFile(data)

    @staticmethod
    def _validate_path(path: str) -> None:
        """Reject empty paths, traversal, and absolute paths."""
        if not path or not path.strip():
            msg = _("Storage path cannot be empty.")
            raise CSVStorageError(msg)

        normalized = PurePosixPath(path)

        if normalized.is_absolute():
            msg_0 = _("Storage path must be relative.")
            raise CSVStorageError(msg_0)

        if ".." in normalized.parts:
            msg_1 = _("Storage path must not contain '..'.")
            raise CSVStorageError(msg_1)

    @staticmethod
    def _validate_filename(filename: str) -> None:
        """Reject empty filenames, traversal, and unsafe characters."""
        if not filename or not filename.strip():
            msg = _("Filename cannot be empty.")
            raise CSVStorageError(msg)

        if "/" in filename or "\\" in filename:
            msg_0 = _("Filename must not contain path separators.")
            raise CSVStorageError(
                msg_0
            )

        if ".." in filename:
            msg_1 = _("Filename must not contain relative path segments.")
            raise CSVStorageError(
                msg_1
            )

        if not _FILENAME_RE.match(filename):
            msg_2 = _("Filename contains invalid characters.")
            raise CSVStorageError(
                msg_2
            )


class CSVResponse:
    """
    Helper to build an HTTP response serving a CSV file.
    """

    @staticmethod
    def create(
        csv_file: BytesIO | BinaryIO,
        *,
        filename: str,
        download: bool = True,
        as_attachment: bool | None = None,   # alias optionnel
    ) -> FileResponse:
        """
        Build a FileResponse serving the given CSV buffer.

        Args:
            csv_file: A file-like object containing CSV data.
            filename: The filename shown to the user.
            download: If True, the browser downloads the file.
                      If False, it tries to display it inline.
            as_attachment: Alias for `download`. Takes precedence if set.

        Returns:
            A FileResponse configured for CSV delivery.
        """
        # Allow overriding download via as_attachment for readability.
        if as_attachment is not None:
            download = as_attachment

        # Ensure filename is safe and ends with .csv.
        filename = CSVResponse._sanitize_filename(filename)

        # Rewind buffer to guarantee full content is served.
        try:
            csv_file.seek(0)
        except (AttributeError, OSError) as err:
            msg = _("csv_file must support seek(0).")
            raise ValueError(msg) from err

        return FileResponse(
            csv_file,
            as_attachment=download,
            filename=filename,
            content_type="text/csv; charset=utf-8",
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Ensure the filename is safe and ends with .csv."""
        name = (filename or "").strip()

        if not name:
            name = "export.csv"

        # Reject path separators and traversal.
        if "/" in name or "\\" in name or ".." in name:
            raise ValueError(
                _("Invalid filename: path separators are not allowed.")
            )

        # Reject any other unusual character.
        if not _FILENAME_RE.match(name):
            raise ValueError(
                _("Invalid filename: only letters, digits, '.', '-', '_' are allowed.")
            )

        # Ensure .csv extension.
        if not name.lower().endswith(".csv"):
            name = f"{name}.csv"

        return name


class CSVService:
    """
    Main facade for CSV generation and management.

    Provides a simple API on top of:
      - CSVDocument: describes headers, rows, and options
      - CSVRenderer: renders to CSV
      - CSVStorage: persists to disk or a model field
      - CSVResponse: builds an HTTP response
    """

    # Instances are shared across calls.
    renderer: CSVRenderer = CSVRenderer()
    storage: CSVStorage = CSVStorage()

    # -------------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------------

    @classmethod
    def generate(
        cls,
        *,
        headers: Sequence[str],
        rows: Iterable[Sequence[Any] | Mapping[str, Any]],
        options: CSVOptions | None = None,
    ) -> BinaryIO:
        """
        Render a CSV from headers + rows.

        Returns:
            An in-memory file-like object positioned at 0.
        """
        document = CSVDocument(
            headers=list(headers),
            rows=rows,
            options=options or CSVOptions(),
        )
        return cls.renderer.render(document)

    # -------------------------------------------------------------------------
    # Generation + persistence
    # -------------------------------------------------------------------------

    @classmethod
    def generate_and_save(
        cls,
        *,
        path: str,
        headers: Sequence[str],
        rows: Iterable[Sequence[Any] | Mapping[str, Any]],
        options: CSVOptions | None = None,
    ) -> str:
        """
        Render a CSV and save it to storage.

        Args:
            path: Relative path inside the storage backend (required).

        Returns:
            The actual path where the file was saved.
        """
        csv_file = cls.generate(
            headers=headers,
            rows=rows,
            options=options,
        )
        return cls.storage.save(csv_file, path)

    @classmethod
    def generate_and_save_to_field(
        cls,
        *,
        field,
        filename: str,
        headers: Sequence[str],
        rows: Iterable[Sequence[Any] | Mapping[str, Any]],
        options: CSVOptions | None = None,
    ):
        """
        Render a CSV and save it into a Django FileField.

        Returns the field after saving.
        """
        csv_file = cls.generate(
            headers=headers,
            rows=rows,
            options=options,
        )
        cls.storage.save_to_field(csv_file, field, filename)
        return field

    # -------------------------------------------------------------------------
    # HTTP response
    # -------------------------------------------------------------------------

    @classmethod
    def http_response(
        cls,
        csv_file: BinaryIO,
        *,
        filename: str,
        download: bool = True,
    ) -> FileResponse:
        """Build a FileResponse serving the given CSV buffer."""
        return CSVResponse.create(
            csv_file,
            filename=filename,
            download=download,
        )

    # -------------------------------------------------------------------------
    # Convenience: generate + respond in one call
    # -------------------------------------------------------------------------

    @classmethod
    def generate_response(
        cls,
        *,
        filename: str,
        headers: Sequence[str],
        rows: Iterable[Sequence[Any] | Mapping[str, Any]],
        options: CSVOptions | None = None,
        download: bool = True,
    ) -> FileResponse:
        """
        Generate a CSV and return a FileResponse ready to send.

        This is the most common pattern for views:
            return CSVService.generate_response(
                headers=["name", "email"],
                rows=[["Alice", "alice@x.com"]],
                filename="users.csv",
            )
        """
        csv_file = cls.generate(
            headers=headers,
            rows=rows,
            options=options,
        )
        return cls.http_response(
            csv_file,
            filename=filename,
            download=download,
        )
