""" Module contains test fixtures meant to aide in the testing of jobs and
tool evaluation. Such extensive "fixtures" are something of an anti-pattern
so use of this should be limitted to tests of very 'extensive' classes.
"""

import os.path
import shutil
import string
import tempfile

from collections import defaultdict

from unittest_utils import galaxy_mock

import galaxy.datatypes.registry
import galaxy.model

from galaxy.tools import create_tool_from_source
from galaxy.tools.parser import get_tool_source
from galaxy.util.bunch import Bunch


datatypes_registry = galaxy.datatypes.registry.Registry()
datatypes_registry.load_datatypes()
galaxy.model.set_datatypes_registry(datatypes_registry)


class UsesApp(object):

    def setup_app(self):
        self.test_directory = tempfile.mkdtemp()
        self.app = galaxy_mock.MockApp()
        self.app.config.new_file_path = os.path.join(self.test_directory, "new_files")
        self.app.config.admin_users = "mary@example.com"

    def tear_down_app(self):
        shutil.rmtree(self.test_directory)


# Simple tool with just one text parameter and output.
SIMPLE_TOOL_CONTENTS = '''<tool id="${tool_id}" name="Test Tool" version="$version" profile="$profile">
    <command>echo "$param1" &lt; $out1</command>
    <inputs>
        <param type="text" name="param1" value="" />
    </inputs>
    <outputs>
        <data name="out1" format="data" label="Output ($param1)" />
    </outputs>
</tool>
'''


# A tool with data parameters (kind of like cat1) my favorite test tool :)
SIMPLE_CAT_TOOL_CONTENTS = '''<tool id="${tool_id}" name="Test Tool" version="$version" profile="$profile">
    <command>cat "$param1" #for $r in $repeat# "$r.param2" #end for# &lt; $out1</command>
    <inputs>
        <param type="data" format="tabular" name="param1" value="" />
        <repeat name="repeat1" label="Repeat 1">
            <param type="data" format="tabular" name="param2" value="" />
        </repeat>
    </inputs>
    <outputs>
        <data name="out1" format="data" />
    </outputs>
</tool>
'''


class UsesTools(object):

    def _init_tool(
        self,
        tool_contents=SIMPLE_TOOL_CONTENTS,
        filename="tool.xml",
        version="1.0",
        profile="16.01",
        tool_id="test_tool",
    ):
        self._init_app_for_tools()
        self.tool_file = os.path.join(self.test_directory, filename)
        contents_template = string.Template(tool_contents)
        tool_contents = contents_template.safe_substitute(dict(version=version, profile=profile, tool_id=tool_id))
        self.__write_tool(tool_contents)
        return self.__setup_tool()

    def _init_app_for_tools(self):
        self.app.config.drmaa_external_runjob_script = ""
        self.app.config.tool_secret = "testsecret"
        self.app.config.track_jobs_in_database = False
        self.app.job_config["get_job_tool_configurations"] = lambda ids: [Bunch(handler=Bunch())]

    def __setup_tool(self):
        tool_source = get_tool_source(self.tool_file)
        try:
            self.tool = create_tool_from_source(self.app, tool_source, config_file=self.tool_file)
        except Exception:
            self.tool = None
        if getattr(self, "tool_action", None and self.tool):
            self.tool.tool_action = self.tool_action
        return self.tool

    def __write_tool(self, contents):
        open(self.tool_file, "w").write(contents)


class MockContext(object):

    def __init__(self, model_objects=None):
        self.expunged_all = False
        self.flushed = False
        self.model_objects = model_objects or defaultdict(lambda: {})
        self.created_objects = []
        self.current = self

    def expunge_all(self):
        self.expunged_all = True

    def query(self, clazz):
        return MockQuery(self.model_objects.get(clazz))

    def flush(self):
        self.flushed = True

    def add(self, object):
        self.created_objects.append(object)


class MockQuery(object):

    def __init__(self, class_objects):
        self.class_objects = class_objects

    def filter_by(self, **kwds):
        return Bunch(first=lambda: None)

    def get(self, id):
        return self.class_objects.get(id, None)


__all__ = ('UsesApp', )
