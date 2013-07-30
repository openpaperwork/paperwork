import re

import pyinsane.abstract_th as pyinsane


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
