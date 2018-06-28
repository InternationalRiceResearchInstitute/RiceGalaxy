import logging
import os
import re
import shutil

from six.moves import configparser
from six.moves.urllib.error import HTTPError
from sqlalchemy import and_, false, or_

import tool_shed.dependencies.repository
import tool_shed.util.metadata_util as metadata_util
from galaxy import util
from galaxy import web
from galaxy.web.form_builder import build_select_field
from tool_shed.util import basic_util, common_util, encoding_util, hg_util
from tool_shed.util.web_util import escape

log = logging.getLogger(__name__)

VALID_REPOSITORYNAME_RE = re.compile("^[a-z0-9\_]+$")


def build_allow_push_select_field(trans, current_push_list, selected_value='none'):
    options = []
    for user in trans.sa_session.query(trans.model.User):
        if user.username not in current_push_list:
            options.append(user)
    return build_select_field(trans,
                              objs=options,
                              label_attr='username',
                              select_field_name='allow_push',
                              selected_value=selected_value,
                              refresh_on_change=False,
                              multiple=True)


def change_repository_name_in_hgrc_file(hgrc_file, new_name):
    config = configparser.ConfigParser()
    config.read(hgrc_file)
    config.read(hgrc_file)
    config.set('web', 'name', new_name)
    new_file = open(hgrc_file, 'wb')
    config.write(new_file)
    new_file.close()


def check_for_updates(app, model, repository_id=None):
    message = ''
    status = 'ok'
    if repository_id is None:
        success_count = 0
        repository_names_not_updated = []
        updated_count = 0
        for repository in model.context.query(model.ToolShedRepository) \
                                       .filter(model.ToolShedRepository.table.c.deleted == false()):
            ok, updated = \
                check_or_update_tool_shed_status_for_installed_repository(app, repository)
            if ok:
                success_count += 1
            else:
                repository_names_not_updated.append('<b>%s</b>' % escape(str(repository.name)))
            if updated:
                updated_count += 1
        message = "Checked the status in the tool shed for %d repositories.  " % success_count
        message += "Updated the tool shed status for %d repositories.  " % updated_count
        if repository_names_not_updated:
            message += "Unable to retrieve status from the tool shed for the following repositories:\n"
            message += ", ".join(repository_names_not_updated)
    else:
        repository = get_tool_shed_repository_by_id(app, repository_id)
        ok, updated = \
            check_or_update_tool_shed_status_for_installed_repository(app, repository)
        if ok:
            if updated:
                message = "The tool shed status for repository <b>%s</b> has been updated." % escape(str(repository.name))
            else:
                message = "The status has not changed in the tool shed for repository <b>%s</b>." % escape(str(repository.name))
        else:
            message = "Unable to retrieve status from the tool shed for repository <b>%s</b>." % escape(str(repository.name))
            status = 'error'
    return message, status


def check_or_update_tool_shed_status_for_installed_repository(app, repository):
    updated = False
    tool_shed_status_dict = get_tool_shed_status_for_installed_repository(app, repository)
    if tool_shed_status_dict:
        ok = True
        if tool_shed_status_dict != repository.tool_shed_status:
            repository.tool_shed_status = tool_shed_status_dict
            app.install_model.context.add(repository)
            app.install_model.context.flush()
            updated = True
    else:
        ok = False
    return ok, updated


def create_or_update_tool_shed_repository(app, name, description, installed_changeset_revision, ctx_rev, repository_clone_url,
                                          metadata_dict, status, current_changeset_revision=None, owner='', dist_to_shed=False):
    """
    Update a tool shed repository record in the Galaxy database with the new information received.
    If a record defined by the received tool shed, repository name and owner does not exist, create
    a new record with the received information.
    """
    # The received value for dist_to_shed will be True if the ToolMigrationManager is installing a repository
    # that contains tools or datatypes that used to be in the Galaxy distribution, but have been moved
    # to the main Galaxy tool shed.
    if current_changeset_revision is None:
        # The current_changeset_revision is not passed if a repository is being installed for the first
        # time.  If a previously installed repository was later uninstalled, this value should be received
        # as the value of that change set to which the repository had been updated just prior to it being
        # uninstalled.
        current_changeset_revision = installed_changeset_revision
    context = app.install_model.context
    tool_shed = get_tool_shed_from_clone_url(repository_clone_url)
    if not owner:
        owner = get_repository_owner_from_clone_url(repository_clone_url)
    includes_datatypes = 'datatypes' in metadata_dict
    if status in [app.install_model.ToolShedRepository.installation_status.DEACTIVATED]:
        deleted = True
        uninstalled = False
    elif status in [app.install_model.ToolShedRepository.installation_status.UNINSTALLED]:
        deleted = True
        uninstalled = True
    else:
        deleted = False
        uninstalled = False
    tool_shed_repository = \
        get_installed_repository(app, tool_shed=tool_shed, name=name, owner=owner, installed_changeset_revision=installed_changeset_revision, refresh=True)
    if tool_shed_repository:
        log.debug("Updating an existing row for repository '%s' in the tool_shed_repository table, status set to '%s'." %
                  (str(name), str(status)))
        tool_shed_repository.description = description
        tool_shed_repository.changeset_revision = current_changeset_revision
        tool_shed_repository.ctx_rev = ctx_rev
        tool_shed_repository.metadata = metadata_dict
        tool_shed_repository.includes_datatypes = includes_datatypes
        tool_shed_repository.deleted = deleted
        tool_shed_repository.uninstalled = uninstalled
        tool_shed_repository.status = status
    else:
        log.debug("Adding new row for repository '%s' in the tool_shed_repository table, status set to '%s'." %
                  (str(name), str(status)))
        tool_shed_repository = \
            app.install_model.ToolShedRepository(tool_shed=tool_shed,
                                                 name=name,
                                                 description=description,
                                                 owner=owner,
                                                 installed_changeset_revision=installed_changeset_revision,
                                                 changeset_revision=current_changeset_revision,
                                                 ctx_rev=ctx_rev,
                                                 metadata=metadata_dict,
                                                 includes_datatypes=includes_datatypes,
                                                 dist_to_shed=dist_to_shed,
                                                 deleted=deleted,
                                                 uninstalled=uninstalled,
                                                 status=status)
    context.add(tool_shed_repository)
    context.flush()
    return tool_shed_repository


def create_repo_info_dict(app, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_name=None,
                          repository=None, repository_metadata=None, tool_dependencies=None, repository_dependencies=None):
    """
    Return a dictionary that includes all of the information needed to install a repository into a local
    Galaxy instance.  The dictionary will also contain the recursive list of repository dependencies defined
    for the repository, as well as the defined tool dependencies.

    This method is called from Galaxy under four scenarios:
    1. During the tool shed repository installation process via the tool shed's get_repository_information()
    method.  In this case both the received repository and repository_metadata will be objects, but
    tool_dependencies and repository_dependencies will be None.
    2. When getting updates for an installed repository where the updates include newly defined repository
    dependency definitions.  This scenario is similar to 1. above. The tool shed's get_repository_information()
    method is the caller, and both the received repository and repository_metadata will be objects, but
    tool_dependencies and repository_dependencies will be None.
    3. When a tool shed repository that was uninstalled from a Galaxy instance is being reinstalled with no
    updates available.  In this case, both repository and repository_metadata will be None, but tool_dependencies
    and repository_dependencies will be objects previously retrieved from the tool shed if the repository includes
    definitions for them.
    4. When a tool shed repository that was uninstalled from a Galaxy instance is being reinstalled with updates
    available.  In this case, this method is reached via the tool shed's get_updated_repository_information()
    method, and both repository and repository_metadata will be objects but tool_dependencies and
    repository_dependencies will be None.
    """
    repo_info_dict = {}
    repository = get_repository_by_name_and_owner(app, repository_name, repository_owner)
    if app.name == 'tool_shed':
        # We're in the tool shed.
        repository_metadata = metadata_util.get_repository_metadata_by_changeset_revision(app,
                                                                                 app.security.encode_id(repository.id),
                                                                                 changeset_revision)
        if repository_metadata:
            metadata = repository_metadata.metadata
            if metadata:
                tool_shed_url = str(web.url_for('/', qualified=True)).rstrip('/')
                rb = tool_shed.dependencies.repository.relation_builder.RelationBuilder(app, repository, repository_metadata, tool_shed_url)
                # Get a dictionary of all repositories upon which the contents of the received repository depends.
                repository_dependencies = rb.get_repository_dependencies_for_changeset_revision()
                tool_dependencies = metadata.get('tool_dependencies', {})
    if tool_dependencies:
        new_tool_dependencies = {}
        for dependency_key, requirements_dict in tool_dependencies.items():
            if dependency_key in ['set_environment']:
                new_set_environment_dict_list = []
                for set_environment_dict in requirements_dict:
                    set_environment_dict['repository_name'] = repository_name
                    set_environment_dict['repository_owner'] = repository_owner
                    set_environment_dict['changeset_revision'] = changeset_revision
                    new_set_environment_dict_list.append(set_environment_dict)
                new_tool_dependencies[dependency_key] = new_set_environment_dict_list
            else:
                requirements_dict['repository_name'] = repository_name
                requirements_dict['repository_owner'] = repository_owner
                requirements_dict['changeset_revision'] = changeset_revision
                new_tool_dependencies[dependency_key] = requirements_dict
        tool_dependencies = new_tool_dependencies
    # Cast unicode to string, with the exception of description, since it is free text and can contain special characters.
    repo_info_dict[str(repository.name)] = (repository.description,
                                            str(repository_clone_url),
                                            str(changeset_revision),
                                            str(ctx_rev),
                                            str(repository_owner),
                                            repository_dependencies,
                                            tool_dependencies)
    return repo_info_dict


def create_repository_admin_role(app, repository):
    """
    Create a new role with name-spaced name based on the repository name and its owner's public user
    name.  This will ensure that the tole name is unique.
    """
    sa_session = app.model.context.current
    name = get_repository_admin_role_name(str(repository.name), str(repository.user.username))
    description = 'A user or group member with this role can administer this repository.'
    role = app.model.Role(name=name, description=description, type=app.model.Role.types.SYSTEM)
    sa_session.add(role)
    sa_session.flush()
    # Associate the role with the repository owner.
    app.model.UserRoleAssociation(repository.user, role)
    # Associate the role with the repository.
    rra = app.model.RepositoryRoleAssociation(repository, role)
    sa_session.add(rra)
    sa_session.flush()
    return role


def create_repository(app, name, type, description, long_description, user_id, category_ids=[], remote_repository_url=None, homepage_url=None):
    """Create a new ToolShed repository"""
    sa_session = app.model.context.current
    # Add the repository record to the database.
    repository = app.model.Repository(name=name,
                                      type=type,
                                      remote_repository_url=remote_repository_url,
                                      homepage_url=homepage_url,
                                      description=description,
                                      long_description=long_description,
                                      user_id=user_id)
    # Flush to get the id.
    sa_session.add(repository)
    sa_session.flush()
    # Create an admin role for the repository.
    create_repository_admin_role(app, repository)
    # Determine the repository's repo_path on disk.
    dir = os.path.join(app.config.file_path, *util.directory_hash_id(repository.id))
    # Create directory if it does not exist.
    if not os.path.exists(dir):
        os.makedirs(dir)
    # Define repo name inside hashed directory.
    repository_path = os.path.join(dir, "repo_%d" % repository.id)
    # Create local repository directory.
    if not os.path.exists(repository_path):
        os.makedirs(repository_path)
    # Create the local repository.
    hg_util.get_repo_for_repository(app, repository=None, repo_path=repository_path, create=True)
    # Add an entry in the hgweb.config file for the local repository.
    lhs = "repos/%s/%s" % (repository.user.username, repository.name)
    app.hgweb_config_manager.add_entry(lhs, repository_path)
    # Create a .hg/hgrc file for the local repository.
    hg_util.create_hgrc_file(app, repository)
    flush_needed = False
    if category_ids:
        # Create category associations
        for category_id in category_ids:
            category = sa_session.query(app.model.Category) \
                                 .get(app.security.decode_id(category_id))
            rca = app.model.RepositoryCategoryAssociation(repository, category)
            sa_session.add(rca)
            flush_needed = True
    if flush_needed:
        sa_session.flush()
    # Update the repository registry.
    app.repository_registry.add_entry(repository)
    message = "Repository <b>%s</b> has been created." % escape(str(repository.name))
    return repository, message


def extract_components_from_tuple(repository_components_tuple):
    '''Extract the repository components from the provided tuple in a backward-compatible manner.'''
    toolshed = repository_components_tuple[0]
    name = repository_components_tuple[1]
    owner = repository_components_tuple[2]
    changeset_revision = repository_components_tuple[3]
    components_list = [toolshed, name, owner, changeset_revision]
    if len(repository_components_tuple) == 5:
        toolshed, name, owner, changeset_revision, prior_installation_required = repository_components_tuple
        components_list = [toolshed, name, owner, changeset_revision, prior_installation_required]
    elif len(repository_components_tuple) == 6:
        toolshed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = repository_components_tuple
        components_list = [toolshed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td]
    return components_list


def generate_sharable_link_for_repository_in_tool_shed(repository, changeset_revision=None):
    """Generate the URL for sharing a repository that is in the tool shed."""
    base_url = web.url_for('/', qualified=True).rstrip('/')
    protocol, base = base_url.split('://')
    sharable_url = '%s://%s/view/%s/%s' % (protocol, base, repository.user.username, repository.name)
    if changeset_revision:
        sharable_url += '/%s' % changeset_revision
    return sharable_url


def generate_tool_shed_repository_install_dir(repository_clone_url, changeset_revision):
    """
    Generate a repository installation directory that guarantees repositories with the same
    name will always be installed in different directories.  The tool path will be of the form:
    <tool shed url>/repos/<repository owner>/<repository name>/<installed changeset revision>
    """
    tmp_url = common_util.remove_protocol_and_user_from_clone_url(repository_clone_url)
    # Now tmp_url is something like: bx.psu.edu:9009/repos/some_username/column
    items = tmp_url.split('/repos/')
    tool_shed_url = items[0]
    repo_path = items[1]
    tool_shed_url = common_util.remove_port_from_tool_shed_url(tool_shed_url)
    return '/'.join([tool_shed_url, 'repos', repo_path, changeset_revision])


def get_absolute_path_to_file_in_repository(repo_files_dir, file_name):
    """Return the absolute path to a specified disk file contained in a repository."""
    stripped_file_name = basic_util.strip_path(file_name)
    file_path = None
    for root, dirs, files in os.walk(repo_files_dir):
        if root.find('.hg') < 0:
            for name in files:
                if name == stripped_file_name:
                    return os.path.abspath(os.path.join(root, name))
    return file_path


def get_ids_of_tool_shed_repositories_being_installed(app, as_string=False):
    installing_repository_ids = []
    new_status = app.install_model.ToolShedRepository.installation_status.NEW
    cloning_status = app.install_model.ToolShedRepository.installation_status.CLONING
    setting_tool_versions_status = app.install_model.ToolShedRepository.installation_status.SETTING_TOOL_VERSIONS
    installing_dependencies_status = app.install_model.ToolShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES
    loading_datatypes_status = app.install_model.ToolShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES
    for tool_shed_repository in \
        app.install_model.context.query(app.install_model.ToolShedRepository) \
                                 .filter(or_(app.install_model.ToolShedRepository.status == new_status,
                                             app.install_model.ToolShedRepository.status == cloning_status,
                                             app.install_model.ToolShedRepository.status == setting_tool_versions_status,
                                             app.install_model.ToolShedRepository.status == installing_dependencies_status,
                                             app.install_model.ToolShedRepository.status == loading_datatypes_status)):
        installing_repository_ids.append(app.security.encode_id(tool_shed_repository.id))
    if as_string:
        return ','.join(installing_repository_ids)
    return installing_repository_ids


def get_installed_repository(app, tool_shed=None, name=None, owner=None, changeset_revision=None, installed_changeset_revision=None, repository_id=None, refresh=False):
    """
    Return a tool shed repository database record defined by the combination of a toolshed, repository name,
    repository owner and either current or originally installed changeset_revision.
    """
    # We store the port, if one exists, in the database.
    tool_shed = common_util.remove_protocol_from_tool_shed_url(tool_shed)
    if hasattr(app, 'tool_shed_repository_cache'):
        if refresh:
            app.tool_shed_repository_cache.rebuild()
        return app.tool_shed_repository_cache.get_installed_repository(tool_shed=tool_shed,
                                                                       name=name,
                                                                       owner=owner,
                                                                       installed_changeset_revision=installed_changeset_revision,
                                                                       changeset_revision=changeset_revision,
                                                                       repository_id=repository_id)
    query = app.install_model.context.query(app.install_model.ToolShedRepository)
    if repository_id:
        clause_list = [app.install_model.ToolShedRepository.table.c.id == repository_id]
    else:
        clause_list = [app.install_model.ToolShedRepository.table.c.tool_shed == tool_shed,
                       app.install_model.ToolShedRepository.table.c.name == name,
                       app.install_model.ToolShedRepository.table.c.owner == owner]
    if changeset_revision is not None:
        clause_list.append(app.install_model.ToolShedRepository.table.c.changeset_revision == changeset_revision)
    if installed_changeset_revision is not None:
        clause_list.append(app.install_model.ToolShedRepository.table.c.installed_changeset_revision == installed_changeset_revision)
    return query.filter(and_(*clause_list)).first()


def get_installed_tool_shed_repository(app, id):
    """Get a tool shed repository record from the Galaxy database defined by the id."""
    rval = []
    if isinstance(id, list):
        return_list = True
    else:
        id = [id]
        return_list = False
    if hasattr(app, 'tool_shed_repository_cache'):
        app.tool_shed_repository_cache.rebuild()
    repository_ids = [app.security.decode_id(i)for i in id]
    rval = [get_installed_repository(app=app, repository_id=repo_id) for repo_id in repository_ids]
    if return_list:
        return rval
    return rval[0]


def get_prior_import_or_install_required_dict(app, tsr_ids, repo_info_dicts):
    """
    This method is used in the Tool Shed when exporting a repository and its dependencies,
    and in Galaxy when a repository and its dependencies are being installed.  Return a
    dictionary whose keys are the received tsr_ids and whose values are a list of tsr_ids,
    each of which is contained in the received list of tsr_ids and whose associated repository
    must be imported or installed prior to the repository associated with the tsr_id key.
    """
    # Initialize the dictionary.
    prior_import_or_install_required_dict = {}
    for tsr_id in tsr_ids:
        prior_import_or_install_required_dict[tsr_id] = []
    # Inspect the repository dependencies for each repository about to be installed and populate the dictionary.
    for repo_info_dict in repo_info_dicts:
        repository, repository_dependencies = get_repository_and_repository_dependencies_from_repo_info_dict(app, repo_info_dict)
        if repository:
            encoded_repository_id = app.security.encode_id(repository.id)
            if encoded_repository_id in tsr_ids:
                # We've located the database table record for one of the repositories we're about to install, so find out if it has any repository
                # dependencies that require prior installation.
                prior_import_or_install_ids = get_repository_ids_requiring_prior_import_or_install(app, tsr_ids, repository_dependencies)
                prior_import_or_install_required_dict[encoded_repository_id] = prior_import_or_install_ids
    return prior_import_or_install_required_dict


def get_repo_info_dict(app, user, repository_id, changeset_revision):
    repository = get_repository_in_tool_shed(app, repository_id)
    repo = hg_util.get_repo_for_repository(app, repository=repository, repo_path=None, create=False)
    repository_clone_url = common_util.generate_clone_url_for_repository_in_tool_shed(user, repository)
    repository_metadata = metadata_util.get_repository_metadata_by_changeset_revision(app,
                                                                                      repository_id,
                                                                                      changeset_revision)
    if not repository_metadata:
        # The received changeset_revision is no longer installable, so get the next changeset_revision
        # in the repository's changelog.  This generally occurs only with repositories of type
        # repository_suite_definition or tool_dependency_definition.
        next_downloadable_changeset_revision = \
            metadata_util.get_next_downloadable_changeset_revision(repository, repo, changeset_revision)
        if next_downloadable_changeset_revision and next_downloadable_changeset_revision != changeset_revision:
            repository_metadata = metadata_util.get_repository_metadata_by_changeset_revision(app,
                                                                                              repository_id,
                                                                                              next_downloadable_changeset_revision)
    if repository_metadata:
        # For now, we'll always assume that we'll get repository_metadata, but if we discover our assumption
        # is not valid we'll have to enhance the callers to handle repository_metadata values of None in the
        # returned repo_info_dict.
        metadata = repository_metadata.metadata
        if 'tools' in metadata:
            includes_tools = True
        else:
            includes_tools = False
        includes_tools_for_display_in_tool_panel = repository_metadata.includes_tools_for_display_in_tool_panel
        repository_dependencies_dict = metadata.get('repository_dependencies', {})
        repository_dependencies = repository_dependencies_dict.get('repository_dependencies', [])
        has_repository_dependencies, has_repository_dependencies_only_if_compiling_contained_td = \
            get_repository_dependency_types(repository_dependencies)
        if 'tool_dependencies' in metadata:
            includes_tool_dependencies = True
        else:
            includes_tool_dependencies = False
    else:
        # Here's where we may have to handle enhancements to the callers. See above comment.
        includes_tools = False
        has_repository_dependencies = False
        has_repository_dependencies_only_if_compiling_contained_td = False
        includes_tool_dependencies = False
        includes_tools_for_display_in_tool_panel = False
    ctx = hg_util.get_changectx_for_changeset(repo, changeset_revision)
    repo_info_dict = create_repo_info_dict(app=app,
                                           repository_clone_url=repository_clone_url,
                                           changeset_revision=changeset_revision,
                                           ctx_rev=str(ctx.rev()),
                                           repository_owner=repository.user.username,
                                           repository_name=repository.name,
                                           repository=repository,
                                           repository_metadata=repository_metadata,
                                           tool_dependencies=None,
                                           repository_dependencies=None)
    return repo_info_dict, includes_tools, includes_tool_dependencies, includes_tools_for_display_in_tool_panel, \
        has_repository_dependencies, has_repository_dependencies_only_if_compiling_contained_td


def get_repo_info_tuple_contents(repo_info_tuple):
    """Take care in handling the repo_info_tuple as it evolves over time as new tool shed features are introduced."""
    if len(repo_info_tuple) == 6:
        description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, tool_dependencies = repo_info_tuple
        repository_dependencies = None
    elif len(repo_info_tuple) == 7:
        description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, tool_dependencies = repo_info_tuple
    return description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, tool_dependencies


def get_repositories_by_category(app, category_id, installable=False):
    sa_session = app.model.context.current
    resultset = sa_session.query(app.model.Category).get(category_id)
    repositories = []
    default_value_mapper = {'id': app.security.encode_id, 'user_id': app.security.encode_id}
    for row in resultset.repositories:
        repository_dict = row.repository.to_dict(value_mapper=default_value_mapper)
        repository_dict['metadata'] = {}
        for changeset, changehash in row.repository.installable_revisions(app):
            encoded_id = app.security.encode_id(row.repository.id)
            metadata = metadata_util.get_repository_metadata_by_changeset_revision(app, encoded_id, changehash)
            repository_dict['metadata']['%s:%s' % (changeset, changehash)] = metadata.to_dict(value_mapper=default_value_mapper)
        if installable:
            if len(row.repository.installable_revisions(app)):
                repositories.append(repository_dict)
        else:
            repositories.append(repository_dict)
    return repositories


def get_repository_admin_role_name(repository_name, repository_owner):
    return '%s_%s_admin' % (str(repository_name), str(repository_owner))


def get_repository_and_repository_dependencies_from_repo_info_dict(app, repo_info_dict):
    """Return a tool_shed_repository or repository record defined by the information in the received repo_info_dict."""
    repository_name = list(repo_info_dict.keys())[0]
    repo_info_tuple = repo_info_dict[repository_name]
    description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, tool_dependencies = \
        get_repo_info_tuple_contents(repo_info_tuple)
    if hasattr(app, "install_model"):
        # In a tool shed client (Galaxy, or something install repositories like Galaxy)
        tool_shed = get_tool_shed_from_clone_url(repository_clone_url)
        repository = get_repository_for_dependency_relationship(app, tool_shed, repository_name, repository_owner, changeset_revision)
    else:
        # We're in the tool shed.
        repository = get_repository_by_name_and_owner(app, repository_name, repository_owner)
    return repository, repository_dependencies


def get_repository_by_id(app, id):
    """Get a repository from the database via id."""
    if is_tool_shed_client(app):
        return app.install_model.context.query(app.install_model.ToolShedRepository).get(app.security.decode_id(id))
    else:
        sa_session = app.model.context.current
        return sa_session.query(app.model.Repository).get(app.security.decode_id(id))


def get_repository_by_name_and_owner(app, name, owner):
    """Get a repository from the database via name and owner"""
    repository_query = get_repository_query(app)
    if is_tool_shed_client(app):
        return repository_query \
            .filter(and_(app.install_model.ToolShedRepository.table.c.name == name,
                         app.install_model.ToolShedRepository.table.c.owner == owner)) \
            .first()
    # We're in the tool shed.
    user = common_util.get_user_by_username(app, owner)
    if user:
        return repository_query \
            .filter(and_(app.model.Repository.table.c.name == name,
                         app.model.Repository.table.c.user_id == user.id)) \
            .first()
    return None


def get_repository_by_name(app, name):
    """Get a repository from the database via name."""
    return get_repository_query(app).filter_by(name=name).first()


def get_repository_dependency_types(repository_dependencies):
    """
    Inspect the received list of repository_dependencies tuples and return boolean values
    for has_repository_dependencies and has_repository_dependencies_only_if_compiling_contained_td.
    """
    # Set has_repository_dependencies, which will be True only if at least one repository_dependency
    # is defined with the value of
    # only_if_compiling_contained_td as False.
    has_repository_dependencies = False
    for rd_tup in repository_dependencies:
        tool_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
            common_util.parse_repository_dependency_tuple(rd_tup)
        if not util.asbool(only_if_compiling_contained_td):
            has_repository_dependencies = True
            break
    # Set has_repository_dependencies_only_if_compiling_contained_td, which will be True only if at
    # least one repository_dependency is defined with the value of only_if_compiling_contained_td as True.
    has_repository_dependencies_only_if_compiling_contained_td = False
    for rd_tup in repository_dependencies:
        tool_shed, name, owner, changeset_revision, prior_installation_required, only_if_compiling_contained_td = \
            common_util.parse_repository_dependency_tuple(rd_tup)
        if util.asbool(only_if_compiling_contained_td):
            has_repository_dependencies_only_if_compiling_contained_td = True
            break
    return has_repository_dependencies, has_repository_dependencies_only_if_compiling_contained_td


def get_repository_for_dependency_relationship(app, tool_shed, name, owner, changeset_revision):
    """
    Return an installed tool_shed_repository database record that is defined by either the current changeset
    revision or the installed_changeset_revision.
    """
    # This method is used only in Galaxy, not the Tool Shed.  We store the port (if one exists) in the database.
    tool_shed = common_util.remove_protocol_from_tool_shed_url(tool_shed)
    if tool_shed is None or name is None or owner is None or changeset_revision is None:
        message = "Unable to retrieve the repository record from the database because one or more of the following "
        message += "required parameters is None: tool_shed: %s, name: %s, owner: %s, changeset_revision: %s " % \
            (str(tool_shed), str(name), str(owner), str(changeset_revision))
        raise Exception(message)
    app.tool_shed_repository_cache.rebuild()
    repository = get_installed_repository(app=app,
                                          tool_shed=tool_shed,
                                          name=name,
                                          owner=owner,
                                          installed_changeset_revision=changeset_revision)
    if not repository:
        repository = get_installed_repository(app=app,
                                              tool_shed=tool_shed,
                                              name=name,
                                              owner=owner,
                                              changeset_revision=changeset_revision)
    if not repository:
        tool_shed_url = common_util.get_tool_shed_url_from_tool_shed_registry(app, tool_shed)
        repository_clone_url = os.path.join(tool_shed_url, 'repos', owner, name)
        repo_info_tuple = (None, repository_clone_url, changeset_revision, None, owner, None, None)
        repository, pcr = repository_was_previously_installed(app, tool_shed_url, name, repo_info_tuple)
    if not repository:
        # The received changeset_revision is no longer installable, so get the next changeset_revision
        # in the repository's changelog in the tool shed that is associated with repository_metadata.
        tool_shed_url = common_util.get_tool_shed_url_from_tool_shed_registry(app, tool_shed)
        params = dict(name=name, owner=owner, changeset_revision=changeset_revision)
        pathspec = ['repository', 'next_installable_changeset_revision']
        text = util.url_get(tool_shed_url, password_mgr=app.tool_shed_registry.url_auth(tool_shed_url), pathspec=pathspec, params=params)
        if text:
            repository = get_installed_repository(app=app,
                                                  tool_shed=tool_shed,
                                                  name=name,
                                                  owner=owner,
                                                  changeset_revision=text)
    return repository


def get_repository_ids_requiring_prior_import_or_install(app, tsr_ids, repository_dependencies):
    """
    This method is used in the Tool Shed when exporting a repository and its dependencies,
    and in Galaxy when a repository and its dependencies are being installed.  Inspect the
    received repository_dependencies and determine if the encoded id of each required
    repository is in the received tsr_ids.  If so, then determine whether that required
    repository should be imported / installed prior to its dependent repository.  Return a
    list of encoded repository ids, each of which is contained in the received list of tsr_ids,
    and whose associated repositories must be imported / installed prior to the dependent
    repository associated with the received repository_dependencies.
    """
    prior_tsr_ids = []
    if repository_dependencies:
        for key, rd_tups in repository_dependencies.items():
            if key in ['description', 'root_key']:
                continue
            for rd_tup in rd_tups:
                tool_shed, \
                    name, \
                    owner, \
                    changeset_revision, \
                    prior_installation_required, \
                    only_if_compiling_contained_td = \
                    common_util.parse_repository_dependency_tuple(rd_tup)
                # If only_if_compiling_contained_td is False, then the repository dependency
                # is not required to be installed prior to the dependent repository even if
                # prior_installation_required is True.  This is because the only meaningful
                # content of the repository dependency is its contained tool dependency, which
                # is required in order to compile the dependent repository's tool dependency.
                # In the scenario where the repository dependency is not installed prior to the
                # dependent repository's tool dependency compilation process, the tool dependency
                # compilation framework will install the repository dependency prior to compilation
                # of the dependent repository's tool dependency.
                if not util.asbool(only_if_compiling_contained_td):
                    if util.asbool(prior_installation_required):
                        if is_tool_shed_client(app):
                            # We store the port, if one exists, in the database.
                            tool_shed = common_util.remove_protocol_from_tool_shed_url(tool_shed)
                            repository = get_repository_for_dependency_relationship(app,
                                                                                    tool_shed,
                                                                                    name,
                                                                                    owner,
                                                                                    changeset_revision)
                        else:
                            repository = get_repository_by_name_and_owner(app, name, owner)
                        if repository:
                            encoded_repository_id = app.security.encode_id(repository.id)
                            if encoded_repository_id in tsr_ids:
                                prior_tsr_ids.append(encoded_repository_id)
    return prior_tsr_ids


def get_repository_in_tool_shed(app, id):
    """Get a repository on the tool shed side from the database via id."""
    return get_repository_query(app).get(app.security.decode_id(id))


def get_repository_owner(cleaned_repository_url):
    """Gvien a "cleaned" repository clone URL, return the owner of the repository."""
    items = cleaned_repository_url.split('/repos/')
    repo_path = items[1]
    if repo_path.startswith('/'):
        repo_path = repo_path.replace('/', '', 1)
    return repo_path.lstrip('/').split('/')[0]


def get_repository_owner_from_clone_url(repository_clone_url):
    """Given a repository clone URL, return the owner of the repository."""
    tmp_url = common_util.remove_protocol_and_user_from_clone_url(repository_clone_url)
    return get_repository_owner(tmp_url)


def get_repository_query(app):
    if is_tool_shed_client(app):
        query = app.install_model.context.query(app.install_model.ToolShedRepository)
    else:
        query = app.model.context.query(app.model.Repository)
    return query


def get_role_by_id(app, role_id):
    """Get a Role from the database by id."""
    sa_session = app.model.context.current
    return sa_session.query(app.model.Role).get(app.security.decode_id(role_id))


def get_tool_shed_from_clone_url(repository_clone_url):
    tmp_url = common_util.remove_protocol_and_user_from_clone_url(repository_clone_url)
    return tmp_url.split('/repos/')[0].rstrip('/')


def get_tool_shed_repository_by_id(app, repository_id):
    """Return a tool shed repository database record defined by the id."""
    # This method is used only in Galaxy, not the tool shed.
    return app.install_model.context.query(app.install_model.ToolShedRepository) \
                                    .filter(app.install_model.ToolShedRepository.table.c.id == app.security.decode_id(repository_id)) \
                                    .first()


def get_tool_shed_repository_status_label(app, tool_shed_repository=None, name=None, owner=None, changeset_revision=None, repository_clone_url=None):
    """Return a color-coded label for the status of the received tool-shed_repository installed into Galaxy."""
    if tool_shed_repository is None:
        if name is not None and owner is not None and repository_clone_url is not None:
            tool_shed = get_tool_shed_from_clone_url(repository_clone_url)
            tool_shed_repository = get_installed_repository(app,
                                                            tool_shed=tool_shed,
                                                            name=name,
                                                            owner=owner,
                                                            installed_changeset_revision=changeset_revision)
    if tool_shed_repository:
        status_label = tool_shed_repository.status
        if tool_shed_repository.status in [app.install_model.ToolShedRepository.installation_status.CLONING,
                                           app.install_model.ToolShedRepository.installation_status.SETTING_TOOL_VERSIONS,
                                           app.install_model.ToolShedRepository.installation_status.INSTALLING_REPOSITORY_DEPENDENCIES,
                                           app.install_model.ToolShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES,
                                           app.install_model.ToolShedRepository.installation_status.LOADING_PROPRIETARY_DATATYPES]:
            bgcolor = app.install_model.ToolShedRepository.states.INSTALLING
        elif tool_shed_repository.status in [app.install_model.ToolShedRepository.installation_status.NEW,
                                             app.install_model.ToolShedRepository.installation_status.UNINSTALLED]:
            bgcolor = app.install_model.ToolShedRepository.states.UNINSTALLED
        elif tool_shed_repository.status in [app.install_model.ToolShedRepository.installation_status.ERROR]:
            bgcolor = app.install_model.ToolShedRepository.states.ERROR
        elif tool_shed_repository.status in [app.install_model.ToolShedRepository.installation_status.DEACTIVATED]:
            bgcolor = app.install_model.ToolShedRepository.states.WARNING
        elif tool_shed_repository.status in [app.install_model.ToolShedRepository.installation_status.INSTALLED]:
            if tool_shed_repository.repository_dependencies_being_installed:
                bgcolor = app.install_model.ToolShedRepository.states.WARNING
                status_label = '%s, %s' % (status_label,
                                           app.install_model.ToolShedRepository.installation_status.INSTALLING_REPOSITORY_DEPENDENCIES)
            elif tool_shed_repository.missing_repository_dependencies:
                bgcolor = app.install_model.ToolShedRepository.states.WARNING
                status_label = '%s, missing repository dependencies' % status_label
            elif tool_shed_repository.tool_dependencies_being_installed:
                bgcolor = app.install_model.ToolShedRepository.states.WARNING
                status_label = '%s, %s' % (status_label,
                                           app.install_model.ToolShedRepository.installation_status.INSTALLING_TOOL_DEPENDENCIES)
            elif tool_shed_repository.missing_tool_dependencies:
                bgcolor = app.install_model.ToolShedRepository.states.WARNING
                status_label = '%s, missing tool dependencies' % status_label
            else:
                bgcolor = app.install_model.ToolShedRepository.states.OK
        else:
            bgcolor = app.install_model.ToolShedRepository.states.ERROR
    else:
        bgcolor = app.install_model.ToolShedRepository.states.WARNING
        status_label = 'unknown status'
    return '<div class="count-box state-color-%s">%s</div>' % (bgcolor, status_label)


def get_tool_shed_status_for_installed_repository(app, repository):
    """
    Send a request to the tool shed to retrieve information about newer installable repository revisions,
    current revision updates, whether the repository revision is the latest downloadable revision, and
    whether the repository has been deprecated in the tool shed.  The received repository is a ToolShedRepository
    object from Galaxy.
    """
    tool_shed_url = common_util.get_tool_shed_url_from_tool_shed_registry(app, str(repository.tool_shed))
    params = dict(name=repository.name, owner=repository.owner, changeset_revision=repository.changeset_revision)
    pathspec = ['repository', 'status_for_installed_repository']
    try:
        encoded_tool_shed_status_dict = util.url_get(tool_shed_url, password_mgr=app.tool_shed_registry.url_auth(tool_shed_url), pathspec=pathspec, params=params)
        tool_shed_status_dict = encoding_util.tool_shed_decode(encoded_tool_shed_status_dict)
        return tool_shed_status_dict
    except HTTPError as e:
        # This should handle backward compatility to the Galaxy 12/20/12 release.  We used to only handle updates for an installed revision
        # using a boolean value.
        log.debug("Error attempting to get tool shed status for installed repository %s: %s\nAttempting older 'check_for_updates' method.\n" %
                  (str(repository.name), str(e)))
        pathspec = ['repository', 'check_for_updates']
        params['from_update_manager'] = True
        try:
            # The value of text will be 'true' or 'false', depending upon whether there is an update available for the installed revision.
            text = util.url_get(tool_shed_url, password_mgr=app.tool_shed_registry.url_auth(tool_shed_url), pathspec=pathspec, params=params)
            return dict(revision_update=text)
        except Exception as e:
            # The required tool shed may be unavailable, so default the revision_update value to 'false'.
            return dict(revision_update='false')
    except Exception as e:
        log.exception("Error attempting to get tool shed status for installed repository %s", str(repository.name))
        return {}


def handle_role_associations(app, role, repository, **kwd):
    sa_session = app.model.context.current
    message = escape(kwd.get('message', ''))
    status = kwd.get('status', 'done')
    repository_owner = repository.user
    if kwd.get('manage_role_associations_button', False):
        in_users_list = util.listify(kwd.get('in_users', []))
        in_users = [sa_session.query(app.model.User).get(x) for x in in_users_list]
        # Make sure the repository owner is always associated with the repostory's admin role.
        owner_associated = False
        for user in in_users:
            if user.id == repository_owner.id:
                owner_associated = True
                break
        if not owner_associated:
            in_users.append(repository_owner)
            message += "The repository owner must always be associated with the repository's administrator role.  "
            status = 'error'
        in_groups_list = util.listify(kwd.get('in_groups', []))
        in_groups = [sa_session.query(app.model.Group).get(x) for x in in_groups_list]
        in_repositories = [repository]
        app.security_agent.set_entity_role_associations(roles=[role],
                                                        users=in_users,
                                                        groups=in_groups,
                                                        repositories=in_repositories)
        sa_session.refresh(role)
        message += "Role <b>%s</b> has been associated with %d users, %d groups and %d repositories.  " % \
            (escape(str(role.name)), len(in_users), len(in_groups), len(in_repositories))
    in_users = []
    out_users = []
    in_groups = []
    out_groups = []
    for user in sa_session.query(app.model.User) \
                          .filter(app.model.User.table.c.deleted == false()) \
                          .order_by(app.model.User.table.c.email):
        if user in [x.user for x in role.users]:
            in_users.append((user.id, user.email))
        else:
            out_users.append((user.id, user.email))
    for group in sa_session.query(app.model.Group) \
                           .filter(app.model.Group.table.c.deleted == false()) \
                           .order_by(app.model.Group.table.c.name):
        if group in [x.group for x in role.groups]:
            in_groups.append((group.id, group.name))
        else:
            out_groups.append((group.id, group.name))
    associations_dict = dict(in_users=in_users,
                             out_users=out_users,
                             in_groups=in_groups,
                             out_groups=out_groups,
                             message=message,
                             status=status)
    return associations_dict


def is_tool_shed_client(app):
    """
    The tool shed and clients to the tool (i.e. Galaxy) require a lot
    of similar functionality in this file but with small differences. This
    method should determine if the app performing the action is the tool shed
    or a client of the tool shed.
    """
    return hasattr(app, "install_model")


def repository_was_previously_installed(app, tool_shed_url, repository_name, repo_info_tuple, from_tip=False):
    """
    Find out if a repository is already installed into Galaxy - there are several scenarios where this
    is necessary.  For example, this method will handle the case where the repository was previously
    installed using an older changeset_revsion, but later the repository was updated in the tool shed
    and now we're trying to install the latest changeset revision of the same repository instead of
    updating the one that was previously installed.  We'll look in the database instead of on disk since
    the repository may be currently uninstalled.
    """
    tool_shed_url = common_util.get_tool_shed_url_from_tool_shed_registry(app, tool_shed_url)
    description, repository_clone_url, changeset_revision, ctx_rev, repository_owner, repository_dependencies, tool_dependencies = \
        get_repo_info_tuple_contents(repo_info_tuple)
    tool_shed = get_tool_shed_from_clone_url(repository_clone_url)
    # See if we can locate the repository using the value of changeset_revision.
    tool_shed_repository = get_installed_repository(app,
                                                    tool_shed=tool_shed,
                                                    name=repository_name,
                                                    owner=repository_owner,
                                                    installed_changeset_revision=changeset_revision)
    if tool_shed_repository:
        return tool_shed_repository, changeset_revision
    # Get all previous changeset revisions from the tool shed for the repository back to, but excluding,
    # the previous valid changeset revision to see if it was previously installed using one of them.
    params = dict(galaxy_url=web.url_for('/', qualified=True),
                  name=repository_name,
                  owner=repository_owner,
                  changeset_revision=changeset_revision,
                  from_tip=str(from_tip))
    pathspec = ['repository', 'previous_changeset_revisions']
    text = util.url_get(tool_shed_url, password_mgr=app.tool_shed_registry.url_auth(tool_shed_url), pathspec=pathspec, params=params)
    if text:
        changeset_revisions = util.listify(text)
        for previous_changeset_revision in changeset_revisions:
            tool_shed_repository = get_installed_repository(app,
                                                            tool_shed=tool_shed,
                                                            name=repository_name,
                                                            owner=repository_owner,
                                                            installed_changeset_revision=previous_changeset_revision)
            if tool_shed_repository:
                return tool_shed_repository, previous_changeset_revision
    return None, None


def set_repository_attributes(app, repository, status, error_message, deleted, uninstalled, remove_from_disk=False):
    if remove_from_disk:
        relative_install_dir = repository.repo_path(app)
        if relative_install_dir:
            clone_dir = os.path.abspath(relative_install_dir)
            try:
                shutil.rmtree(clone_dir)
                log.debug("Removed repository installation directory: %s" % str(clone_dir))
            except Exception as e:
                log.debug("Error removing repository installation directory %s: %s" % (str(clone_dir), str(e)))
    repository.error_message = error_message
    repository.status = status
    repository.deleted = deleted
    repository.uninstalled = uninstalled
    app.install_model.context.add(repository)
    app.install_model.context.flush()


def update_repository(app, trans, id, **kwds):
    """Update an existing ToolShed repository"""
    message = None
    flush_needed = False
    sa_session = app.model.context.current
    repository = sa_session.query(app.model.Repository).get(app.security.decode_id(id))
    if repository is None:
        return None, "Unknown repository ID"

    if not (trans.user_is_admin() or
            trans.app.security_agent.user_can_administer_repository(trans.user, repository)):
        message = "You are not the owner of this repository, so you cannot administer it."
        return None, message

    # Whitelist properties that can be changed via this method
    for key in ('type', 'description', 'long_description', 'remote_repository_url', 'homepage_url'):
        # If that key is available, not None and different than what's in the model
        if key in kwds and kwds[key] is not None and kwds[key] != getattr(repository, key):
            setattr(repository, key, kwds[key])
            flush_needed = True

    if 'category_ids' in kwds and isinstance(kwds['category_ids'], list):
        # Get existing category associations
        category_associations = sa_session.query(app.model.RepositoryCategoryAssociation) \
                                          .filter(app.model.RepositoryCategoryAssociation.table.c.repository_id == app.security.decode_id(id))
        # Remove all of them
        for rca in category_associations:
            sa_session.delete(rca)

        # Then (re)create category associations
        for category_id in kwds['category_ids']:
            category = sa_session.query(app.model.Category) \
                                 .get(app.security.decode_id(category_id))
            if category:
                rca = app.model.RepositoryCategoryAssociation(repository, category)
                sa_session.add(rca)
            else:
                pass
        flush_needed = True

    # However some properties are special, like 'name'
    if 'name' in kwds and kwds['name'] is not None and repository.name != kwds['name']:
        if repository.times_downloaded != 0:
            message = "Repository names cannot be changed if the repository has been cloned."
        else:
            message = validate_repository_name(trans.app, kwds['name'], trans.user)
        if message:
            return None, message

        repo_dir = repository.repo_path(app)
        # Change the entry in the hgweb.config file for the repository.
        old_lhs = "repos/%s/%s" % (repository.user.username, repository.name)
        new_lhs = "repos/%s/%s" % (repository.user.username, kwds['name'])
        trans.app.hgweb_config_manager.change_entry(old_lhs, new_lhs, repo_dir)

        # Change the entry in the repository's hgrc file.
        hgrc_file = os.path.join(repo_dir, '.hg', 'hgrc')
        change_repository_name_in_hgrc_file(hgrc_file, kwds['name'])

        # Rename the repository's admin role to match the new repository name.
        repository_admin_role = repository.admin_role
        repository_admin_role.name = get_repository_admin_role_name(str(kwds['name']), str(repository.user.username))
        trans.sa_session.add(repository_admin_role)
        repository.name = kwds['name']
        flush_needed = True

    if flush_needed:
        trans.sa_session.add(repository)
        trans.sa_session.flush()
        message = "The repository information has been updated."
    else:
        message = None
    return repository, message


def validate_repository_name(app, name, user):
    """
    Validate whether the given name qualifies as a new TS repo name.
    Repository names must be unique for each user, must be at least two characters
    in length and must contain only lower-case letters, numbers, and the '_' character.
    """
    if name in ['None', None, '']:
        return 'Enter the required repository name.'
    if name in ['repos']:
        return "The term <b>%s</b> is a reserved word in the tool shed, so it cannot be used as a repository name." % name
    check_existing = get_repository_by_name_and_owner(app, name, user.username)
    if check_existing is not None:
        if check_existing.deleted:
            return 'You own a deleted repository named <b>%s</b>, please choose a different name.' % escape(name)
        else:
            return "You already own a repository named <b>%s</b>, please choose a different name." % escape(name)
    if len(name) < 2:
        return "Repository names must be at least 2 characters in length."
    if len(name) > 80:
        return "Repository names cannot be more than 80 characters in length."
    if not(VALID_REPOSITORYNAME_RE.match(name)):
        return "Repository names must contain only lower-case letters, numbers and underscore."
    return ''
