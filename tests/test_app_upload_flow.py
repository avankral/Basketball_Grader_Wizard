"""Tests for app upload flow guards."""

from src.app import should_process_upload


class TestUploadProcessingGuard:
    """Tests to prevent upload-triggered rerun loops."""

    def test_does_not_process_without_file(self) -> None:
        """No file means no processing even when button is clicked."""
        assert should_process_upload(uploaded_file=None, process_clicked=True) is False

    def test_does_not_process_without_click(self) -> None:
        """File present but no click should not process on rerun."""
        assert should_process_upload(uploaded_file=object(), process_clicked=False) is False

    def test_processes_only_with_file_and_click(self) -> None:
        """Processing should run only when both conditions are true."""
        assert should_process_upload(uploaded_file=object(), process_clicked=True) is True
