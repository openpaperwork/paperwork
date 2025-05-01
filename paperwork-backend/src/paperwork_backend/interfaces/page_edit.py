from typing import List
import abc


class AbstractPageEditorUI(abc.ABC):
    CAPABILITY_SHOW_FRAME = (1 << 0)
    CAPABILITIES = 0

    def can(self, capability):
        return bool(self.CAPABILITIES & capability)

    @abc.abstractmethod
    def set_modifier_state(self, modifier_id, enabled):
        """
        Indicates if an modifier must be shown as enabled or disabled.
        """
        ...

    @abc.abstractmethod
    def show_preview(self, img):
        """
        Indicates the image to display, with all the changes applied from the
        modifiers already applied on it.

        Only called when the image changed.
        """
        ...

    @abc.abstractmethod
    def show_frame_selector(self):
        """
        Tells the UI that it must let the user select a frame on the image
        (image provided by `show_image`). It also specify the current frame
        to display to the user.

        Called every time the image changes if we want the frame to be shown.

        Frame can be obtained by calling PageEditor.frame.get() and
        can be updated with PageEditor.frame.set().
        """
        ...

    @abc.abstractmethod
    def hide_frame_selector(self):
        """
        Tells the UI to not let the user select a frame anymore.
        """
        ...

    @abc.abstractmethod
    def on_edit_end(self, doc_url, page_idx):
        """
        Called when the user modifications have been applied or cancelled.
        """
        ...


class AbstractPageEditorFrame(abc.ABC):
    @abc.abstractmethod
    def get(self):
        ...

    @abc.abstractmethod
    def set(self, frame):
        ...


class AbstractPageEditorSession(abc.ABC):
    @abc.abstractmethod
    def get_frame(self) -> AbstractPageEditorFrame:
        ...

    @abc.abstractmethod
    def get_modifiers(self) -> List[dict]:
        ...

    @abc.abstractmethod
    def on_modifier_selected(self, modifier_id):
        ...

    @abc.abstractmethod
    def on_save(self):
        ...

    @abc.abstractmethod
    def on_cancel(self):
        ...


class PageEditorFactory(abc.ABC):
    @abc.abstractmethod
    def page_editor_session_get(
        self,
        doc_url,
        page_idx,
        page_editor_ui: AbstractPageEditorUI
    ) -> AbstractPageEditorSession:
        ...
