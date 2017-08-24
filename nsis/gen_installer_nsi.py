#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import sys

from paperwork_backend.util import find_language


DOWNLOAD_URI = "https://github.com/openpaperwork/paperwork/releases/download/${PRODUCT_SHORT_VERSION}/paperwork_${PRODUCT_VERSION}_win64.zip"

ALL_LANGUAGES = [
    "eng",  # English (always first)

    "afr",
    "sqi",  # Albanian
    "amh",
    "ara",
    "asm",
    "aze",
    {"lower": "aze_cyrl", "upper": "AZECYRL", "long": "Azerbaijani - Cyrilic"},
    "eus",  # Basque
    "bel",
    "ben",
    "bos",
    "bul",
    "mya",  # Burmese
    "cat",
    "ceb",
    {"lower": "chi_sim", "upper": "CHISIM", "long": "Chinese (simplified)"},
    {"lower": "chi_tra", "upper": "CHITRA", "long": "Chinese (traditional)"},
    "chr",
    "hrv",  # Croatian
    "ces",  # Czech
    "dan",
    "nld",  # Dutch
    "dzo",
    "enm",
    "epo",  # Esperanto
    "est",
    "fin",
    "frk",  # Frankish
    "fra",  # French
    "frm",
    "kat",  # Georgian
    "deu",  # German
    "glg",
    {"lower": "grc", "upper": "GRC", "long": "Greek (ancient)"},
    {"lower": "ell", "upper": "ELL", "long": "Greek (modern)"},
    "guj",
    "hat",
    "heb",
    "hin",
    "hun",
    "isl",  # Icelandic
    "ind",
    "iku",  # Inuktitut
    "gle",  # Irish
    "ita",
    "jpn",  # Japanese
    "jav",
    "kan",
    "khm",
    "kir",
    "kor",
    "kur",
    "lao",
    "lat",
    "lav",
    "lit",
    "mal",
    "mkd",  # Macedonian
    "msa",  # Malay
    "mlt",  # Maltese
    "mar",
    "nep",
    "nor",
    "ori",
    "pan",
    {"lower": "fas", "upper": "FAS", "long": "Persian"},
    "pol",
    "por",
    "pus",
    {"lower": "ron", "upper": "RON", "long": "Romanian"},
    "rus",
    "san",
    "srp",  # Serbian
    {"lower": "srp_latn", "upper": "SRPLATN", "long": "Serbian (Latin)"},
    "sin",
    "slk",
    "slv",
    "spa",  # Spanish
    "swa",
    "swe",
    "syr",
    "tgk",  # Tajik
    "tgl",  # Tagalog
    "tam",
    "tel",
    {"lower": "tha", "upper": "THA", "long": "Thai"},
    "bod",  # Tibetan
    "tir",
    "tur",
    "uig",
    "ukr",
    "urd",
    "uzb",
    {"lower": "uzb_cyrl", "upper": "UZBCYRL", "long": "Uzbek - Cyrilic"},
    "vie",
    "cym",  # Welsh
    "yid",
 ]
 
UNKNOWN_LANGUAGE = {
    'download_section': """
        Section /o "{long}" SEC_{upper}
          inetc::get "https://github.com/tesseract-ocr/tessdata/raw/3.04.00/{lower}.traineddata" "$INSTDIR\\Data\\Tessdata\\{lower}.traineddata" /END
          Pop $0
          StrCmp $0 "OK" +3
             MessageBox MB_OK "Download of {lower}.traineddata failed"
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
          inetc::get "https://github.com/tesseract-ocr/tessdata/raw/3.04.00/{lower}.traineddata" "$INSTDIR\\Data\\Tessdata\\{lower}.traineddata" /END
          Pop $0
          StrCmp $0 "OK" +3
             MessageBox MB_OK "Download of {lower}.traineddata failed"
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

          inetc::get "https://jflesch.github.io/windows/paperwork_1.0/tessdata_eng_3_05_00dev.zip" "$PLUGINSDIR\\tess_eng.zip" /END
          Pop $0
          StrCmp $0 "OK" +3
             MessageBox MB_OK "Download of {lower}.traineddata failed"
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
          inetc::get "https://github.com/tesseract-ocr/tessdata/raw/3.04.00/{lower}.traineddata" "$INSTDIR\\Data\\Tessdata\\{lower}.traineddata" /END
          Pop $0
          StrCmp $0 "OK" +3
             MessageBox MB_OK "Download of {lower}.traineddata failed"
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

VERSION = """!define PRODUCT_VERSION "{version}\"
!define PRODUCT_SHORT_VERSION "{short_version}\""""

HEADER = """
!define PRODUCT_NAME "Paperwork"
!define PRODUCT_PUBLISHER "Openpaper.work"
!define PRODUCT_WEB_SITE "https://openpaper.work"
!define PRODUCT_UNINST_KEY "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"
!define PRODUCT_DOWNLOAD_URI "{download_uri}"

!addplugindir ".\dll"

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
!define MUI_FINISHPAGE_RUN "$INSTDIR\\paperwork.exe"
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
InstallDir "$PROGRAMFILES\\Paperwork"
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
    MessageBox MB_OK "Download failed"
    Quit

  inetc::get "https://jflesch.github.io/windows/paperwork_1.0/tesseract_3_05_00dev.zip" "$PLUGINSDIR\\tesseract.zip" /END
  Pop $0
  StrCmp $0 "OK" +3
    MessageBox MB_OK "Download failed"
    Quit

  inetc::get "https://jflesch.github.io/windows/paperwork_1.0/tessconfig_3_05_00dev.zip" "$PLUGINSDIR\\tessconfig.zip" /END
  Pop $0
  StrCmp $0 "OK" +3
    MessageBox MB_OK "Download failed"
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
  MessageBox MB_ICONQUESTION|MB_YESNO|MB_DEFBUTTON2 "Are you sure you want to deinstall $(^Name) ? (your documents won't be deleted)" IDYES +2
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
  Delete "$INSTDIR\\*.*"
  RMDir "$INSTDIR"

  RMDir "$SMPROGRAMS\\Paperwork"
  RMDir ""

  DeleteRegKey ${PRODUCT_UNINST_ROOT_KEY} "${PRODUCT_UNINST_KEY}"
  SetAutoClose true
SectionEnd
"""


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

    download_uri = DOWNLOAD_URI
    
    if len(args) == 3:
        version = short_version = args[1]
        download_uri = args[2]
    else:
        version = args[1]
        m = re.match("([\d\.]+)", version)  # match everything but the suffix
        short_version = m.string[m.start():m.end()]
        download_uri = DOWNLOAD_URI

    with open("out.nsi", "w") as out_fd:
        out_fd.write(VERSION.format(version=version, short_version=short_version, download_uri=download_uri))
        out_fd.write(HEADER)


        out_fd.write("""
SectionGroup /e "Tesseract OCR data files" SEC_OCR_FILES
""")
        for lang_name in ALL_LANGUAGES:
            print ("Adding download section {}".format(lang_name))
            lang = UNKNOWN_LANGUAGE
            if isinstance(lang_name, str) and lang_name in KNOWN_LANGUAGES:
                lang = KNOWN_LANGUAGES[lang_name]
            txt = lang['download_section']
            txt = txt.format(**get_lang_infos(lang_name))
            out_fd.write(txt)
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