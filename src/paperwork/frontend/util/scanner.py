import logging
import re

import pyinsane.abstract_th as pyinsane


logger = logging.getLogger(__name__)


def set_scanner_opt(scanner_opt_name, scanner_opt, possible_values):
    """
    Set one of the scanner options

    Arguments:
        scanner_opt_name --- for verbose
        scanner_opt --- the scanner option (its value, its constraints, etc)
        possible_values --- a list of values considered valid (the first one
                            being the preferred one)
    """
    value = possible_values[0]
    regexs = [re.compile(x) for x in possible_values]

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


def __set_scan_area_pos(options, opt_name, select_value_func, missing_options):
    if not opt_name in options:
        missing_options.append(opt_name)
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
