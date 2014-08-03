#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2014  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import logging
import re

import pyinsane.abstract_th as pyinsane


logger = logging.getLogger(__name__)


def _set_scanner_opt(scanner_opt_name, scanner_opt, possible_values):
    value = possible_values[0]
    regexs = [re.compile(x, flags=re.IGNORECASE) for x in possible_values]

    if (scanner_opt.constraint_type ==
            pyinsane.SaneConstraintType.STRING_LIST):
        value = None
        for regex in regexs:
            for constraint in scanner_opt.constraint:
                if regex.match(constraint):
                    value = constraint
                    break
            if value is not None:
                break
        if value is None:
            raise pyinsane.SaneException(
                "%s are not a valid values for option %s"
                % (str(possible_values), scanner_opt_name))

    logger.info("Setting scanner option '%s' to '%s'"
                % (scanner_opt_name, str(value)))
    scanner_opt.value = value


def set_scanner_opt(scanner_opt_name, scanner_opt, possible_values):
    """
    Set one of the scanner options

    Arguments:
        scanner_opt_name --- for verbose
        scanner_opt --- the scanner option (its value, its constraints, etc)
        possible_values --- a list of values considered valid (the first one
                            being the preferred one)
    """
    if not scanner_opt.capabilities.is_active():
        logger.warning("Unable to set scanner option '%s':"
                       " Option is not active"
                       % scanner_opt_name)
        return False

    # WORKAROUND(Jflesch): For some reason, my crappy scanner returns
    # I/O errors randomly for fun
    for t in xrange(0, 5):
        try:
            _set_scanner_opt(scanner_opt_name, scanner_opt, possible_values)
            break
        except Exception, exc:
            logger.warning("Warning: Failed to set scanner option"
                           " %s=%s: %s (try %d/5)"
                           % (scanner_opt_name, possible_values, str(exc), t))
    return True


def __set_scan_area_pos(options, opt_name, select_value_func, missing_options):
    if opt_name not in options:
        missing_options.append(opt_name)
    else:
        if not options[opt_name].capabilities.is_active():
            logger.warning("Unable to set scanner option '%s':"
                           " Option is not active" % opt_name)
            return
        constraint = options[opt_name].constraint
        if isinstance(constraint, tuple):
            value = select_value_func(constraint[0], constraint[1])
        else:  # is an array
            value = select_value_func(constraint)
        options[opt_name].value = value


def maximize_scan_area(scanner):
    opts = scanner.options
    missing_opts = []
    __set_scan_area_pos(opts, "tl-x", min, missing_opts)
    __set_scan_area_pos(opts, "tl-y", min, missing_opts)
    __set_scan_area_pos(opts, "br-x", max, missing_opts)
    __set_scan_area_pos(opts, "br-y", max, missing_opts)
    if missing_opts:
        logger.warning("Failed to maximize the scan area. Missing options: %s"
                       % ", ".join(missing_opts))
