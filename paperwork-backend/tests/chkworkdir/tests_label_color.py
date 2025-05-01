import unittest

import openpaperwork_core

from paperwork_backend.interfaces.chkworkdir import Chkworkdir


class TestChkWorkDirEmptyDirectory(unittest.TestCase):
    def setUp(self):
        self.core = openpaperwork_core.Core(auto_load_dependencies=True)
        self.core.load("openpaperwork_core.config.fake")
        self.core.load("openpaperwork_core.fs.fake")
        self.core.load("paperwork_backend.chkworkdir.label_color")
        self.core.init()

        self.config = self.core.get_by_name("openpaperwork_core.config.fake")
        self.config.settings = {
            "workdir": "file:///some_work_dir"
        }
        self.fs = self.core.get_by_name("openpaperwork_core.fs.fake")

    def test_no_problem(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                    "labels": (
                        "coloc,rgb(182,133,45)\n"
                        "facture,rgb(0,177,140)\n"
                        "logement,rgb(246,255,0)\n"
                    )
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                    "labels": (
                        "banque,#702000006e5f\n"
                        "fiche de paie,rgb(0,155,0)\n"
                    )
                },
            },
        }

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 0)

    def test_check_fix(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                    "labels": (
                        "coloc,rgb(182,133,45)\n"
                        "facture,#aabbccddeeff\n"
                        "logement,rgb(246,255,0)\n"
                    )
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                    "labels": (
                        "banque,#702000006e5f\n"
                        "fiche de paie,rgb(0,155,0)\n"
                    )
                },
                "some_doc_zzz_bad_label_color": {
                    "labels": (
                        "coloc,rgb(182,133,45)\n"
                        "facture,rgb(0,177,140)\n"
                        "logement,rgb(246,255,0)\n"
                    )
                },
            },
        }

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 1)

        self.core.call_all(Chkworkdir.fix_work_dir, problems)

        fs = self.fs.fs
        self.assertEqual(
            fs['some_work_dir']['some_doc_zzz_bad_label_color']['labels'],
            (
                "coloc,rgb(182,133,45)\n"
                "logement,rgb(246,255,0)\n"
                "facture,#aabbccddeeff\n"  # fixed
            )
        )
        self.maxDiff = None
        self.assertEqual(
            self.fs.fs, {
                "some_work_dir": {
                    "some_doc_a": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                        "labels": (
                            "coloc,rgb(182,133,45)\n"
                            "facture,#aabbccddeeff\n"
                            "logement,rgb(246,255,0)\n"
                        )
                    },
                    "some_doc_b": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                        "labels": (
                            "banque,#702000006e5f\n"
                            "fiche de paie,rgb(0,155,0)\n"
                        )
                    },
                    "some_doc_zzz_bad_label_color": {
                        "labels": (
                            "coloc,rgb(182,133,45)\n"
                            "logement,rgb(246,255,0)\n"
                            "facture,#aabbccddeeff\n"  # fixed
                        )
                    },
                },
            }
        )

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 0)

    def test_check_rgb(self):
        self.fs.fs = {
            "some_work_dir": {
                "some_doc_a": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                    "labels": (
                        "coloc,rgb(182,133,45)\n"
                        "facture,rgb(1,10,20)\n"
                        "logement,rgb(246,255,0)\n"
                    )
                },
                "some_doc_b": {
                    "paper.1.jpg": "put_an_image_here",
                    "paper.2.jpg": "put_an_image_here",
                    "labels": (
                        "banque,#702000006e5f\n"
                        "fiche de paie,rgb(0,155,0)\n"
                    )
                },
                "some_doc_zzz_bad_label_color": {
                    "labels": (
                        "coloc,rgb(182,133,45)\n"
                        "facture,rgb(0,177,140)\n"
                        "logement,rgb(246,255,0)\n"
                    )
                },
            },
        }

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 1)

        self.core.call_all(Chkworkdir.fix_work_dir, problems)

        fs = self.fs.fs
        self.assertEqual(
            fs['some_work_dir']['some_doc_zzz_bad_label_color']['labels'],
            (
                "coloc,rgb(182,133,45)\n"
                "logement,rgb(246,255,0)\n"
                "facture,rgb(1,10,20)\n"  # fixed
            )
        )
        self.maxDiff = None
        self.assertEqual(
            self.fs.fs, {
                "some_work_dir": {
                    "some_doc_a": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                        "labels": (
                            "coloc,rgb(182,133,45)\n"
                            "facture,rgb(1,10,20)\n"
                            "logement,rgb(246,255,0)\n"
                        )
                    },
                    "some_doc_b": {
                        "paper.1.jpg": "put_an_image_here",
                        "paper.2.jpg": "put_an_image_here",
                        "labels": (
                            "banque,#702000006e5f\n"
                            "fiche de paie,rgb(0,155,0)\n"
                        )
                    },
                    "some_doc_zzz_bad_label_color": {
                        "labels": (
                            "coloc,rgb(182,133,45)\n"
                            "logement,rgb(246,255,0)\n"
                            "facture,rgb(1,10,20)\n"  # fixed
                        )
                    },
                },
            }
        )

        problems = []
        self.core.call_all(Chkworkdir.check_work_dir, problems)
        self.assertEqual(len(problems), 0)
