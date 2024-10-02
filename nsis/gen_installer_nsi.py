#!/usr/bin/env python
# -*- coding: utf-8 -*-

# TODO(Jflesch): PEP8 ...
# flake8: noqa

import pycountry
import re
import sys


DEFAULT_DOWNLOAD_URI = (
    "https://download.openpaper.work/windows/amd64/paperwork-master-latest.zip"
)

ALL_LANGUAGES = [
    "eng",  # English (always first)

    "afr",
    "amh",
    "ara",
    "asm",
    "aze",
    {"lower": "aze_cyrl", "upper": "AZECYRL", "long": "Azerbaijani - Cyrilic"},
    "bel",
    "ben",
    "bod",  # Tibetan
    "bos",
    "bre",
    "bul",
    "cat",
    "ceb",
    "ces",  # Czech
    {"lower": "chi_sim", "upper": "CHISIM", "long": "Chinese (simplified)"},
    {
        "lower": "chi_sim_vert",
        "upper": "CHISIMVERT",
        "long": "Chinese (simplified, vertical)"
    },
    {"lower": "chi_tra", "upper": "CHITRA", "long": "Chinese (traditional)"},
    {
        "lower": "chi_tra_vert",
        "upper": "CHITRAVERT",
        "long": "Chinese (traditional, vertical)"
    },
    "chr",
    "cos",
    "cym",  # Welsh
    "dan",
    "deu",  # German
    "div",
    "dzo",
    {"lower": "ell", "upper": "ELL", "long": "Greek (modern)"},
    "enm",
    "epo",  # Esperanto
    "est",
    "eus",  # Basque
    "fao",
    {"lower": "fas", "upper": "FAS", "long": "Persian"},
    "fil",
    "fin",
    "fra",  # French
    "frk",  # Frankish
    "frm",
    "fry",
    "gla",
    "gle",  # Irish
    "glg",
    {"lower": "grc", "upper": "GRC", "long": "Greek (ancient)"},
    "guj",
    "hat",
    "heb",
    "hin",
    "hrv",  # Croatian
    "hun",
    "hye",
    "iku",  # Inuktitut
    "ind",
    "isl",  # Icelandic
    "ita",
    {"lower": "ita_old", "upper": "ITAOLD", "long": "Italian (old)"},
    "jav",
    "jpn",  # Japanese
    "kan",
    "kat",  # Georgian
    "khm",
    "kir",
    "kor",
    "lao",
    "lat",
    "lav",
    "lit",
    "ltz",
    "mal",
    "mar",
    "mkd",  # Macedonian
    "mlt",  # Maltese
    "mon",
    "mri",
    "msa",  # Malay
    "mya",  # Burmese
    "nep",
    "nld",  # Dutch
    "nor",
    "oci",
    "ori",
    "pan",
    "pol",
    "por",
    "pus",
    "que",
    {"lower": "ron", "upper": "RON", "long": "Romanian"},
    "rus",
    "san",
    "sin",
    "slk",
    "slv",
    "spa",  # Spanish
    "sqi",  # Albanian
    "srp",  # Serbian
    {"lower": "srp_latn", "upper": "SRPLATN", "long": "Serbian (Latin)"},
    "swa",
    "swe",
    "syr",
    "tam",
    "tat",
    "tel",
    "tgk",  # Tajik
    {"lower": "tha", "upper": "THA", "long": "Thai"},
    "tir",
    "ton",
    "tur",
    "uig",
    "ukr",
    "urd",
    "uzb",
    {"lower": "uzb_cyrl", "upper": "UZBCYRL", "long": "Uzbek - Cyrilic"},
    "vie",
    "yid",
    "yor",
 ]

UNKNOWN_LANGUAGE = {
    'download_section': """
        Section /o "{long}" SEC_{upper}
            inetc::get "https://download.openpaper.work/tesseract/4.0.0/tessdata/{lower}.traineddata" "$INSTDIR\\Data\\Tessdata\\{lower}.traineddata" /END
            Pop $0
            StrCmp $0 "OK" +3
                MessageBox MB_OK "Download of {lower}.traineddata failed: $0"
                Quit
        SectionEnd
""",
    'lang_strings': """
LangString DESC_SEC_{upper} ${{LANG_ENGLISH}} "Data files required to run OCR on {long} documents"
LangString DESC_SEC_{upper} ${{LANG_FRENCH}} "Data files required to run OCR on {long} documents"
LangString DESC_SEC_{upper} ${{LANG_GERMAN}} "Data files required to run OCR on {long} documents"
""",
}

KNOWN_LANGUAGES = {
    'deu': {
        "download_section": """
        Section /o "German / Deutsch" SEC_DEU
          inetc::get "https://download.openpaper.work/tesseract/4.0.0/tessdata/{lower}.traineddata" "$INSTDIR\\Data\\Tessdata\\{lower}.traineddata" /END
          Pop $0
          StrCmp $0 "OK" +3
        MessageBox MB_OK "Download of {lower}.traineddata failed: $0"
             Quit
        SectionEnd
""",
        "lang_strings": """
LangString DESC_SEC_DEU ${{LANG_ENGLISH}} "Data files required to run OCR on German documents"
LangString DESC_SEC_DEU ${{LANG_FRENCH}} "Fichiers requis pour la reconnaissance de caractères sur les documents en allemand"
LangString DESC_SEC_DEU ${{LANG_GERMAN}} "Data files required to run OCR on German documents" ; TODO
""",
    },
    'eng': {
        "download_section": """
        Section "English / English" SEC_ENG
            SectionIn RO ; Mandatory section

            inetc::get "https://download.openpaper.work/tesseract/4.0.0/tessdata_eng_4_0_0.zip" "$PLUGINSDIR\\tess_eng.zip" /END
            Pop $0
            StrCmp $0 "OK" +3
                MessageBox MB_OK "Download of {lower}.traineddata failed: $0"
                Quit
            nsisunz::UnzipToLog "$PLUGINSDIR\\tess_eng.zip" "$INSTDIR\\Data\\Tessdata"
        SectionEnd
""",
        "lang_strings": """
LangString DESC_SEC_ENG ${{LANG_ENGLISH}} "Data files required to run OCR on English documents"
LangString DESC_SEC_ENG ${{LANG_FRENCH}} "Fichiers requis pour la reconnaissance de caractères sur les documents en anglais"
LangString DESC_SEC_ENG ${{LANG_GERMAN}} "Data files required to run OCR on English documents" ; TODO
""",
    },
    'fra': {
        "download_section": """
        Section /o "French / Français" SEC_FRA
            inetc::get "https://download.openpaper.work/tesseract/4.0.0/tessdata/{lower}.traineddata" "$INSTDIR\\Data\\Tessdata\\{lower}.traineddata" /END
            Pop $0
            StrCmp $0 "OK" +3
                MessageBox MB_OK "Download of {lower}.traineddata failed: $0"
                Quit
        SectionEnd
""",
        "lang_strings": """
LangString DESC_SEC_FRA ${{LANG_ENGLISH}} "Data files required to run OCR on French documents"
LangString DESC_SEC_FRA ${{LANG_FRENCH}} "Fichiers requis pour la reconnaissance de caractères sur les documents en français"
LangString DESC_SEC_FRA ${{LANG_GERMAN}} "Data files required to run OCR on French documents" ; TODO
""",
    },
}

VERSION = """
!define PRODUCT_VERSION "{version}"
!define PRODUCT_SHORT_VERSION "{short_version}"
!define PRODUCT_DOWNLOAD_URI "{download_uri}"
"""

HEADER = """
!define PRODUCT_NAME "Paperwork"
!define PRODUCT_PUBLISHER "Openpaper.work"
!define PRODUCT_WEB_SITE "https://openpaper.work"
!define PRODUCT_UNINST_KEY "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

!addplugindir ".\dll"

!include x64.nsh


; MUI 1.67 compatible ------
!include "MUI.nsh"

!include "Sections.nsh"
!include "LogicLib.nsh"

; MUI Settings
!define MUI_ABORTWARNING
!define MUI_ICON "data\\paperwork_64.ico"
!define MUI_UNICON "data\\paperwork_64.ico"

; Language Selection Dialog Settings
!define MUI_LANGDLL_REGISTRY_ROOT "${PRODUCT_UNINST_ROOT_KEY}"
!define MUI_LANGDLL_REGISTRY_KEY "${PRODUCT_UNINST_KEY}"
!define MUI_LANGDLL_REGISTRY_VALUENAME "NSIS:Language"

; Welcome page
!insertmacro MUI_PAGE_WELCOME
; License page
!insertmacro MUI_PAGE_LICENSE "data\\licences.txt"
; Components page
!insertmacro MUI_PAGE_COMPONENTS
; Directory page
!insertmacro MUI_PAGE_DIRECTORY
; Instfiles page
!insertmacro MUI_PAGE_INSTFILES
; Finish page
!insertmacro MUI_PAGE_FINISH

; Uninstaller pages
!insertmacro MUI_UNPAGE_INSTFILES

; Language files
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"

; MUI end ------

Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "paperwork_installer.exe"
InstallDir "$PROGRAMFILES64\\Paperwork"
ShowInstDetails hide
ShowUnInstDetails hide
BrandingText "OpenPaper.work"


Section "Paperwork" SEC_PAPERWORK
  SectionIn RO ; Mandatory section

  SetOutPath "$INSTDIR"
  SetOverwrite on

  inetc::get "${PRODUCT_DOWNLOAD_URI}" "$PLUGINSDIR\\paperwork.zip" /END
  Pop $0
  StrCmp $0 "OK" +3
    MessageBox MB_OK "Download of ${PRODUCT_DOWNLOAD_URI} failed: $0"
    Quit

  inetc::get "https://download.openpaper.work/tesseract/4.0.0/tesseract_4_0_0.zip" "$PLUGINSDIR\\tesseract.zip" /END
  Pop $0
  StrCmp $0 "OK" +3
  MessageBox MB_OK "Download failed: $0"
    Quit

  inetc::get "https://download.openpaper.work/tesseract/4.0.0/tessconfig_4_0_0.zip" "$PLUGINSDIR\\tessconfig.zip" /END
  Pop $0
  StrCmp $0 "OK" +3
  MessageBox MB_OK "Download failed: $0"
    Quit

  CreateDirectory "$INSTDIR"
  nsisunz::UnzipToLog "$PLUGINSDIR\\paperwork.zip" "$INSTDIR"

  ; CreateShortCut "$DESKTOP.lnk" "$INSTDIR\\paperwork.exe"
  ; CreateShortCut "$STARTMENU.lnk" "$INSTDIR\\paperwork.exe"

  SetOutPath "$INSTDIR\\Tesseract"
  CreateDirectory "$INSTDIR\\Tesseract"
  nsisunz::UnzipToLog "$PLUGINSDIR\\tesseract.zip" "$INSTDIR"

  SetOutPath "$INSTDIR\\Data\\Tessdata"
  CreateDirectory "$INSTDIR\\Data\\Tessdata"
  nsisunz::UnzipToLog "$PLUGINSDIR\\tessconfig.zip" "$INSTDIR\\Data\\Tessdata"

  RMDir /r "$PROFILE\\.local"
SectionEnd

Section "Desktop icon" SEC_DESKTOP_ICON
  CreateShortCut "$DESKTOP\\Paperwork.lnk" "$INSTDIR\\paperwork.exe" "" "$INSTDIR\\Data\\paperwork_64.ico" 0 SW_SHOWNORMAL "" "Paperwork"
SectionEnd
"""

MIDDLE = """

!macro SecSelect SecId
  Push $0
  SectionSetFlags ${SecId} ${SF_SELECTED}
  SectionSetInstTypes ${SecId} 1
  Pop $0
!macroend

!define SelectSection '!insertmacro SecSelect'

Function .onInit
  InitPluginsDir
  !insertmacro MUI_LANGDLL_DISPLAY

  StrCmp $LANGUAGE ${LANG_FRENCH} french maybegerman
french:
    ${SelectSection} ${SEC_FRA}
    Goto end

maybegerman:
  StrCmp $LANGUAGE ${LANG_GERMAN} german end
german:
    ${SelectSection} ${SEC_DEU}
end:
FunctionEnd

Section -AdditionalIcons
  SetOutPath $INSTDIR
  WriteIniStr "$INSTDIR\${PRODUCT_NAME}.url" "InternetShortcut" "URL" "${PRODUCT_WEB_SITE}"
  CreateDirectory "$SMPROGRAMS\\Paperwork"
  CreateShortCut "$SMPROGRAMS\\Paperwork\\Paperwork.lnk" "$INSTDIR\\paperwork.exe" "" "$INSTDIR\\Data\\paperwork_64.ico" 0 SW_SHOWNORMAL "" "Paperwork"
  CreateShortCut "$SMPROGRAMS\\Paperwork\\Website.lnk" "$INSTDIR\\${PRODUCT_NAME}.url"
  CreateShortCut "$SMPROGRAMS\\Paperwork\\Uninstall.lnk" "$INSTDIR\\uninst.exe"
SectionEnd

Section -Post
  WriteUninstaller "$INSTDIR\\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayName" "$(^Name)"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\\uninst.exe"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
SectionEnd

LangString DESC_SEC_PAPERWORK ${LANG_ENGLISH} "Paperwork and all the required libriaires (Tesseract, GTK, etc)"
LangString DESC_SEC_PAPERWORK ${LANG_FRENCH} "Paperwork et toutes les librairies requises (Tesseract, GTK, etc)"
LangString DESC_SEC_PAPERWORK ${LANG_GERMAN} "Paperwork and all the required libriaires (Tesseract, GTK, etc)" ; TODO

LangString DESC_SEC_OCR_FILES ${LANG_ENGLISH} "Data files required to run OCR"
LangString DESC_SEC_OCR_FILES ${LANG_FRENCH} "Fichiers de données nécessaires pour la reconnaissance de caractères"
LangString DESC_SEC_OCR_FILES ${LANG_GERMAN} "Data files required to run OCR" ; TODO
"""


FOOTER = """
LangString DESC_SEC_DESKTOP_ICON ${LANG_ENGLISH} "Icon on the desktop to launch Paperwork"
LangString DESC_SEC_DESKTOP_ICON ${LANG_FRENCH} "Icône sur le bureau pour lancer Paperwork"
LangString DESC_SEC_DESKTOP_ICON ${LANG_GERMAN} "Icon on the desktop to launch Paperwork" ; TODO

Function un.onUninstSuccess
  HideWindow
  MessageBox MB_ICONINFORMATION|MB_OK "$(^Name) has been deleted successfully"
FunctionEnd

Function un.onInit
!insertmacro MUI_UNGETLANGUAGE
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to uninstall $(^Name) ? (your documents won't be deleted)" IDYES +2
  Abort
FunctionEnd

Section Uninstall
  Delete "$SMPROGRAMS\\Paperwork\\Paperwork.lnk"
  Delete "$SMPROGRAMS\\Paperwork\\Uninstall.lnk"
  Delete "$SMPROGRAMS\\Paperwork\\Website.lnk"
  Delete "$DESKTOP\\Paperwork.lnk"
  ; Delete "$STARTMENU.lnk"
  ; Delete "$DESKTOP.lnk"

  RMDir /r "$INSTDIR\\data"
  RMDir /r "$INSTDIR\\etc"
  RMDir /r "$INSTDIR\\gi_typelibs"
  RMDir /r "$INSTDIR\\include"
  RMDir /r "$INSTDIR\\lib2to3"
  RMDir /r "$INSTDIR\\pycountry"
  RMDir /r "$INSTDIR\\share"
  RMDir /r "$INSTDIR\\tcl"
  RMDir /r "$INSTDIR\\tesseract"
  RMDir /r "$INSTDIR\\tk"
  RMDir /r "$INSTDIR\\*.*"
  RMDir /r "$PROFILE\\.local"
  Delete "$INSTDIR\\*.*"
  RMDir "$INSTDIR"

  RMDir "$SMPROGRAMS\\Paperwork"
  RMDir ""

  SetRegView 64
  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  SetAutoClose true
SectionEnd
"""

def find_language(lang_str):
    lang_str = lang_str.lower()
    if "_" in lang_str:
        lang_str = lang_str.split("_")[0]
    print("System language: {}".format(lang_str))

    attrs = (
        'iso_639_3_code',
        'iso639_3_code',
        'iso639_2T_code',
        'iso639_1_code',
        'terminology',
        'bibliographic',
        'alpha_3',
        'alpha_2',
        'alpha2',
        'name',
    )
    for attr in attrs:
        try:
            r = pycountry.pycountry.languages.get(**{attr: lang_str})
            if r is not None:
                return r
        except (KeyError, UnicodeDecodeError):
            pass
    raise Exception("Unable to find language !")


def get_lang_infos(lang_name):
    if isinstance(lang_name, dict):
        return lang_name

    lang = lang_name.split("_")
    lang_name = lang[0]
    suffix = "" if len(lang) <= 1 else lang[1]

    lang = find_language(lang_name)

    if not suffix:
        long_name = lang.name
    else:
        long_name = "{} ({})".format(lang.name, suffix)

    return {
        "lower": lang_name.lower() + suffix.lower(),
        "upper": lang_name.upper() + suffix.upper(),
        "long": long_name,
    }


def main(args):
    if (len(args) < 2):
        print ("ARGS: {} <version> [<download URI>]".format(args[0]))
        return

    download_uri = DEFAULT_DOWNLOAD_URI

    if len(args) == 3:
        version = short_version = args[1]
        download_uri = args[2]
    else:
        version = args[1]
        m = re.match(r"([\d\.]+)", version)  # match everything but the suffix
        short_version = m.string[m.start():m.end()]
        download_uri = DEFAULT_DOWNLOAD_URI

    with open("out.nsi", "w") as out_fd:
        out_fd.write(VERSION.format(version=version, short_version=short_version, download_uri=download_uri))
        out_fd.write(HEADER)
        out_fd.write("""
SectionGroup /e "Tesseract OCR data files" SEC_OCR_FILES
""")

        langs = {}
        for lang_name in ALL_LANGUAGES:
            print ("Adding download section {}".format(lang_name))
            lang = UNKNOWN_LANGUAGE
            if isinstance(lang_name, str) and lang_name in KNOWN_LANGUAGES:
                lang = KNOWN_LANGUAGES[lang_name]
            txt = lang['download_section']
            infos = get_lang_infos(lang_name)
            txt = txt.format(**infos)
            langs[infos['long']] = txt
        lang_sorted = sorted(langs.keys())
        for lang_name in lang_sorted:
            out_fd.write(langs[lang_name])
        out_fd.write("""
SectionGroupEnd
""")
        out_fd.write(MIDDLE)

        for lang_name in ALL_LANGUAGES:
            print ("Adding strings section {}".format(lang_name))
            lang = UNKNOWN_LANGUAGE
            if isinstance(lang_name, str) and lang_name in KNOWN_LANGUAGES:
                lang = KNOWN_LANGUAGES[lang_name]
            txt = lang['lang_strings']
            txt = txt.format(**get_lang_infos(lang_name))
            out_fd.write(txt)

        out_fd.write("""
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_PAPERWORK} $(DESC_SEC_PAPERWORK)
""")

        for lang_name in ALL_LANGUAGES:
            print ("Adding MUI section {}".format(lang_name))
            infos = get_lang_infos(lang_name)
            txt = "  !insertmacro MUI_DESCRIPTION_TEXT ${{SEC_{upper}}} $(DESC_SEC_{upper})\n".format(upper=infos['upper'])
            out_fd.write(txt)
        out_fd.write("""
  !insertmacro MUI_DESCRIPTION_TEXT ${SEC_DESKTOP_ICON} $(DESC_SEC_DESKTOP_ICON)
!insertmacro MUI_FUNCTION_DESCRIPTION_END
""")

        out_fd.write(FOOTER)
    print ("out.nsi written")


if __name__ == "__main__":
    main(sys.argv)
