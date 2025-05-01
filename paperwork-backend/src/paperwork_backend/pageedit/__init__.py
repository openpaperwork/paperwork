class AbstractPageEditorUI:
    CAPABILITY_SHOW_FRAME = (1 << 0)
    CAPABILITIES = 0

    def can(self, capability):
        return bool(self.CAPABILITIES & capability)

    def set_modifier_state(self, modifier_id, enabled):
        """
        Indicates if an modifier must be shown as enabled or disabled.
        """
        pass

    def show_preview(self, img):
        """
        Indicates the image to display, with all the changes applied from the
        modifiers already applied on it.

        Only called when the image changed.
        """
        return

    def show_frame_selector(self):
        """
        Tells the UI that it must let the user select a frame on the image
        (image provided by `show_image`). It also specify the current frame
        to display to the user.

        Called every time the image changes if we want the frame to be shown.

        Frame can be obtained by calling PageEditor.get_frame().get() and
        can be updated with PageEditor.get_frame().set().
        """
        return

    def hide_frame_selector(self):
        """
        Tells the UI to not let the user select a frame anymore.
        """
        return

    def on_edit_end(self, doc_url, page_idx):
        """
        Called when the user modifications have been applied or cancelled.
        """
        pass
