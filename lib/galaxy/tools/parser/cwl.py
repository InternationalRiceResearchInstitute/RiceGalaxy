import logging
import os

from galaxy.tools.cwl import tool_proxy
from galaxy.tools.deps import requirements
from galaxy.util.odict import odict

from .interface import PageSource
from .interface import PagesSource
from .interface import ToolSource
from .interface import ToolStdioExitCode
from .output_actions import ToolOutputActionGroup
from .output_objects import ToolOutput
from .yaml import YamlInputSource

log = logging.getLogger(__name__)


class CwlToolSource(ToolSource):

    def __init__(self, tool_file, strict_cwl_validation=True):
        self._cwl_tool_file = tool_file
        self._id, _ = os.path.splitext(os.path.basename(tool_file))
        self._tool_proxy = None
        self._source_path = tool_file
        self._strict_cwl_validation = strict_cwl_validation

    @property
    def tool_proxy(self):
        if self._tool_proxy is None:
            self._tool_proxy = tool_proxy(self._source_path, strict_cwl_validation=self._strict_cwl_validation)
        return self._tool_proxy

    def parse_tool_type(self):
        return 'cwl'

    def parse_id(self):
        return self._id

    def parse_name(self):
        return self.tool_proxy.label() or self.parse_id()

    def parse_command(self):
        return "$__cwl_command"

    def parse_environment_variables(self):
        environment_variables = []
        # TODO: Is this even possible from here, should instead this be moved
        # into the job.

        # for environment_variable_el in environment_variables_el.findall("environment_variable"):
        #    definition = {
        #        "name": environment_variable_el.get("name"),
        #        "template": environment_variable_el.text,
        #    }
        #    environment_variables.append(
        #        definition
        #    )

        return environment_variables

    def parse_edam_operations(self):
        return []

    def parse_edam_topics(self):
        return []

    def parse_help(self):
        return self.tool_proxy.description() or ""

    def parse_sanitize(self):
        return False

    def parse_strict_shell(self):
        return True

    def parse_stdio(self):
        # TODO: remove duplication with YAML
        from galaxy.jobs.error_level import StdioErrorLevel

        # New format - starting out just using exit code.
        exit_code_lower = ToolStdioExitCode()
        exit_code_lower.range_start = float("-inf")
        exit_code_lower.range_end = -1
        exit_code_lower.error_level = StdioErrorLevel.FATAL
        exit_code_high = ToolStdioExitCode()
        exit_code_high.range_start = 1
        exit_code_high.range_end = float("inf")
        exit_code_lower.error_level = StdioErrorLevel.FATAL
        return [exit_code_lower, exit_code_high], []

    def parse_interpreter(self):
        return None

    def parse_version(self):
        return "0.0.1"

    def parse_description(self):
        return self.tool_proxy.description()

    def parse_input_pages(self):
        page_source = CwlPageSource(self.tool_proxy)
        return PagesSource([page_source])

    def parse_outputs(self, tool):
        output_instances = self.tool_proxy.output_instances()
        outputs = odict()
        output_defs = []
        for output_instance in output_instances:
            output_defs.append(self._parse_output(tool, output_instance))
        # TODO: parse outputs collections
        for output_def in output_defs:
            outputs[output_def.name] = output_def
        return outputs, odict()

    def _parse_output(self, tool, output_instance):
        name = output_instance.name
        # TODO: handle filters, actions, change_format
        output = ToolOutput(name)
        if "File" in output_instance.output_data_type:
            output.format = "_sniff_"
        else:
            output.format = "expression.json"
        output.change_format = []
        output.format_source = None
        output.metadata_source = ""
        output.parent = None
        output.label = None
        output.count = None
        output.filters = []
        output.tool = tool
        output.hidden = ""
        output.dataset_collector_descriptions = []
        output.actions = ToolOutputActionGroup(output, None)
        return output

    def parse_requirements_and_containers(self):
        containers = []
        docker_identifier = self.tool_proxy.docker_identifier()
        if docker_identifier:
            containers.append({"type": "docker",
                               "identifier": docker_identifier})
        return requirements.parse_requirements_from_dict(dict(
            requirements=[],  # TODO: enable via extensions
            containers=containers,
        ))

    def parse_profile(self):
        return "16.04"


class CwlPageSource(PageSource):

    def __init__(self, tool_proxy):
        cwl_instances = tool_proxy.input_instances()
        self._input_list = map(self._to_input_source, cwl_instances)

    def _to_input_source(self, input_instance):
        as_dict = input_instance.to_dict()
        return YamlInputSource(as_dict)

    def parse_input_sources(self):
        return self._input_list
