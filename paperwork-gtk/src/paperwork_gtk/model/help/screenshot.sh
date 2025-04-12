#!/bin/sh

set -e

# Explicitly set the revision of the test documents here, so we can figure out
# exactly which version of Paperwork was tied to which version of the test
# documents.
TEST_DOCS_TAG="2.1"

TMP_DIR="$(mktemp -d --suffix=paperwork)"
echo "Temporary directory: ${TMP_DIR}"

OUT_DIR="${PWD}/out"

mkdir -p "${TMP_DIR}/config"
mkdir -p "${TMP_DIR}/local"
mkdir -p "${TMP_DIR}/papers"

export XDG_CONFIG_HOME="${TMP_DIR}/config"
export XDG_DATA_HOME="${TMP_DIR}/local"
BASE_WORKDIR="${TMP_DIR}/papers"
WORKDIR="${BASE_WORKDIR}/paperwork-test-documents/papers"

cd "${BASE_WORKDIR}"
if [ -d "${PAPERWORK_TEST_DOCUMENTS}" ];
then
	rm -rf paperwork-test-documents
	echo "Copying test documents from ${PAPERWORK_TEST_DOCUMENTS} to $(readlink -f .)/paperwork-test-documents ..."
	cp -r --no-preserve=mode "${PAPERWORK_TEST_DOCUMENTS}" ./paperwork-test-documents
else
	echo "Downloading test documents to $(readlink -f .)/paperwork-test-documents ... If internet access is forbidden, set PAPERWORK_TEST_DOCUMENTS env var to the path to a pre-fetched copy."
	git clone --depth 1 --branch "${TEST_DOCS_TAG}" https://gitlab.gnome.org/World/OpenPaperwork/paperwork-test-documents.git
fi

echo "Updating Paperwork database ..."
paperwork-cli config put workdir str "file://${WORKDIR}"
paperwork-cli sync

echo "Making screenshots ..."
paperwork-gtk plugins add openpaperwork_gtk.interactive

paperwork-gtk << EOF
wait()
core.call_all("doc_open", "20990307_0000_00", "file://${WORKDIR}/20990307_0000_00")
core.call_all("search_set", "label:contrat conditions generales")
wait()

core.call_all("open_bug_report")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("close_bug_report")
core.call_all("mainwindow_focus")

core.call_all("gtk_show_shortcuts")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_hide_shortcuts")
core.call_all("mainwindow_focus")

core.call_all("gtk_open_layout_settings")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_close_layout_settings")
core.call_all("mainwindow_focus")

core.call_all("gtk_open_advanced_search_dialog")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_close_advanced_search_dialog")
core.call_all("mainwindow_focus")

core.call_all("gtk_open_settings")
wait()
core.call_all("settings_scroll_to_bottom")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("settings_scroll_to_top")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("display_calibration_screen")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("hide_calibration_screen")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("close_settings")
core.call_all("mainwindow_focus")
core.call_all("open_doc_properties", "20990307_0000_00", "file://${WORKDIR}/20990307_0000_00")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("docproperties_scroll_to_last")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("mainwindow_show_default", side="left")
wait()
core.call_all("screenshot_snap_all_doc_widgets", "file://${OUT_DIR}")

core.call_all("gtk_open_app_menu")
wait()
core.call_all("screenshot_snap_app_menu", "file://${OUT_DIR}/app_menu_opened.png")

core.call_all("page_menu_open")
wait()
core.call_all("screenshot_snap_page_action_menu", "file://${OUT_DIR}/page_menu_opened.png")

core.call_all("doc_menu_open")
wait()
core.call_all("screenshot_snap_doc_action_menu", "file://${OUT_DIR}/doc_menu_opened.png")
EOF

set +e
echo "Cleaning up the mess ..."
sleep 5
rm -rf "${TMP_DIR}"
echo "All done !"
