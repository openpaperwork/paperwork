import abc


class BugReportAttachment(abc.ABC):
    @abc.abstractmethod
    def bug_report_get_attachments(self, out: dict):
        ...


class BugReportAttachmentFileUrl(abc.ABC):
    @abc.abstractmethod
    def bug_report_get_attachment_file_url(attachment_id, *args):
        ...


class BugReportAttachmentUpdate(abc.ABC):
    @abc.abstractmethod
    def bug_report_update_attachment(self, attachment_id, infos: dict, *args):
        ...


class BugReportAttachmentSelectionListener(abc.ABC):
    @abc.abstractmethod
    def on_bug_report_attachment_selected(self, attachment_id, *args):
        ...

    @abc.abstractmethod
    def on_bug_report_attachment_unselected(self, attachment_id, *args):
        ...
