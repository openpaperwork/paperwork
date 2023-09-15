#!/usr/bin/env python3

import collections
import fnmatch
import json
import os
import os.path
import re
import subprocess
import sys


CATEGORIES = [
    # order of evaluation matters
    ("doc", "Documentation"),
    ("openpaperwork-core", "OpenPaperwork Core"),
    ("openpaperwork-gtk", "OpenPaperwork GTK"),
    ("paperwork-backend", "Paperwork Backend"),
    ("paperwork-gtk", "GTK Frontend"),
    ("paperwork-shell", "CLI Frontend"),
    ("flatpak", "Flatpak Integration"),
    (None, "Others"),  # default
]


REPLACEMENT_RULES = {
    # Because I'm a dimw** who doesn't always configure his Git correctly.
    "jflesch": "Jerome Flesch",

    # Those are translations commits from Weblate. Weblate credits are
    # downloaded from Weblate manually.
    "Weblate Admin": None,

    # Shouldn't happen
    "Not Committed Yet": None,
}


EXTRA_IGNORES = [
    "sub",
    ".git",
    "AUTHORS*",
]


REGEX_EMAIL_AUTHOR = re.compile(
    r"[^(]*\((.+)\s\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} .*"
)


def split_path(path):
    path = os.path.normpath(path)
    return path.split(os.sep)


class IgnoreList(object):
    def __init__(self, ignore_list):
        self.ignore_list = EXTRA_IGNORES + ignore_list

    @staticmethod
    def find_gitignore():
        current_dir = os.path.abspath(__file__)
        while not os.path.exists(os.path.join(current_dir, ".gitignore")):
            current_dir = os.path.dirname(current_dir)
            if current_dir == "/":
                raise Exception(".gitignore not found")
        return os.path.join(current_dir, ".gitignore")

    @staticmethod
    def load():
        gitignore_path = IgnoreList.find_gitignore()
        sys.stderr.write("Loading {} ... ".format(gitignore_path))
        sys.stderr.flush()
        with open(gitignore_path, 'r') as fd:
            ignore_list = fd.readlines()
        ignore_list = [line.strip() for line in ignore_list]
        ignore_list = [line for line in ignore_list if line != ""]
        ignore_list = [line.replace("/", "") for line in ignore_list]
        sys.stderr.write("{} ignores loaded\n".format(len(ignore_list)))
        return IgnoreList(ignore_list)

    def match(self, file_path):
        for pattern in self.ignore_list:
            if fnmatch.fnmatch(file_path, pattern):
                return True

        file_path = split_path(file_path)
        for pattern in self.ignore_list:
            for file_path_component in file_path:
                if fnmatch.fnmatch(file_path_component, pattern):
                    return True
        return False


def walk(directory, ignore_list):
    for (dirpath, dirnames, file_names) in os.walk(directory):
        for file_name in file_names:
            file_path = os.path.join(dirpath, file_name)
            if ignore_list.match(file_path):
                continue
            yield file_path


def get_category_name(file_path):
    file_path = split_path(file_path)
    for (category_pattern, category_name) in CATEGORIES:
        if category_pattern is None:
            return category_name
        for component in file_path:
            if component == category_pattern:
                return category_name
    assert False


def count_lines(line_counts, file_path):
    output = subprocess.run(
        ['git', 'blame', file_path],
        capture_output=True
    )
    if output.returncode != os.EX_OK:
        sys.stderr.write(
            "WARNING: git blame {} failed ! (returncode={})\n".format(
                file_path, output.returncode
            )
        )
        return

    try:
        stdout = output.stdout.decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write(
            "WARNING: Unicode on {}. Assuming it's a binary file\n".format(
                file_path
            )
        )
        return

    stdout = [line.strip() for line in stdout.split("\n")]

    for line in stdout:
        if line == "":
            continue

        author = REGEX_EMAIL_AUTHOR.match(line)
        if author is None:
            sys.stderr.write(
                "WARNING: Failed to find author email in the following line:\n"
            )
            sys.stderr.write(line + "\n")
            continue
        author = author[1].strip()
        author = REPLACEMENT_RULES.get(author, author)

        if author is None:
            # replacement rules told us to ignore this one
            continue

        line_counts[author] += 1


def dump_json(line_counts):
    # We want to merge this JSON with the one from Weblate later. So we
    # imitate the weird JSON output of Weblate here.

    out = []
    for (category_name, authors) in line_counts.items():
        category = {category_name: []}
        out.append(category)

        category = category[category_name]
        for (author, line_count) in authors.items():
            category.append([
                '',  # we don't care about emails
                author,
                line_count,
            ])
        # sort authors by line count
        category.sort(key=lambda x: x[2], reverse=True)

    # Sort categories alphabetically
    out.sort(key=lambda x: next(iter(x)).lower())

    print(json.dumps(
        out,
        indent=4,
        separators=(',', ': '),
        sort_keys=True
    ))


def main():
    if len(sys.argv) < 2 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
        sys.stderr.write("Syntax:\n")
        sys.stderr.write("  {} <directory to examine>\n".format(sys.argv[0]))
        return

    ignore_list = IgnoreList.load()
    line_counts = collections.defaultdict(
        lambda: collections.defaultdict(lambda: 0)
    )

    for file_path in walk(sys.argv[1], ignore_list):
        category = get_category_name(file_path)
        sys.stderr.write("Examining {} (category={}) ...\n".format(
            file_path, category
        ))
        counts = line_counts[category]
        count_lines(counts, file_path)

    for (category, authors) in line_counts.items():
        sys.stderr.write("  - {}\n".format(category))
        for (k, v) in authors.items():
            sys.stderr.write("{}: {}\n".format(k, v))
        sys.stderr.write("\n")

    dump_json(line_counts)


if __name__ == "__main__":
    main()
