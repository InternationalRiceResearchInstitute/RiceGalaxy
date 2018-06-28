"""
API operations for Workflows
"""
from __future__ import absolute_import

import logging

from six.moves.urllib.parse import unquote_plus
from sqlalchemy import desc, false, or_, true

from galaxy import (
    exceptions,
    model,
    util
)
from galaxy.managers import (
    histories,
    workflows
)
from galaxy.model.item_attrs import UsesAnnotations
from galaxy.tools.parameters import populate_state
from galaxy.util.sanitize_html import sanitize_html
from galaxy.web import _future_expose_api as expose_api
from galaxy.web.base.controller import (
    BaseAPIController,
    SharableMixin,
    url_for,
    UsesStoredWorkflowMixin
)
from galaxy.workflow.extract import extract_workflow
from galaxy.workflow.modules import module_factory
from galaxy.workflow.run import invoke, queue_invoke
from galaxy.workflow.run_request import build_workflow_run_configs

from tool_shed.galaxy_install.install_manager import InstallRepositoryManager

log = logging.getLogger(__name__)


class WorkflowsAPIController(BaseAPIController, UsesStoredWorkflowMixin, UsesAnnotations, SharableMixin):

    def __init__(self, app):
        super(WorkflowsAPIController, self).__init__(app)
        self.history_manager = histories.HistoryManager(app)
        self.workflow_manager = workflows.WorkflowsManager(app)
        self.workflow_contents_manager = workflows.WorkflowContentsManager(app)

    def __get_full_shed_url(self, url):
        for name, shed_url in self.app.tool_shed_registry.tool_sheds.items():
            if url in shed_url:
                return shed_url
        return None

    @expose_api
    def index(self, trans, **kwd):
        """
        GET /api/workflows
        """
        return self.get_workflows_list(trans, kwd)

    @expose_api
    def get_workflow_menu(self, trans, **kwd):
        """
        Get workflows present in the tools panel
        GET /api/workflows/menu
        """
        user = trans.get_user()
        ids_in_menu = [x.stored_workflow_id for x in user.stored_workflow_menu_entries]
        return {
            'ids_in_menu': ids_in_menu,
            'workflows': self.get_workflows_list(trans, kwd)
        }

    @expose_api
    def set_workflow_menu(self, trans, **kwd):
        """
        Save workflow menu to be shown in the tool panel
        PUT /api/workflows/menu
        """
        payload = kwd.get('payload')
        user = trans.get_user()
        workflow_ids = payload.get('workflow_ids')
        if workflow_ids is None:
            workflow_ids = []
        elif type(workflow_ids) != list:
            workflow_ids = [workflow_ids]
        workflow_ids_decoded = []
        # Decode the encoded workflow ids
        for ids in workflow_ids:
            workflow_ids_decoded.append(trans.security.decode_id(ids))
        sess = trans.sa_session
        # This explicit remove seems like a hack, need to figure out
        # how to make the association do it automatically.
        for m in user.stored_workflow_menu_entries:
            sess.delete(m)
        user.stored_workflow_menu_entries = []
        q = sess.query(model.StoredWorkflow)
        # To ensure id list is unique
        seen_workflow_ids = set()
        for wf_id in workflow_ids_decoded:
            if wf_id in seen_workflow_ids:
                continue
            else:
                seen_workflow_ids.add(wf_id)
            m = model.StoredWorkflowMenuEntry()
            m.stored_workflow = q.get(wf_id)
            user.stored_workflow_menu_entries.append(m)
        sess.flush()
        message = "Menu updated."
        trans.set_message(message)
        return {'message': message, 'status': 'done'}

    def get_workflows_list(self, trans, kwd):
        """
        Displays a collection of workflows.

        :param  show_published:      if True, show also published workflows
        :type   show_published:      boolean
        :param  missing_tools:       if True, include a list of missing tools per workflow
        :type   missing_tools:       boolean
        """
        show_published = util.string_as_bool(kwd.get('show_published', 'False'))
        missing_tools = util.string_as_bool(kwd.get('missing_tools', 'False'))
        rval = []
        filter1 = (trans.app.model.StoredWorkflow.user == trans.user)
        user = trans.get_user()
        if show_published:
            filter1 = or_(filter1, (trans.app.model.StoredWorkflow.published == true()))
        for wf in trans.sa_session.query(trans.app.model.StoredWorkflow).filter(
                filter1, trans.app.model.StoredWorkflow.table.c.deleted == false()).order_by(
                desc(trans.app.model.StoredWorkflow.table.c.update_time)).all():

            item = wf.to_dict(value_mapper={'id': trans.security.encode_id})
            encoded_id = trans.security.encode_id(wf.id)
            item['url'] = url_for('workflow', id=encoded_id)
            item['owner'] = wf.user.username
            item['number_of_steps'] = len(wf.latest_workflow.steps)
            item['show_in_tool_panel'] = False
            for x in user.stored_workflow_menu_entries:
                if x.stored_workflow_id == wf.id:
                    item['show_in_tool_panel'] = True
                    break
            rval.append(item)
        for wf_sa in trans.sa_session.query(trans.app.model.StoredWorkflowUserShareAssociation).filter_by(
                user=trans.user).join('stored_workflow').filter(
                trans.app.model.StoredWorkflow.deleted == false()).order_by(
                desc(trans.app.model.StoredWorkflow.update_time)).all():
            item = wf_sa.stored_workflow.to_dict(value_mapper={'id': trans.security.encode_id})
            encoded_id = trans.security.encode_id(wf_sa.stored_workflow.id)
            item['url'] = url_for('workflow', id=encoded_id)
            item['slug'] = wf_sa.stored_workflow.slug
            item['owner'] = wf_sa.stored_workflow.user.username
            item['number_of_steps'] = len(wf_sa.stored_workflow.latest_workflow.steps)
            item['show_in_tool_panel'] = False
            for x in user.stored_workflow_menu_entries:
                if x.stored_workflow_id == wf_sa.id:
                    item['show_in_tool_panel'] = True
                    break
            rval.append(item)
        if missing_tools:
            workflows_missing_tools = []
            workflows = []
            workflows_by_toolshed = dict()
            for key, value in enumerate(rval):
                tool_ids = []
                workflow_details = self.workflow_contents_manager.workflow_to_dict(trans, self.__get_stored_workflow(trans, value['id']), style='instance')
                if 'steps' in workflow_details:
                    for step in workflow_details['steps']:
                        tool_id = workflow_details['steps'][step]['tool_id']
                        if tool_id not in tool_ids and self.app.toolbox.is_missing_shed_tool(tool_id):
                            tool_ids.append(tool_id)
                if len(tool_ids) > 0:
                    value['missing_tools'] = tool_ids
                    workflows_missing_tools.append(value)
            for workflow in workflows_missing_tools:
                for tool_id in workflow['missing_tools']:
                    toolshed, _, owner, name, tool, version = tool_id.split('/')
                    shed_url = self.__get_full_shed_url(toolshed)
                    repo_identifier = '/'.join([toolshed, owner, name])
                    if repo_identifier not in workflows_by_toolshed:
                        workflows_by_toolshed[repo_identifier] = dict(shed=shed_url.rstrip('/'), repository=name, owner=owner, tools=[tool_id], workflows=[workflow['name']])
                    else:
                        if tool_id not in workflows_by_toolshed[repo_identifier]['tools']:
                            workflows_by_toolshed[repo_identifier]['tools'].append(tool_id)
                        if workflow['name'] not in workflows_by_toolshed[repo_identifier]['workflows']:
                            workflows_by_toolshed[repo_identifier]['workflows'].append(workflow['name'])
            for repo_tag in workflows_by_toolshed:
                workflows.append(workflows_by_toolshed[repo_tag])
            return workflows
        return rval

    @expose_api
    def show(self, trans, id, **kwd):
        """
        GET /api/workflows/{encoded_workflow_id}

        Displays information needed to run a workflow from the command line.
        """
        stored_workflow = self.__get_stored_workflow(trans, id)
        if stored_workflow.importable is False and stored_workflow.user != trans.user and not trans.user_is_admin():
            if trans.sa_session.query(trans.app.model.StoredWorkflowUserShareAssociation).filter_by(user=trans.user, stored_workflow=stored_workflow).count() == 0:
                message = "Workflow is neither importable, nor owned by or shared with current user"
                raise exceptions.ItemAccessibilityException(message)
        if kwd.get("legacy", False):
            style = "legacy"
        else:
            style = "instance"
        return self.workflow_contents_manager.workflow_to_dict(trans, stored_workflow, style=style)

    @expose_api
    def create(self, trans, payload, **kwd):
        """
        POST /api/workflows

        Run or create workflows from the api.

        If installed_repository_file or from_history_id is specified a new
        workflow will be created for this user. Otherwise, workflow_id must be
        specified and this API method will cause a workflow to execute.

        :param  installed_repository_file    The path of a workflow to import. Either workflow_id, installed_repository_file or from_history_id must be specified
        :type   installed_repository_file    str

        :param  workflow_id:                 An existing workflow id. Either workflow_id, installed_repository_file or from_history_id must be specified
        :type   workflow_id:                 str

        :param  parameters:                  If workflow_id is set - see _update_step_parameters()
        :type   parameters:                  dict

        :param  ds_map:                      If workflow_id is set - a dictionary mapping each input step id to a dictionary with 2 keys: 'src' (which can be 'ldda', 'ld' or 'hda') and 'id' (which should be the id of a LibraryDatasetDatasetAssociation, LibraryDataset or HistoryDatasetAssociation respectively)
        :type   ds_map:                      dict

        :param  no_add_to_history:           If workflow_id is set - if present in the payload with any value, the input datasets will not be added to the selected history
        :type   no_add_to_history:           str

        :param  history:                     If workflow_id is set - optional history where to run the workflow, either the name of a new history or "hist_id=HIST_ID" where HIST_ID is the id of an existing history. If not specified, the workflow will be run a new unnamed history
        :type   history:                     str

        :param  replacement_params:          If workflow_id is set - an optional dictionary used when renaming datasets
        :type   replacement_params:          dict

        :param  from_history_id:             Id of history to extract a workflow from. Either workflow_id, installed_repository_file or from_history_id must be specified
        :type   from_history_id:             str

        :param  job_ids:                     If from_history_id is set - optional list of jobs to include when extracting a workflow from history
        :type   job_ids:                     str

        :param  dataset_ids:                 If from_history_id is set - optional list of HDA `hid`s corresponding to workflow inputs when extracting a workflow from history
        :type   dataset_ids:                 str

        :param  dataset_collection_ids:      If from_history_id is set - optional list of HDCA `hid`s corresponding to workflow inputs when extracting a workflow from history
        :type   dataset_collection_ids:      str

        :param  workflow_name:               If from_history_id is set - name of the workflow to create when extracting a workflow from history
        :type   workflow_name:               str

        :param  allow_tool_state_corrections:  If set to True, any Tool parameter changes will not prevent running workflow, defaults to False
        :type   allow_tool_state_corrections:  bool
        """
        ways_to_create = set([
            'workflow_id',
            'installed_repository_file',
            'from_history_id',
            'shared_workflow_id',
            'workflow',
        ])
        if len(ways_to_create.intersection(payload)) == 0:
            message = "One parameter among - %s - must be specified" % ", ".join(ways_to_create)
            raise exceptions.RequestParameterMissingException(message)

        if len(ways_to_create.intersection(payload)) > 1:
            message = "Only one parameter among - %s - must be specified" % ", ".join(ways_to_create)
            raise exceptions.RequestParameterInvalidException(message)

        if 'installed_repository_file' in payload:
            workflow_controller = trans.webapp.controllers['workflow']
            result = workflow_controller.import_workflow(trans=trans,
                                                         cntrller='api',
                                                         **payload)
            return result

        if 'from_history_id' in payload:
            from_history_id = payload.get('from_history_id')
            from_history_id = self.decode_id(from_history_id)
            history = self.history_manager.get_accessible(from_history_id, trans.user, current_history=trans.history)

            job_ids = [self.decode_id(_) for _ in payload.get('job_ids', [])]
            dataset_ids = payload.get('dataset_ids', [])
            dataset_collection_ids = payload.get('dataset_collection_ids', [])
            workflow_name = payload['workflow_name']
            stored_workflow = extract_workflow(
                trans=trans,
                user=trans.get_user(),
                history=history,
                job_ids=job_ids,
                dataset_ids=dataset_ids,
                dataset_collection_ids=dataset_collection_ids,
                workflow_name=workflow_name,
            )
            item = stored_workflow.to_dict(value_mapper={'id': trans.security.encode_id})
            item['url'] = url_for('workflow', id=item['id'])
            return item

        if 'shared_workflow_id' in payload:
            workflow_id = payload['shared_workflow_id']
            return self.__api_import_shared_workflow(trans, workflow_id, payload)

        if 'workflow' in payload:
            return self.__api_import_new_workflow(trans, payload, **kwd)

        workflow_id = payload.get('workflow_id', None)
        if not workflow_id:
            message = "Invalid workflow_id specified."
            raise exceptions.RequestParameterInvalidException(message)

        # Get workflow + accessibility check.
        stored_workflow = self.__get_stored_accessible_workflow(trans, workflow_id)
        workflow = stored_workflow.latest_workflow

        run_configs = build_workflow_run_configs(trans, workflow, payload)
        assert len(run_configs) == 1
        run_config = run_configs[0]
        history = run_config.target_history

        # invoke may throw MessageExceptions on tool erors, failure
        # to match up inputs, etc...
        outputs, invocation = invoke(
            trans=trans,
            workflow=workflow,
            workflow_run_config=run_config,
            populate_state=True,
        )
        trans.sa_session.flush()

        # Build legacy output - should probably include more information from
        # outputs.
        rval = {}
        rval['history'] = trans.security.encode_id(history.id)
        rval['outputs'] = []
        for step in workflow.steps:
            if step.type == 'tool' or step.type is None:
                for v in outputs[step.id].values():
                    rval['outputs'].append(trans.security.encode_id(v.id))

        # Newer version of this API just returns the invocation as a dict, to
        # facilitate migration - produce the newer style response and blend in
        # the older information.
        invocation_response = self.__encode_invocation(trans, invocation, step_details=kwd.get('step_details', False))
        invocation_response.update(rval)
        return invocation_response

    @expose_api
    def workflow_dict(self, trans, workflow_id, **kwd):
        """
        GET /api/workflows/{encoded_workflow_id}/download
        Returns a selected workflow as a json dictionary.
        """
        stored_workflow = self.__get_stored_accessible_workflow(trans, workflow_id)

        style = kwd.get("style", "export")
        download_format = kwd.get('format')
        ret_dict = self.workflow_contents_manager.workflow_to_dict(trans, stored_workflow, style=style)
        if download_format == 'json-download':
            sname = stored_workflow.name
            sname = ''.join(c in util.FILENAME_VALID_CHARS and c or '_' for c in sname)[0:150]
            trans.response.headers["Content-Disposition"] = 'attachment; filename="Galaxy-Workflow-%s.ga"' % (sname)
            trans.response.set_content_type('application/galaxy-archive')
        return ret_dict

    @expose_api
    def delete(self, trans, id, **kwd):
        """
        DELETE /api/workflows/{encoded_workflow_id}
        Deletes a specified workflow
        Author: rpark

        copied from galaxy.web.controllers.workflows.py (delete)
        """
        workflow_id = id

        try:
            stored_workflow = trans.sa_session.query(self.app.model.StoredWorkflow).get(self.decode_id(workflow_id))
        except Exception as e:
            trans.response.status = 400
            return ("Workflow with ID='%s' can not be found\n Exception: %s") % (workflow_id, str(e))

        # check to see if user has permissions to selected workflow
        if stored_workflow.user != trans.user and not trans.user_is_admin():
            trans.response.status = 403
            return("Workflow is not owned by current user")

        # Mark a workflow as deleted
        stored_workflow.deleted = True
        trans.sa_session.flush()

        # TODO: Unsure of response message to let api know that a workflow was successfully deleted
        return ("Workflow '%s' successfully deleted" % stored_workflow.name)

    @expose_api
    def import_new_workflow_deprecated(self, trans, payload, **kwd):
        """
        POST /api/workflows/upload
        Importing dynamic workflows from the api. Return newly generated workflow id.
        Author: rpark

        # currently assumes payload['workflow'] is a json representation of a workflow to be inserted into the database

        Deprecated in favor to POST /api/workflows with encoded 'workflow' in
        payload the same way.
        """
        return self.__api_import_new_workflow(trans, payload, **kwd)

    @expose_api
    def update(self, trans, id, payload, **kwds):
        """
        * PUT /api/workflows/{id}
            updates the workflow stored with ``id``

        :type   id:      str
        :param  id:      the encoded id of the workflow to update
        :type   payload: dict
        :param  payload: a dictionary containing any or all the
            * workflow   the json description of the workflow as would be
                         produced by GET workflows/<id>/download or
                         given to `POST workflows`

                         The workflow contents will be updated to target
                         this.

            * name       optional string name for the workflow, if not present in payload,
                         name defaults to existing name
            * annotation optional string annotation for the workflow, if not present in payload,
                         annotation defaults to existing annotation
            * menu_entry optional boolean marking if the workflow should appear in the user's menu,
                         if not present, workflow menu entries are not modified

        :rtype:     dict
        :returns:   serialized version of the workflow
        """
        stored_workflow = self.__get_stored_workflow(trans, id)
        workflow_dict = payload.get('workflow')
        if workflow_dict:
            new_workflow_name = payload.get('name') or workflow_dict.get('name')
            if new_workflow_name:
                stored_workflow.name = sanitize_html(new_workflow_name)

            if 'annotation' in payload:
                newAnnotation = sanitize_html(payload['annotation'])
                self.add_item_annotation(trans.sa_session, trans.get_user(), stored_workflow, newAnnotation)

            if 'menu_entry' in payload or 'show_in_tool_panel' in workflow_dict:
                if payload.get('menu_entry') or workflow_dict.get('show_in_tool_panel'):
                    menuEntry = model.StoredWorkflowMenuEntry()
                    menuEntry.stored_workflow = stored_workflow
                    trans.get_user().stored_workflow_menu_entries.append(menuEntry)
                else:
                    # remove if in list
                    entries = {x.stored_workflow_id: x for x in trans.get_user().stored_workflow_menu_entries}
                    if (trans.security.decode_id(id) in entries):
                        trans.get_user().stored_workflow_menu_entries.remove(entries[trans.security.decode_id(id)])
            # set tags
            trans.app.tag_handler.set_tags_from_list(user=trans.user, item=stored_workflow, new_tags_list=workflow_dict.get('tags', []))

            if 'steps' in workflow_dict:
                try:
                    workflow, errors = self.workflow_contents_manager.update_workflow_from_dict(
                        trans,
                        stored_workflow,
                        workflow_dict,
                    )
                except workflows.MissingToolsException:
                    raise exceptions.MessageException("This workflow contains missing tools. It cannot be saved until they have been removed from the workflow or installed.")
            else:
                # We only adjusted tags and menu entry
                return payload
        else:
            message = "Updating workflow requires dictionary containing 'workflow' attribute with new JSON description."
            raise exceptions.RequestParameterInvalidException(message)
        return self.workflow_contents_manager.workflow_to_dict(trans, stored_workflow, style="instance")

    @expose_api
    def build_module(self, trans, payload={}):
        """
        POST /api/workflows/build_module
        Builds module models for the workflow editor.
        """
        inputs = payload.get('inputs', {})
        module = module_factory.from_dict(trans, payload)
        module_state = {}
        populate_state(trans, module.get_inputs(), inputs, module_state, check=False)
        module.recover_state(module_state)
        return {
            'label'             : inputs.get('__label', ''),
            'annotation'        : inputs.get('__annotation', ''),
            'name'              : module.get_name(),
            'tool_state'        : module.get_state(),
            'data_inputs'       : module.get_data_inputs(),
            'data_outputs'      : module.get_data_outputs(),
            'config_form'       : module.get_config_form(),
            'post_job_actions'  : module.get_post_job_actions(inputs)
        }

    #
    # -- Helper methods --
    #
    def _get_tool(self, id, tool_version=None, user=None):
        id = unquote_plus(id)
        tool = self.app.toolbox.get_tool(id, tool_version)
        if not tool or not tool.allow_user_access(user):
            raise exceptions.ObjectNotFound("Could not find tool with id '%s'" % id)
        return tool

    def __api_import_new_workflow(self, trans, payload, **kwd):
        data = payload['workflow']

        import_tools = util.string_as_bool(payload.get("import_tools", False))
        if import_tools and not trans.user_is_admin():
            raise exceptions.AdminRequiredException()

        publish = util.string_as_bool(payload.get("publish", False))
        # If 'publish' set, default to importable.
        importable = util.string_as_bool(payload.get("importable", publish))
        # Galaxy will try to upgrade tool versions that don't match exactly during import,
        # this prevents that.
        exact_tools = util.string_as_bool(payload.get("exact_tools", False))

        if publish and not importable:
            raise exceptions.RequestParameterInvalidException("Published workflow must be importable.")

        from_dict_kwds = dict(
            source="API",
            publish=publish,
            exact_tools=exact_tools,
        )
        workflow, missing_tool_tups = self._workflow_from_dict(trans, data, **from_dict_kwds)

        if importable:
            self._make_item_accessible(trans.sa_session, workflow)
            trans.sa_session.flush()

        # galaxy workflow newly created id
        workflow_id = workflow.id
        # api encoded, id
        encoded_id = trans.security.encode_id(workflow_id)

        # return list
        rval = []

        item = workflow.to_dict(value_mapper={'id': trans.security.encode_id})
        item['url'] = url_for('workflow', id=encoded_id)
        item['owner'] = workflow.user.username
        item['number_of_steps'] = len(workflow.latest_workflow.steps)
        rval.append(item)

        #
        if import_tools:
            tools = {}
            for key in data['steps']:
                item = data['steps'][key]
                if item is not None:
                    if 'tool_shed_repository' in item:
                        tool_shed_repository = item['tool_shed_repository']
                        if 'owner' in tool_shed_repository and 'changeset_revision' in tool_shed_repository and 'name' in tool_shed_repository and 'tool_shed' in tool_shed_repository:
                            toolstr = tool_shed_repository['owner'] \
                                + tool_shed_repository['changeset_revision'] \
                                + tool_shed_repository['name'] \
                                + tool_shed_repository['tool_shed']
                            tools[toolstr] = tool_shed_repository
            irm = InstallRepositoryManager(self.app)
            for k in tools:
                item = tools[k]
                tool_shed_url = 'https://' + item['tool_shed'] + '/'
                name = item['name']
                owner = item['owner']
                changeset_revision = item['changeset_revision']
                irm.install(tool_shed_url,
                            name,
                            owner,
                            changeset_revision,
                            payload)
        return item

    @expose_api
    def import_shared_workflow_deprecated(self, trans, payload, **kwd):
        """
        POST /api/workflows/import
        Import a workflow shared by other users.

        :param  workflow_id:      the workflow id (required)
        :type   workflow_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        # Pull parameters out of payload.
        workflow_id = payload.get('workflow_id', None)
        if workflow_id is None:
            raise exceptions.ObjectAttributeMissingException("Missing required parameter 'workflow_id'.")
        self.__api_import_shared_workflow(trans, workflow_id, payload)

    def __api_import_shared_workflow(self, trans, workflow_id, payload, **kwd):
        try:
            stored_workflow = self.get_stored_workflow(trans, workflow_id, check_ownership=False)
        except:
            raise exceptions.ObjectNotFound("Malformed workflow id ( %s ) specified." % workflow_id)
        if stored_workflow.importable is False:
            raise exceptions.ItemAccessibilityException('The owner of this workflow has disabled imports via this link.')
        elif stored_workflow.deleted:
            raise exceptions.ItemDeletionException("You can't import this workflow because it has been deleted.")
        imported_workflow = self._import_shared_workflow(trans, stored_workflow)
        item = imported_workflow.to_dict(value_mapper={'id': trans.security.encode_id})
        encoded_id = trans.security.encode_id(imported_workflow.id)
        item['url'] = url_for('workflow', id=encoded_id)
        return item

    @expose_api
    def invoke(self, trans, workflow_id, payload, **kwd):
        """
        POST /api/workflows/{encoded_workflow_id}/invocations

        Schedule the workflow specified by `workflow_id` to run.
        """
        # /usage is awkward in this context but is consistent with the rest of
        # this module. Would prefer to redo it all to use /invocation(s).
        # Get workflow + accessibility check.
        stored_workflow = self.__get_stored_accessible_workflow(trans, workflow_id)
        workflow = stored_workflow.latest_workflow
        run_configs = build_workflow_run_configs(trans, workflow, payload)
        is_batch = payload.get('batch')
        if not is_batch and len(run_configs) != 1:
            raise exceptions.RequestParameterInvalidException("Must specify 'batch' to use batch parameters.")

        invocations = []
        for run_config in run_configs:
            workflow_scheduler_id = payload.get('scheduler', None)
            # TODO: workflow scheduler hints
            work_request_params = dict(scheduler=workflow_scheduler_id)
            workflow_invocation = queue_invoke(
                trans=trans,
                workflow=workflow,
                workflow_run_config=run_config,
                request_params=work_request_params
            )
            invocation = self.encode_all_ids(trans, workflow_invocation.to_dict(), recursive=True)
            invocations.append(invocation)

        if is_batch:
            return invocations
        else:
            return invocations[0]

    @expose_api
    def index_invocations(self, trans, workflow_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations

        Get the list of the workflow invocations

        :param  workflow_id:      the workflow id (required)
        :type   workflow_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        stored_workflow = self.__get_stored_workflow(trans, workflow_id)
        results = self.workflow_manager.build_invocations_query(trans, stored_workflow.id)
        out = []
        for r in results:
            out.append(self.__encode_invocation(trans, r, view="collection"))
        return out

    @expose_api
    def show_invocation(self, trans, workflow_id, invocation_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}
        Get detailed description of workflow invocation

        :param  workflow_id:        the workflow id (required)
        :type   workflow_id:        str

        :param  invocation_id:      the invocation id (required)
        :type   invocation_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_workflow_invocation_id = self.decode_id(invocation_id)
        workflow_invocation = self.workflow_manager.get_invocation(trans, decoded_workflow_invocation_id)
        if workflow_invocation:
            return self.__encode_invocation(trans, workflow_invocation, step_details=kwd.get('step_details', False))
        return None

    @expose_api
    def cancel_invocation(self, trans, workflow_id, invocation_id, **kwd):
        """
        DELETE /api/workflows/{workflow_id}/invocations/{invocation_id}
        Cancel the specified workflow invocation.

        :param  workflow_id:      the workflow id (required)
        :type   workflow_id:      str

        :param  invocation_id:      the usage id (required)
        :type   invocation_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_workflow_invocation_id = self.decode_id(invocation_id)
        workflow_invocation = self.workflow_manager.cancel_invocation(trans, decoded_workflow_invocation_id)
        return self.__encode_invocation(trans, workflow_invocation)

    @expose_api
    def invocation_step(self, trans, workflow_id, invocation_id, step_id, **kwd):
        """
        GET /api/workflows/{workflow_id}/invocations/{invocation_id}/steps/{step_id}

        :param  workflow_id:        the workflow id (required)
        :type   workflow_id:        str

        :param  invocation_id:      the invocation id (required)
        :type   invocation_id:      str

        :param  step_id:      encoded id of the WorkflowInvocationStep (required)
        :type   step_id:      str

        :param  payload:       payload containing update action information
                               for running workflow.

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_invocation_step_id = self.decode_id(step_id)
        invocation_step = self.workflow_manager.get_invocation_step(
            trans,
            decoded_invocation_step_id
        )
        return self.__encode_invocation_step(trans, invocation_step)

    @expose_api
    def update_invocation_step(self, trans, workflow_id, invocation_id, step_id, payload, **kwd):
        """
        PUT /api/workflows/{workflow_id}/invocations/{invocation_id}/steps/{step_id}
        Update state of running workflow step invocation - still very nebulous
        but this would be for stuff like confirming paused steps can proceed
        etc....


        :param  workflow_id:      the workflow id (required)
        :type   workflow_id:      str

        :param  invocation_id:      the usage id (required)
        :type   invocation_id:      str

        :param  step_id:      encoded id of the WorkflowInvocationStep (required)
        :type   step_id:      str

        :raises: exceptions.MessageException, exceptions.ObjectNotFound
        """
        decoded_invocation_step_id = self.decode_id(step_id)
        action = payload.get("action", None)

        invocation_step = self.workflow_manager.update_invocation_step(
            trans,
            decoded_invocation_step_id,
            action=action,
        )
        return self.__encode_invocation_step(trans, invocation_step)

    def __encode_invocation_step(self, trans, invocation_step):
        return self.encode_all_ids(
            trans,
            invocation_step.to_dict('element'),
            True
        )

    def __get_stored_accessible_workflow(self, trans, workflow_id):
        return self.workflow_manager.get_stored_accessible_workflow(trans, workflow_id)

    def __get_stored_workflow(self, trans, workflow_id):
        return self.workflow_manager.get_stored_workflow(trans, workflow_id)

    def __encode_invocation(self, trans, invocation, view="element", step_details=False):
        return self.encode_all_ids(
            trans,
            invocation.to_dict(view, step_details=step_details),
            True
        )
