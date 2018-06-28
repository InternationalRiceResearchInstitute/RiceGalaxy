"""This module contains a linting functions for tool error detection."""
from .command import get_command


def lint_stdio(tool_source, lint_ctx):
    tool_xml = getattr(tool_source, "xml_tree", None)
    stdios = tool_xml.findall("./stdio") if tool_xml else []

    if not stdios:
        command = get_command(tool_xml) if tool_xml else None
        if command is None or not command.get("detect_errors"):
            if tool_source.parse_profile() <= "16.01":
                lint_ctx.info("No stdio definition found, tool indicates error conditions with output written to stderr.")
            else:
                lint_ctx.info("No stdio definition found, tool indicates error conditions with non-zero exit codes.")
        return

    if len(stdios) > 1:
        lint_ctx.error("More than one stdio tag found, behavior undefined.")
        return

    stdio = stdios[0]
    for child in list(stdio):
        if child.tag == "regex":
            _lint_regex(child, lint_ctx)
        elif child.tag == "exit_code":
            _lint_exit_code(child, lint_ctx)
        else:
            message = "Unknown stdio child tag discovered [%s]. "
            message += "Valid options are exit_code and regex."
            lint_ctx.warn(message % child.tag)


def _lint_exit_code(child, lint_ctx):
    for key, value in child.attrib.items():
        if key == "range":
            # TODO: validate
            pass
        elif key == "level":
            _lint_level(value, lint_ctx)
        elif key == "description":
            pass
        else:
            lint_ctx.warn("Unknown attribute [%s] encountered on exit_code tag." % key)


def _lint_regex(child, lint_ctx):
    for key, value in child.attrib.items():
        if key == "source":
            if value not in ["stderr", "stdout", "both"]:
                lint_ctx.error("Unknown error code level encountered [%s]" % value)
        elif key == "level":
            _lint_level(value, lint_ctx)
        elif key == "match":
            # TODO: validate
            pass
        elif key == "description":
            pass
        else:
            lint_ctx.warn("Unknown attribute [%s] encountered on regex tag." % key)


def _lint_level(level_value, lint_ctx):
    if level_value not in ["warning", "fatal", "log"]:
        lint_ctx.error("Unknown error code level encountered [%s]" % level_value)
