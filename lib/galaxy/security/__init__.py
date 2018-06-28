"""
Galaxy Security

"""
import logging
import socket
from datetime import datetime, timedelta

from sqlalchemy import and_, false, not_, or_
from sqlalchemy.orm import eagerload_all

from galaxy.util import listify
from galaxy.util.bunch import Bunch

log = logging.getLogger(__name__)


class Action(object):
    def __init__(self, action, description, model):
        self.action = action
        self.description = description
        self.model = model


class RBACAgent:
    """Class that handles galaxy security"""
    permitted_actions = Bunch(
        DATASET_MANAGE_PERMISSIONS=Action("manage permissions", "Users having associated role can manage the roles associated with permissions on this dataset.", "grant"),
        DATASET_ACCESS=Action("access", "Users having associated role can import this dataset into their history for analysis.", "restrict"),
        LIBRARY_ACCESS=Action("access library", "Restrict access to this library to only users having associated role", "restrict"),
        LIBRARY_ADD=Action("add library item", "Users having associated role can add library items to this library item", "grant"),
        LIBRARY_MODIFY=Action("modify library item", "Users having associated role can modify this library item", "grant"),
        LIBRARY_MANAGE=Action("manage library permissions", "Users having associated role can manage roles associated with permissions on this library item", "grant"),
        # Request type permissions
        REQUEST_TYPE_ACCESS=Action("access request_type", "Restrict access to this request type to only users having associated role", "restrict")
    )

    def get_action(self, name, default=None):
        """Get a permitted action by its dict key or action name"""
        for k, v in self.permitted_actions.items():
            if k == name or v.action == name:
                return v
        return default

    def get_actions(self):
        """Get all permitted actions as a list of Action objects"""
        return list(self.permitted_actions.__dict__.values())

    def get_item_actions(self, action, item):
        raise Exception('No valid method of retrieving action (%s) for item %s.' % (action, item))

    def guess_derived_permissions_for_datasets(self, datasets=[]):
        raise Exception("Unimplemented Method")

    def can_access_dataset(self, roles, dataset):
        raise Exception("Unimplemented Method")

    def can_manage_dataset(self, roles, dataset):
        raise Exception("Unimplemented Method")

    def can_access_library(self, roles, library):
        raise Exception("Unimplemented Method")

    def can_add_library_item(self, roles, item):
        raise Exception("Unimplemented Method")

    def can_modify_library_item(self, roles, item):
        raise Exception("Unimplemented Method")

    def can_manage_library_item(self, roles, item):
        raise Exception("Unimplemented Method")

    def associate_components(self, **kwd):
        raise Exception('No valid method of associating provided components: %s' % kwd)

    def create_private_user_role(self, user):
        raise Exception("Unimplemented Method")

    def get_private_user_role(self, user):
        raise Exception("Unimplemented Method")

    def get_accessible_request_types(self, trans, user):
        raise Exception("Unimplemented Method")

    def user_set_default_permissions(self, user, permissions={}, history=False, dataset=False):
        raise Exception("Unimplemented Method")

    def history_set_default_permissions(self, history, permissions=None, dataset=False, bypass_manage_permission=False):
        raise Exception("Unimplemented Method")

    def set_all_dataset_permissions(self, dataset, permissions, new=False):
        raise Exception("Unimplemented Method")

    def set_dataset_permission(self, dataset, permission):
        raise Exception("Unimplemented Method")

    def set_all_library_permissions(self, trans, dataset, permissions):
        raise Exception("Unimplemented Method")

    def set_library_item_permission(self, library_item, permission):
        raise Exception("Unimplemented Method")

    def library_is_public(self, library):
        raise Exception("Unimplemented Method")

    def make_library_public(self, library):
        raise Exception("Unimplemented Method")

    def get_accessible_libraries(self, trans, user):
        raise Exception("Unimplemented Method")

    def get_permitted_libraries(self, trans, user, actions):
        raise Exception("Unimplemented Method")

    def folder_is_public(self, library):
        raise Exception("Unimplemented Method")

    def make_folder_public(self, folder, count=0):
        raise Exception("Unimplemented Method")

    def dataset_is_public(self, dataset):
        raise Exception("Unimplemented Method")

    def make_dataset_public(self, dataset):
        raise Exception("Unimplemented Method")

    def get_permissions(self, library_dataset):
        raise Exception("Unimplemented Method")

    def get_all_roles(self, trans, cntrller):
        raise Exception("Unimplemented Method")

    def get_legitimate_roles(self, trans, item, cntrller):
        raise Exception("Unimplemented Method")

    def derive_roles_from_access(self, trans, item_id, cntrller, library=False, **kwd):
        raise Exception("Unimplemented Method")

    def get_component_associations(self, **kwd):
        raise Exception("Unimplemented Method")

    def components_are_associated(self, **kwd):
        return bool(self.get_component_associations(**kwd))

    def convert_permitted_action_strings(self, permitted_action_strings):
        """
        When getting permitted actions from an untrusted source like a
        form, ensure that they match our actual permitted actions.
        """
        return [_ for _ in [self.permitted_actions.get(action_string) for action_string in permitted_action_strings] if _ is not None]


class GalaxyRBACAgent(RBACAgent):
    def __init__(self, model, permitted_actions=None):
        self.model = model
        if permitted_actions:
            self.permitted_actions = permitted_actions
        # List of "library_item" objects and their associated permissions and info template objects
        self.library_item_assocs = (
            (self.model.Library, self.model.LibraryPermissions),
            (self.model.LibraryFolder, self.model.LibraryFolderPermissions),
            (self.model.LibraryDataset, self.model.LibraryDatasetPermissions),
            (self.model.LibraryDatasetDatasetAssociation, self.model.LibraryDatasetDatasetAssociationPermissions))

    @property
    def sa_session(self):
        """Returns a SQLAlchemy session"""
        return self.model.context

    def sort_by_attr(self, seq, attr):
        """
        Sort the sequence of objects by object's attribute
        Arguments:
        seq  - the list or any sequence (including immutable one) of objects to sort.
        attr - the name of attribute to sort by
        """
        # Use the "Schwartzian transform"
        # Create the auxiliary list of tuples where every i-th tuple has form
        # (seq[i].attr, i, seq[i]) and sort it. The second item of tuple is needed not
        # only to provide stable sorting, but mainly to eliminate comparison of objects
        # (which can be expensive or prohibited) in case of equal attribute values.
        intermed = map(None, (getattr(_, attr) for _ in seq), range(len(seq)), seq)
        intermed.sort()
        return [_[-1] for _ in intermed]

    def _get_npns_roles(self, trans):
        """
        non-private, non-sharing roles
        """
        return trans.sa_session.query(trans.app.model.Role) \
                    .filter(and_(self.model.Role.table.c.deleted == false(),
                        self.model.Role.table.c.type != self.model.Role.types.PRIVATE,
                        self.model.Role.table.c.type != self.model.Role.types.SHARING)) \
                    .order_by(self.model.Role.table.c.name)

    def get_all_roles(self, trans, cntrller):
        admin_controller = cntrller in ['library_admin']
        roles = set()
        if not trans.user:
            return self._get_npns_roles(trans)
        if admin_controller:
            # The library is public and the user is an admin, so all roles are legitimate
            for role in trans.sa_session.query(trans.app.model.Role) \
                                        .filter(self.model.Role.table.c.deleted == false()) \
                                        .order_by(self.model.Role.table.c.name):
                roles.add(role)
        else:
            # Add the current user's private role
            roles.add(self.get_private_user_role(trans.user))
            # Add the current user's sharing roles
            for role in self.get_sharing_roles(trans.user):
                roles.add(role)
            # Add all remaining non-private, non-sharing roles
            for role in self._get_npns_roles(trans):
                roles.add(role)
        return self.sort_by_attr([role for role in roles], 'name')

    def get_roles_for_action(self, item, action):
        """
        Return a list containing the roles associated with given action on given item
        where item is one of Library, LibraryFolder, LibraryDatasetDatasetAssociation,
        LibraryDataset, Dataset.
        """
        roles = []
        for item_permission in item.actions:
            permission_action = self.get_action(item_permission.action)
            if permission_action == action:
                roles.append(item_permission.role)
        return roles

    def get_valid_roles(self, trans, item, query=None, page=None, page_limit=None, is_library_access=False):
        """
        This method retrieves the list of possible roles that user can select
        in the item permissions form. Admins can select any role so the
        results are paginated in order to save the bandwidth and to speed
        things up.
        Standard users can select their own private role, any of their
        sharing roles and any public role (not private and not sharing).
        """
        roles = []
        if query not in [None, '']:
            query = query.strip().replace('_', '/_').replace('%', '/%').replace('/', '//')
            search_query = query + '%'
        else:
            search_query = None
        # Limit the query only to get the page needed
        if page is not None and page_limit is not None:
            limit = page * page_limit
        else:
            limit = None
        total_count = None
        if isinstance(item, self.model.Library) and self.library_is_public(item):
            is_public_item = True
        elif isinstance(item, self.model.Dataset) and self.dataset_is_public(item):
            is_public_item = True
        elif isinstance(item, self.model.LibraryFolder):
            is_public_item = True
        else:
            is_public_item = False
        # Admins can always choose from all non-deleted roles
        if trans.user_is_admin() or trans.app.config.expose_user_email:
            if trans.user_is_admin():
                db_query = trans.sa_session.query(trans.app.model.Role).filter(self.model.Role.table.c.deleted == false())
            else:
                # User is not an admin but the configuration exposes all private roles to all users.
                db_query = trans.sa_session.query(trans.app.model.Role) \
                    .filter(and_(self.model.Role.table.c.deleted == false(),
                                 self.model.Role.table.c.type == self.model.Role.types.PRIVATE))
            if search_query:
                db_query = db_query.filter(self.model.Role.table.c.name.like(search_query, escape='/'))
            total_count = db_query.count()
            if limit is not None:
                # Takes the least number of results from beginning that includes the requested page
                roles = db_query.order_by(self.model.Role.table.c.name).limit(limit).all()
                page_start = (page * page_limit) - page_limit
                page_end = page_start + page_limit
                if total_count < page_start + 1:
                    # Return empty list if there are less results than the requested position
                    roles = []
                else:
                    roles = roles[page_start:page_end]
            else:
                roles = db_query.order_by(self.model.Role.table.c.name)
        # Non-admin and public item
        elif is_public_item:
            # Add the current user's private role
            roles.append(self.get_private_user_role(trans.user))
            # Add the current user's sharing roles
            for role in self.get_sharing_roles(trans.user):
                roles.append(role)
            # Add all remaining non-private, non-sharing roles
            for role in self._get_npns_roles(trans):
                roles.append(role)
        # User will see all the roles derived from the access roles on the item
        else:
            # If item has roles associated with the access permission, we need to start with them.
            access_roles = item.get_access_roles(trans)
            for role in access_roles:
                if trans.user_is_admin() or self.ok_to_display(trans.user, role):
                    roles.append(role)
                    # Each role potentially has users.  We need to find all roles that each of those users have.
                    for ura in role.users:
                        user = ura.user
                        for ura2 in user.roles:
                            if trans.user_is_admin() or self.ok_to_display(trans.user, ura2.role):
                                roles.append(ura2.role)
                    # Each role also potentially has groups which, in turn, have members ( users ).  We need to
                    # find all roles that each group's members have.
                    for gra in role.groups:
                        group = gra.group
                        for uga in group.users:
                            user = uga.user
                            for ura in user.roles:
                                if trans.user_is_admin() or self.ok_to_display(trans.user, ura.role):
                                    roles.append(ura.role)

        # Omit duplicated roles by converting to set
        return_roles = set(roles)
        if total_count is None:
            total_count = len(return_roles)
        return self.sort_by_attr([role for role in return_roles], 'name'), total_count

    def get_legitimate_roles(self, trans, item, cntrller):
        """
        Return a sorted list of legitimate roles that can be associated with a permission on
        item where item is a Library or a Dataset.  The cntrller param is the controller from
        which the request is sent.  We cannot use trans.user_is_admin() because the controller is
        what is important since admin users do not necessarily have permission to do things
        on items outside of the admin view.

        If cntrller is from the admin side ( e.g., library_admin ):

            - if item is public, all roles, including private roles, are legitimate.
            - if item is restricted, legitimate roles are derived from the users and groups associated
              with each role that is associated with the access permission ( i.e., DATASET_MANAGE_PERMISSIONS or
              LIBRARY_MANAGE ) on item.  Legitimate roles will include private roles.

        If cntrller is not from the admin side ( e.g., root, library ):

            - if item is public, all non-private roles, except for the current user's private role,
              are legitimate.
            - if item is restricted, legitimate roles are derived from the users and groups associated
              with each role that is associated with the access permission on item.  Private roles, except
              for the current user's private role, will be excluded.
        """
        admin_controller = cntrller in ['library_admin']
        roles = set()
        if (isinstance(item, self.model.Library) and self.library_is_public(item)) or \
                (isinstance(item, self.model.Dataset) and self.dataset_is_public(item)):
            return self.get_all_roles(trans, cntrller)
        # If item has roles associated with the access permission, we need to start with them.
        access_roles = item.get_access_roles(trans)
        for role in access_roles:
            if admin_controller or self.ok_to_display(trans.user, role):
                roles.add(role)
                # Each role potentially has users.  We need to find all roles that each of those users have.
                for ura in role.users:
                    user = ura.user
                    for ura2 in user.roles:
                        if admin_controller or self.ok_to_display(trans.user, ura2.role):
                            roles.add(ura2.role)
                # Each role also potentially has groups which, in turn, have members ( users ).  We need to
                # find all roles that each group's members have.
                for gra in role.groups:
                    group = gra.group
                    for uga in group.users:
                        user = uga.user
                        for ura in user.roles:
                            if admin_controller or self.ok_to_display(trans.user, ura.role):
                                roles.add(ura.role)
        return self.sort_by_attr([role for role in roles], 'name')

    def ok_to_display(self, user, role):
        """
        Method for checking if:
        - a role is private and is the current user's private role
        - a role is a sharing role and belongs to the current user
        """
        if user:
            if role.type == self.model.Role.types.PRIVATE:
                return role == self.get_private_user_role(user)
            if role.type == self.model.Role.types.SHARING:
                return role in self.get_sharing_roles(user)
            # If role.type is neither private nor sharing, it's ok to display
            return True
        return role.type != self.model.Role.types.PRIVATE and role.type != self.model.Role.types.SHARING

    def allow_action(self, roles, action, item):
        """
        Method for checking a permission for the current user ( based on roles ) to perform a
        specific action on an item, which must be one of:
        Dataset, Library, LibraryFolder, LibraryDataset, LibraryDatasetDatasetAssociation
        """
        # SM: Note that calling get_item_actions will emit a query.
        item_actions = self.get_item_actions(action, item)

        if not item_actions:
            return action.model == 'restrict'
        ret_val = False
        # For DATASET_ACCESS only, user must have ALL associated roles
        if action == self.permitted_actions.DATASET_ACCESS:
            for item_action in item_actions:
                if item_action.role not in roles:
                    break
            else:
                ret_val = True
        # For remaining actions, user must have any associated role
        else:
            for item_action in item_actions:
                if item_action.role in roles:
                    ret_val = True
                    break
        return ret_val

    def get_actions_for_items(self, trans, action, permission_items):
        # TODO: Rename this; it's a replacement for get_item_actions, but it
        # doesn't represent what it's really doing, which is confusing.
        # TODO: Make this work for other classes besides lib_datasets.
        # That should be as easy as checking the type and writing a query for each;
        # we're avoiding using the SQLAlchemy backrefs because they can cause lots
        # of queries to be generated.
        #
        # Originally, get_item_actions did:
        # return [ permission for permission in item.actions if permission.action == action.action ]
        # The "item" can be just about anything with permissions, and referencing
        # item.actions causes the item's permissions to be retrieved.
        # This method will retrieve all permissions for all "items" and only
        # return the permissions associated with that given action.
        # We initialize the permissions list to be empty; we will return an
        # empty list by default.
        #
        # If the dataset id has no corresponding action in its permissions,
        # then the returned permissions will not carry an entry for the dataset.
        ret_permissions = {}
        if (len(permission_items) > 0):
            # SM: NB: LibraryDatasets became Datasets for some odd reason.
            if (isinstance(permission_items[0], trans.model.LibraryDataset)):
                ids = [item.library_dataset_id for item in permission_items]
                permissions = trans.sa_session.query(trans.model.LibraryDatasetPermissions) \
                                   .filter(and_(trans.model.LibraryDatasetPermissions.library_dataset_id.in_(ids),
                                                trans.model.LibraryDatasetPermissions.action == action.action)) \
                                   .all()

                # Massage the return data. We will return a list of permissions
                # for each library dataset. So we initialize the return list to
                # have an empty list for each dataset. Then each permission is
                # appended to the right lib dataset.
                # TODO: Consider eliminating the initialization and just return
                # empty values for each library dataset id.
                for item in permission_items:
                    ret_permissions[item.library_dataset_id] = []
                for permission in permissions:
                    ret_permissions[permission.library_dataset_id].append(permission)
            elif (isinstance(permission_items[0], trans.model.Dataset)):
                ids = [item.id for item in permission_items]
                permissions = trans.sa_session.query(trans.model.DatasetPermissions) \
                                   .filter(and_(trans.model.DatasetPermissions.dataset_id.in_(ids),
                                                trans.model.DatasetPermissions.action == action.action)) \
                                   .all()

                # Massage the return data. We will return a list of permissions
                # for each library dataset. So we initialize the return list to
                # have an empty list for each dataset. Then each permission is
                # appended to the right lib dataset.
                # TODO: Consider eliminating the initialization and just return
                # empty values for each library dataset id.
                for item in permission_items:
                    ret_permissions[item.id] = []
                for permission in permissions:
                    ret_permissions[permission.dataset_id].append(permission)

        # Test that we get the same response from get_item_actions each item:
        test_code = False
        if test_code:
            try:
                log.debug("get_actions_for_items: Test start")
                for item in permission_items:
                    base_result = self.get_item_actions(action, item)
                    new_result = ret_permissions[item.library_dataset_id]
                    # For now, just test against LibraryDatasetIds; other classes
                    # are not tested yet.
                    if len(base_result) == len(new_result):
                        common_result = set(base_result).intersection(new_result)
                        if len(common_result) == len(base_result):
                            log.debug("Match on permissions for id %d" %
                                      item.library_dataset_id)
                        # TODO: Fix this failure message:
                        else:
                            log.debug("Error: dataset %d; originally: %s; now: %s"
                                      % (item.library_dataset_id,
                                         base_result, new_result))
                    else:
                        log.debug("Error: dataset %d: had %d entries, now %d entries"
                                  % (item.library_dataset_id, len(base_result),
                                     len(new_result)))
                log.debug("get_actions_for_items: Test end")
            except Exception as e:
                log.debug("Exception in test code: %s" % e)

        return ret_permissions

    def allow_action_on_libitems(self, trans, user_roles, action, items):
        """
        This should be the equivalent of allow_action defined on multiple items.
        It is meant to specifically replace allow_action for multiple
        LibraryDatasets, but it could be reproduced or modified for
        allow_action's permitted classes - Dataset, Library, LibraryFolder, and
        LDDAs.
        """
        all_items_actions = self.get_actions_for_items(trans, action, items)
        ret_allow_action = {}

        # Change item to lib_dataset or vice-versa.
        for item in items:
            if item.id in all_items_actions:
                item_actions = all_items_actions[item.id]

                if self.permitted_actions.DATASET_ACCESS == action:
                    ret_allow_action[item.id] = True
                    for item_action in item_actions:
                        if item_action.role not in user_roles:
                            ret_allow_action[item.id] = False
                            break

                # Else look for just one dataset role to be in the list of
                # acceptable user roles:
                else:
                    ret_allow_action[item.id] = False
                    for item_action in item_actions:
                        if item_action.role in user_roles:
                            ret_allow_action[item.id] = True
                            break

            else:
                if 'restrict' == action.model:
                    ret_allow_action[item.id] = True
                else:
                    ret_allow_action[item.id] = False

        # Test it: the result for each dataset should match the result for
        # allow_action:
        test_code = False
        if test_code:
            log.debug("allow_action_for_items: test start")
            for item in items:
                orig_value = self.allow_action(user_roles, action, item)
                if orig_value == ret_allow_action[item.id]:
                    log.debug("Item %d: success" % item.id)
                else:
                    log.debug("Item %d: fail: original: %s; new: %s"
                              % (item.id, orig_value, ret_allow_action[item.id]))
            log.debug("allow_action_for_items: test end")
        return ret_allow_action

    # DELETEME: SM: DO NOT TOUCH! This actually works.
    def dataset_access_mapping(self, trans, user_roles, datasets):
        '''
        For the given list of datasets, return a mapping of the datasets' ids
        to whether they can be accessed by the user or not. The datasets input
        is expected to be a simple list of Dataset objects.
        '''
        datasets_public_map = self.datasets_are_public(trans, datasets)
        datasets_allow_action_map = self.allow_action_on_libitems(trans, user_roles, self.permitted_actions.DATASET_ACCESS, datasets)
        can_access = {}
        for dataset in datasets:
            can_access[dataset.id] = datasets_public_map[dataset.id] or datasets_allow_action_map[dataset.id]
        return can_access

    def dataset_permission_map_for_access(self, trans, user_roles, libitems):
        '''
        For a given list of library items (e.g., Datasets), return a map of the
        datasets' ids to whether they can have permission to use that action
        (e.g., "access" or "modify") on the dataset. The libitems input is
        expected to be a simple list of library items, such as Datasets or
        LibraryDatasets.
        NB: This is currently only usable for Datasets; it was intended to
        be used for any library item.
        '''
        # Map the library items to whether they are publicly accessible or not.
        # Then determine what actions are allowed on the item (in case it's not
        # public). Finally, the item is accessible if it's publicly available
        # or the right permissions are enabled.
        # TODO: This only works for Datasets; other code is using X_is_public,
        # so this will have to be rewritten to support other items.
        libitems_public_map = self.datasets_are_public(trans, libitems)
        libitems_allow_action_map = self.allow_action_on_libitems(
            trans, user_roles, self.permitted_actions.DATASET_ACCESS, libitems
        )
        can_access = {}
        for libitem in libitems:
            can_access[libitem.id] = libitems_public_map[libitem.id] or libitems_allow_action_map[libitem.id]
        return can_access

    def item_permission_map_for_modify(self, trans, user_roles, libitems):
        return self.allow_action_on_libitems(
            trans, user_roles, self.permitted_actions.LIBRARY_MODIFY, libitems
        )

    def item_permission_map_for_manage(self, trans, user_roles, libitems):
        return self.allow_action_on_libitems(
            trans, user_roles, self.permitted_actions.LIBRARY_MANAGE, libitems
        )

    def item_permission_map_for_add(self, trans, user_roles, libitems):
        return self.allow_action_on_libitems(
            trans, user_roles, self.permitted_actions.LIBRARY_ADD, libitems
        )

    def can_access_dataset(self, user_roles, dataset):
        # SM: dataset_is_public will access dataset.actions, which is a
        # backref that causes a query to be made to DatasetPermissions
        retval = self.dataset_is_public(dataset) or self.allow_action(user_roles, self.permitted_actions.DATASET_ACCESS, dataset)
        return retval

    def can_manage_dataset(self, roles, dataset):
        return self.allow_action(roles, self.permitted_actions.DATASET_MANAGE_PERMISSIONS, dataset)

    def can_access_library(self, roles, library):
        return self.library_is_public(library) or self.allow_action(roles, self.permitted_actions.LIBRARY_ACCESS, library)

    def get_accessible_libraries(self, trans, user):
        """Return all data libraries that the received user can access"""
        accessible_libraries = []
        current_user_role_ids = [role.id for role in user.all_roles()]
        library_access_action = self.permitted_actions.LIBRARY_ACCESS.action
        restricted_library_ids = [lp.library_id for lp in trans.sa_session.query(trans.model.LibraryPermissions)
                                  .filter(trans.model.LibraryPermissions.table.c.action == library_access_action).distinct()]
        accessible_restricted_library_ids = [lp.library_id for lp in trans.sa_session.query(trans.model.LibraryPermissions)
            .filter(and_(
                trans.model.LibraryPermissions.table.c.action == library_access_action,
                trans.model.LibraryPermissions.table.c.role_id.in_(current_user_role_ids)))]
        # Filter to get libraries accessible by the current user.  Get both
        # public libraries and restricted libraries accessible by the current user.
        for library in trans.sa_session.query(trans.model.Library) \
                                       .filter(and_(trans.model.Library.table.c.deleted == false(),
                                                    (or_(not_(trans.model.Library.table.c.id.in_(restricted_library_ids)),
                                                         trans.model.Library.table.c.id.in_(accessible_restricted_library_ids))))) \
                                       .order_by(trans.app.model.Library.name):
            accessible_libraries.append(library)
        return accessible_libraries

    def has_accessible_folders(self, trans, folder, user, roles, search_downward=True):
        if self.has_accessible_library_datasets(trans, folder, user, roles, search_downward=search_downward) or \
                self.can_add_library_item(roles, folder) or \
                self.can_modify_library_item(roles, folder) or \
                self.can_manage_library_item(roles, folder):
            return True
        if search_downward:
            for folder in folder.active_folders:
                return self.has_accessible_folders(trans, folder, user, roles, search_downward=search_downward)
        return False

    def has_accessible_library_datasets(self, trans, folder, user, roles, search_downward=True):
        for library_dataset in trans.sa_session.query(trans.model.LibraryDataset) \
                .filter(and_(trans.model.LibraryDataset.table.c.deleted == false(),
                             trans.app.model.LibraryDataset.table.c.folder_id == folder.id)):
            if self.can_access_library_item(roles, library_dataset, user):
                return True
        if search_downward:
            return self.__active_folders_have_accessible_library_datasets(trans, folder, user, roles)
        return False

    def __active_folders_have_accessible_library_datasets(self, trans, folder, user, roles):
        for active_folder in folder.active_folders:
            if self.has_accessible_library_datasets(trans, active_folder, user, roles):
                return True
        return False

    def can_access_library_item(self, roles, item, user):
        if type(item) == self.model.Library:
            return self.can_access_library(roles, item)
        elif type(item) == self.model.LibraryFolder:
            return self.can_access_library(roles, item.parent_library) and self.check_folder_contents(user, roles, item)[0]
        elif type(item) == self.model.LibraryDataset:
            return self.can_access_library(roles, item.folder.parent_library) and self.can_access_dataset(roles, item.library_dataset_dataset_association.dataset)
        elif type(item) == self.model.LibraryDatasetDatasetAssociation:
            return self.can_access_library(roles, item.library_dataset.folder.parent_library) and self.can_access_dataset(roles, item.dataset)
        elif type(item) == self.model.LibraryDatasetCollectionAssociation:
            return self.can_access_library(roles, item.folder.parent_library)
        else:
            log.warning('Unknown library item type: %s' % type(item))
            return False

    def can_add_library_item(self, roles, item):
        return self.allow_action(roles, self.permitted_actions.LIBRARY_ADD, item)

    def can_modify_library_item(self, roles, item):
        return self.allow_action(roles, self.permitted_actions.LIBRARY_MODIFY, item)

    def can_manage_library_item(self, roles, item):
        return self.allow_action(roles, self.permitted_actions.LIBRARY_MANAGE, item)

    def get_item_actions(self, action, item):
        # item must be one of: Dataset, Library, LibraryFolder, LibraryDataset, LibraryDatasetDatasetAssociation
        # SM: Accessing item.actions emits a query to Library_Dataset_Permissions
        # if the item is a LibraryDataset:
        # TODO: Pass in the item's actions - the item isn't needed
        return [permission for permission in item.actions if permission.action == action.action]

    def guess_derived_permissions_for_datasets(self, datasets=[]):
        """Returns a dict of { action : [ role, role, ... ] } for the output dataset based upon provided datasets"""
        perms = {}
        for dataset in datasets:
            if not isinstance(dataset, self.model.Dataset):
                dataset = dataset.dataset
            these_perms = {}
            # initialize blank perms
            for action in self.get_actions():
                these_perms[action] = []
            # collect this dataset's perms
            these_perms = self.get_permissions(dataset)
            # join or intersect this dataset's permissions with others
            for action, roles in these_perms.items():
                if action not in perms.keys():
                    perms[action] = roles
                else:
                    if action.model == 'grant':
                        # intersect existing roles with new roles
                        perms[action] = [_ for _ in roles if _ in perms[action]]
                    elif action.model == 'restrict':
                        # join existing roles with new roles
                        perms[action].extend([_ for _ in roles if _ not in perms[action]])
        return perms

    def associate_components(self, **kwd):
        if 'user' in kwd:
            if 'group' in kwd:
                return self.associate_user_group(kwd['user'], kwd['group'])
            elif 'role' in kwd:
                return self.associate_user_role(kwd['user'], kwd['role'])
        elif 'role' in kwd:
            if 'group' in kwd:
                return self.associate_group_role(kwd['group'], kwd['role'])
        if 'action' in kwd:
            if 'dataset' in kwd and 'role' in kwd:
                return self.associate_action_dataset_role(kwd['action'], kwd['dataset'], kwd['role'])
        raise Exception('No valid method of associating provided components: %s' % kwd)

    def associate_user_group(self, user, group):
        assoc = self.model.UserGroupAssociation(user, group)
        self.sa_session.add(assoc)
        self.sa_session.flush()
        return assoc

    def associate_user_role(self, user, role):
        assoc = self.model.UserRoleAssociation(user, role)
        self.sa_session.add(assoc)
        self.sa_session.flush()
        return assoc

    def associate_group_role(self, group, role):
        assoc = self.model.GroupRoleAssociation(group, role)
        self.sa_session.add(assoc)
        self.sa_session.flush()
        return assoc

    def associate_action_dataset_role(self, action, dataset, role):
        assoc = self.model.DatasetPermissions(action, dataset, role)
        self.sa_session.add(assoc)
        self.sa_session.flush()
        return assoc

    def create_private_user_role(self, user):
        # Create private role
        role = self.model.Role(name=user.email, description='Private Role for ' + user.email, type=self.model.Role.types.PRIVATE)
        self.sa_session.add(role)
        self.sa_session.flush()
        # Add user to role
        self.associate_components(role=role, user=user)
        return role

    def get_private_user_role(self, user, auto_create=False):
        role = self.sa_session.query(self.model.Role) \
                              .filter(and_(self.model.Role.table.c.name == user.email,
                                           self.model.Role.table.c.type == self.model.Role.types.PRIVATE)) \
                              .first()
        if not role:
            if auto_create:
                return self.create_private_user_role(user)
            else:
                return None
        return role

    def get_sharing_roles(self, user):
        return self.sa_session.query(self.model.Role) \
                              .filter(and_((self.model.Role.table.c.name).like("Sharing role for: %" + user.email + "%"),
                                           self.model.Role.table.c.type == self.model.Role.types.SHARING))

    def user_set_default_permissions(self, user, permissions={}, history=False, dataset=False, bypass_manage_permission=False, default_access_private=False):
        # bypass_manage_permission is used to change permissions of datasets in a userless history when logging in
        flush_needed = False
        if user is None:
            return None
        if not permissions:
            # default permissions
            permissions = {self.permitted_actions.DATASET_MANAGE_PERMISSIONS: [self.get_private_user_role(user, auto_create=True)]}
            # new_user_dataset_access_role_default_private is set as True in config file
            if default_access_private:
                permissions[self.permitted_actions.DATASET_ACCESS] = next(iter(permissions.values()))
        # Delete all of the current default permissions for the user
        for dup in user.default_permissions:
            self.sa_session.delete(dup)
            flush_needed = True
        # Add the new default permissions for the user
        for action, roles in permissions.items():
            if isinstance(action, Action):
                action = action.action
            for dup in [self.model.DefaultUserPermissions(user, action, role) for role in roles]:
                self.sa_session.add(dup)
                flush_needed = True
        if flush_needed:
            self.sa_session.flush()
        if history:
            for history in user.active_histories:
                self.history_set_default_permissions(history, permissions=permissions, dataset=dataset, bypass_manage_permission=bypass_manage_permission)

    def user_get_default_permissions(self, user):
        permissions = {}
        for dup in user.default_permissions:
            action = self.get_action(dup.action)
            if action in permissions:
                permissions[action].append(dup.role)
            else:
                permissions[action] = [dup.role]
        return permissions

    def history_set_default_permissions(self, history, permissions={}, dataset=False, bypass_manage_permission=False):
        # bypass_manage_permission is used to change permissions of datasets in a user-less history when logging in
        flush_needed = False
        user = history.user
        if not user:
            # default permissions on a user-less history are None
            return None
        if not permissions:
            permissions = self.user_get_default_permissions(user)
        # Delete all of the current default permission for the history
        for dhp in history.default_permissions:
            self.sa_session.delete(dhp)
            flush_needed = True
        # Add the new default permissions for the history
        for action, roles in permissions.items():
            if isinstance(action, Action):
                action = action.action
            for dhp in [self.model.DefaultHistoryPermissions(history, action, role) for role in roles]:
                self.sa_session.add(dhp)
                flush_needed = True
        if flush_needed:
            self.sa_session.flush()
        if dataset:
            # Only deal with datasets that are not purged
            for hda in history.activatable_datasets:
                dataset = hda.dataset
                if dataset.library_associations:
                    # Don't change permissions on a dataset associated with a library
                    continue
                if [assoc for assoc in dataset.history_associations if assoc.history not in user.histories]:
                    # Don't change permissions on a dataset associated with a history not owned by the user
                    continue
                if bypass_manage_permission or self.can_manage_dataset(user.all_roles(), dataset):
                    self.set_all_dataset_permissions(dataset, permissions)

    def history_get_default_permissions(self, history):
        permissions = {}
        for dhp in history.default_permissions:
            action = self.get_action(dhp.action)
            if action in permissions:
                permissions[action].append(dhp.role)
            else:
                permissions[action] = [dhp.role]
        return permissions

    def set_all_dataset_permissions(self, dataset, permissions={}, new=False, flush=True):
        """
        Set new full permissions on a dataset, eliminating all current permissions.
        Permission looks like: { Action : [ Role, Role ] }
        """
        # Make sure that DATASET_MANAGE_PERMISSIONS is associated with at least 1 role
        has_dataset_manage_permissions = False
        for action, roles in permissions.items():
            if isinstance(action, Action):
                if action == self.permitted_actions.DATASET_MANAGE_PERMISSIONS and roles:
                    has_dataset_manage_permissions = True
                    break
            elif action == self.permitted_actions.DATASET_MANAGE_PERMISSIONS.action and roles:
                has_dataset_manage_permissions = True
                break
        if not has_dataset_manage_permissions:
            return "At least 1 role must be associated with the <b>manage permissions</b> permission on this dataset."
        flush_needed = False
        # Delete all of the current permissions on the dataset
        if not new:
            for dp in dataset.actions:
                self.sa_session.delete(dp)
                flush_needed = True
        # Add the new permissions on the dataset
        for action, roles in permissions.items():
            if isinstance(action, Action):
                action = action.action
            for role in roles:
                dp = self.model.DatasetPermissions(action, dataset, role_id=role.id)
                self.sa_session.add(dp)
                flush_needed = True
        if flush_needed and flush:
            self.sa_session.flush()
        return ""

    def set_dataset_permission(self, dataset, permission={}):
        """
        Set a specific permission on a dataset, leaving all other current permissions on the dataset alone.
        Permission looks like: { Action.action : [ Role, Role ] }
        """
        flush_needed = False
        for action, roles in permission.items():
            if isinstance(action, Action):
                action = action.action
            # Delete the current specific permission on the dataset if one exists
            for dp in dataset.actions:
                if dp.action == action:
                    self.sa_session.delete(dp)
                    flush_needed = True
            # Add the new specific permission on the dataset
            for dp in [self.model.DatasetPermissions(action, dataset, role) for role in roles]:
                self.sa_session.add(dp)
                flush_needed = True
        if flush_needed:
            self.sa_session.flush()

    def get_permissions(self, item):
        """
        Return a dictionary containing the actions and associated roles on item
        where item is one of Library, LibraryFolder, LibraryDatasetDatasetAssociation,
        LibraryDataset, Dataset.  The dictionary looks like: { Action : [ Role, Role ] }.
        """
        permissions = {}
        for item_permission in item.actions:
            action = self.get_action(item_permission.action)
            if action in permissions:
                permissions[action].append(item_permission.role)
            else:
                permissions[action] = [item_permission.role]
        return permissions

    def get_accessible_request_types(self, trans, user):
        """Return all RequestTypes that the received user has permission to access."""
        accessible_request_types = []
        current_user_role_ids = [role.id for role in user.all_roles()]
        request_type_access_action = self.permitted_actions.REQUEST_TYPE_ACCESS.action
        restricted_request_type_ids = [rtp.request_type_id for rtp in trans.sa_session.query(trans.model.RequestTypePermissions)
            .filter(trans.model.RequestTypePermissions.table.c.action == request_type_access_action).distinct()]
        accessible_restricted_request_type_ids = [rtp.request_type_id for rtp in trans.sa_session.query(trans.model.RequestTypePermissions)
            .filter(and_(
                trans.model.RequestTypePermissions.table.c.action == request_type_access_action,
                trans.model.RequestTypePermissions.table.c.role_id.in_(current_user_role_ids)))]
        # Filter to get libraries accessible by the current user.  Get both
        # public libraries and restricted libraries accessible by the current user.
        for request_type in trans.sa_session.query(trans.model.RequestType) \
                                            .filter(and_(trans.model.RequestType.table.c.deleted == false(),
                                                         (or_(not_(trans.model.RequestType.table.c.id.in_(restricted_request_type_ids)),
                                                              trans.model.RequestType.table.c.id.in_(accessible_restricted_request_type_ids))))) \
                                            .order_by(trans.app.model.RequestType.name):
            accessible_request_types.append(request_type)
        return accessible_request_types

    def copy_dataset_permissions(self, src, dst):
        if not isinstance(src, self.model.Dataset):
            src = src.dataset
        if not isinstance(dst, self.model.Dataset):
            dst = dst.dataset
        self.set_all_dataset_permissions(dst, self.get_permissions(src))

    def privately_share_dataset(self, dataset, users=[]):
        intersect = None
        for user in users:
            roles = [ura.role for ura in user.roles if ura.role.type == self.model.Role.types.SHARING]
            if intersect is None:
                intersect = roles
            else:
                new_intersect = []
                for role in roles:
                    if role in intersect:
                        new_intersect.append(role)
                intersect = new_intersect
        sharing_role = None
        if intersect:
            for role in intersect:
                if not [_ for _ in [ura.user for ura in role.users] if _ not in users]:
                    # only use a role if it contains ONLY the users we're sharing with
                    sharing_role = role
                    break
        if sharing_role is None:
            sharing_role = self.model.Role(name="Sharing role for: " + ", ".join([u.email for u in users]),
                                           type=self.model.Role.types.SHARING)
            self.sa_session.add(sharing_role)
            self.sa_session.flush()
            for user in users:
                self.associate_components(user=user, role=sharing_role)
        self.set_dataset_permission(dataset, {self.permitted_actions.DATASET_ACCESS: [sharing_role]})

    def set_all_library_permissions(self, trans, library_item, permissions={}):
        # Set new permissions on library_item, eliminating all current permissions
        flush_needed = False
        for role_assoc in library_item.actions:
            self.sa_session.delete(role_assoc)
            flush_needed = True
        # Add the new permissions on library_item
        for item_class, permission_class in self.library_item_assocs:
            if isinstance(library_item, item_class):
                for action, roles in list(permissions.items()):
                    if isinstance(action, Action):
                        action = action.action
                    for role_assoc in [permission_class(action, library_item, role) for role in roles]:
                        self.sa_session.add(role_assoc)
                        flush_needed = True
                    if isinstance(library_item, self.model.LibraryDatasetDatasetAssociation):
                        # Permission setting related to DATASET_MANAGE_PERMISSIONS was broken for a period of time,
                        # so it is possible that some Datasets have no roles associated with the DATASET_MANAGE_PERMISSIONS
                        # permission.  In this case, we'll reset this permission to the library_item user's private role.
                        if not library_item.dataset.has_manage_permissions_roles(trans):
                            # Well this looks like a bug, this should be looked at.
                            # Default permissions above is single hash that keeps getting reeditted here
                            # because permission is being defined instead of permissions. -John
                            permissions[self.permitted_actions.DATASET_MANAGE_PERMISSIONS] = [trans.app.security_agent.get_private_user_role(library_item.user)]
                            self.set_dataset_permission(library_item.dataset, permissions)
                        if action == self.permitted_actions.LIBRARY_MANAGE.action and roles:
                            # Handle the special case when we are setting the LIBRARY_MANAGE_PERMISSION on a
                            # library_dataset_dataset_association since the roles need to be applied to the
                            # DATASET_MANAGE_PERMISSIONS permission on the associated dataset.
                            permissions = {}
                            permissions[self.permitted_actions.DATASET_MANAGE_PERMISSIONS] = roles
                            self.set_dataset_permission(library_item.dataset, permissions)
        if flush_needed:
            self.sa_session.flush()

    def set_library_item_permission(self, library_item, permission={}):
        """
        Set a specific permission on a library item, leaving all other current permissions on the item alone.
        Permission looks like: { Action.action : [ Role, Role ] }
        """
        flush_needed = False
        for action, roles in permission.items():
            if isinstance(action, Action):
                action = action.action
            # Delete the current specific permission on the library item if one exists
            for item_permission in library_item.actions:
                if item_permission.action == action:
                    self.sa_session.delete(item_permission)
                    flush_needed = True
            # Add the new specific permission on the library item
            if isinstance(library_item, self.model.LibraryDataset):
                for item_permission in [self.model.LibraryDatasetPermissions(action, library_item, role) for role in roles]:
                    self.sa_session.add(item_permission)
                    flush_needed = True
            elif isinstance(library_item, self.model.LibraryPermissions):
                for item_permission in [self.model.LibraryPermissions(action, library_item, role) for role in roles]:
                    self.sa_session.add(item_permission)
                    flush_needed = True
        if flush_needed:
            self.sa_session.flush()

    def library_is_public(self, library, contents=False):
        if contents:
            # Check all contained folders and datasets to find any that are not public
            if not self.folder_is_public(library.root_folder):
                return False
        # A library is considered public if there are no "access" actions associated with it.
        return self.permitted_actions.LIBRARY_ACCESS.action not in [a.action for a in library.actions]

    def library_is_unrestricted(self, library):
        # A library is considered unrestricted if there are no "access" actions associated with it.
        return self.permitted_actions.LIBRARY_ACCESS.action not in [a.action for a in library.actions]

    def make_library_public(self, library, contents=False):
        flush_needed = False
        if contents:
            # Make all contained folders (include deleted folders, but not purged folders), public
            self.make_folder_public(library.root_folder)
        # A library is considered public if there are no LIBRARY_ACCESS actions associated with it.
        for lp in library.actions:
            if lp.action == self.permitted_actions.LIBRARY_ACCESS.action:
                self.sa_session.delete(lp)
                flush_needed = True
        if flush_needed:
            self.sa_session.flush()

    def folder_is_public(self, folder):
        for sub_folder in folder.folders:
            if not self.folder_is_public(sub_folder):
                return False
        for library_dataset in folder.datasets:
            ldda = library_dataset.library_dataset_dataset_association
            if ldda and ldda.dataset and not self.dataset_is_public(ldda.dataset):
                return False
        return True

    def folder_is_unrestricted(self, folder):
        # TODO implement folder restrictions
        # for now all folders are _visible_ but the restricted datasets within are not visible
        return True

    def make_folder_public(self, folder):
        # Make all of the contents (include deleted contents, but not purged contents) of folder public
        for sub_folder in folder.folders:
            if not sub_folder.purged:
                self.make_folder_public(sub_folder)
        for library_dataset in folder.datasets:
            dataset = library_dataset.library_dataset_dataset_association.dataset
            if not dataset.purged and not self.dataset_is_public(dataset):
                self.make_dataset_public(dataset)

    def dataset_is_public(self, dataset):
        """
        A dataset is considered public if there are no "access" actions
        associated with it.  Any other actions ( 'manage permissions',
        'edit metadata' ) are irrelevant. Accessing dataset.actions
        will cause a query to be emitted.
        """
        return self.permitted_actions.DATASET_ACCESS.action not in [a.action for a in dataset.actions]

    def dataset_is_unrestricted(self, trans, dataset):
        """
        Different implementation of the method above with signature:
        def dataset_is_public( self, dataset )
        """
        return len(dataset.library_dataset_dataset_association.get_access_roles(trans)) == 0

    def dataset_is_private_to_user(self, trans, dataset):
        """
        If the LibraryDataset object has exactly one access role and that is
        the current user's private role then we consider the dataset private.
        """
        private_role = self.get_private_user_role(trans.user)
        access_roles = dataset.library_dataset_dataset_association.get_access_roles(trans)

        if len(access_roles) != 1:
            return False
        else:
            if access_roles[0].id == private_role.id:
                return True
            else:
                return False

    def datasets_are_public(self, trans, datasets):
        '''
        Given a transaction object and a list of Datasets, return
        a mapping from Dataset ids to whether the Dataset is public
        or not. All Dataset ids should be returned in the mapping's keys.
        '''
        # We go the other way around from dataset_is_public: we start with
        # all datasets being marked as public. If there is an access action
        # associated with the dataset, then we mark it as nonpublic:
        datasets_public = {}
        dataset_ids = [dataset.id for dataset in datasets]
        for dataset_id in dataset_ids:
            datasets_public[dataset_id] = True

        # Now get all datasets which have DATASET_ACCESS actions:
        access_data_perms = trans.sa_session.query(trans.app.model.DatasetPermissions) \
                                 .filter(and_(trans.app.model.DatasetPermissions.dataset_id.in_(dataset_ids),
                                              trans.app.model.DatasetPermissions.action == self.permitted_actions.DATASET_ACCESS.action)) \
                                 .all()
        # Every dataset returned has "access" privileges associated with it,
        # so it's not public.
        for permission in access_data_perms:
            datasets_public[permission.dataset_id] = False
        return datasets_public

    def make_dataset_public(self, dataset):
        # A dataset is considered public if there are no "access" actions associated with it.  Any
        # other actions ( 'manage permissions', 'edit metadata' ) are irrelevant.
        flush_needed = False
        for dp in dataset.actions:
            if dp.action == self.permitted_actions.DATASET_ACCESS.action:
                self.sa_session.delete(dp)
                flush_needed = True
        if flush_needed:
            self.sa_session.flush()

    def derive_roles_from_access(self, trans, item_id, cntrller, library=False, **kwd):
        # Check the access permission on a dataset.  If library is true, item_id refers to a library.  If library
        # is False, item_id refers to a dataset ( item_id must currently be decoded before being sent ).  The
        # cntrller param is the calling controller, which needs to be passed to get_legitimate_roles().
        msg = ''
        permissions = {}
        # accessible will be True only if at least 1 user has every role in DATASET_ACCESS_in
        accessible = False
        # legitimate will be True only if all roles in DATASET_ACCESS_in are in the set of roles returned from
        # get_legitimate_roles()
        # legitimate = False # TODO: not used
        # private_role_found will be true only if more than 1 role is being associated with the DATASET_ACCESS
        # permission on item, and at least 1 of the roles is private.
        private_role_found = False
        error = False
        for k, v in get_permitted_actions(filter='DATASET').items():
            # Change for removing the prefix '_in' from the roles select box
            in_roles = [self.sa_session.query(self.model.Role).get(x) for x in listify(kwd[k])]
            if not in_roles:
                in_roles = [self.sa_session.query(self.model.Role).get(x) for x in listify(kwd.get(k + '_in', []))]
            if v == self.permitted_actions.DATASET_ACCESS and in_roles:
                if library:
                    item = self.sa_session.query(self.model.Library).get(item_id)
                else:
                    item = self.sa_session.query(self.model.Dataset).get(item_id)
                if (library and not self.library_is_public(item)) or (not library and not self.dataset_is_public(item)):
                    # Ensure that roles being associated with DATASET_ACCESS are a subset of the legitimate roles
                    # derived from the roles associated with the access permission on item if it's not public.  This
                    # will keep illegitimate roles from being associated with the DATASET_ACCESS permission on the
                    # dataset (i.e., in the case where item is .a library, if Role1 is associated with LIBRARY_ACCESS,
                    # then only those users that have Role1 should be associated with DATASET_ACCESS.
                    legitimate_roles = self.get_legitimate_roles(trans, item, cntrller)
                    illegitimate_roles = []
                    for role in in_roles:
                        if role not in legitimate_roles:
                            illegitimate_roles.append(role)
                    if illegitimate_roles:
                        # This condition should never occur since illegitimate roles are filtered out of the set of
                        # roles displayed on the forms, but just in case there is a bug somewhere that incorrectly
                        # filters, we'll display this message.
                        error = True
                        msg += "The following roles are not associated with users that have the 'access' permission on this "
                        msg += "item, so they were incorrectly displayed: "
                        for role in illegitimate_roles:
                            msg += "%s, " % role.name
                        msg = msg.rstrip(", ")
                        new_in_roles = []
                        for role in in_roles:
                            if role in legitimate_roles:
                                new_in_roles.append(role)
                        in_roles = new_in_roles
                if len(in_roles) > 1:
                    # At least 1 user must have every role associated with the access
                    # permission on this dataset, or the dataset is not accessible.
                    # Since we have more than 1 role, none of them can be private.
                    for role in in_roles:
                        if role.type == self.model.Role.types.PRIVATE:
                            private_role_found = True
                            break
                if len(in_roles) == 1:
                    accessible = True
                else:
                    # At least 1 user must have every role associated with the access
                    # permission on this dataset, or the dataset is not accessible.
                    in_roles_set = set()
                    for role in in_roles:
                        in_roles_set.add(role)
                    users_set = set()
                    for role in in_roles:
                        for ura in role.users:
                            users_set.add(ura.user)
                        for gra in role.groups:
                            group = gra.group
                            for uga in group.users:
                                users_set.add(uga.user)
                    # Make sure that at least 1 user has every role being associated with the dataset.
                    for user in users_set:
                        user_roles_set = set()
                        for ura in user.roles:
                            user_roles_set.add(ura.role)
                        if in_roles_set.issubset(user_roles_set):
                            accessible = True
                            break
                if private_role_found or not accessible:
                    error = True
                    # Don't set the permissions for DATASET_ACCESS if inaccessible or multiple roles with
                    # at least 1 private, but set all other permissions.
                    permissions[self.get_action(v.action)] = []
                    msg = "At least 1 user must have every role associated with accessing datasets.  "
                    if private_role_found:
                        msg += "Since you are associating more than 1 role, no private roles are allowed."
                    if not accessible:
                        msg += "The roles you attempted to associate for access would make the datasets in-accessible by everyone."
                else:
                    permissions[self.get_action(v.action)] = in_roles
            else:
                permissions[self.get_action(v.action)] = in_roles
        return permissions, in_roles, error, msg

    def copy_library_permissions(self, trans, source_library_item, target_library_item, user=None):
        # Copy all relevant permissions from source.
        permissions = {}
        for role_assoc in source_library_item.actions:
            if role_assoc.action != self.permitted_actions.LIBRARY_ACCESS.action:
                # LIBRARY_ACCESS is a special permission that is set only at the library level.
                if role_assoc.action in permissions:
                    permissions[role_assoc.action].append(role_assoc.role)
                else:
                    permissions[role_assoc.action] = [role_assoc.role]
        self.set_all_library_permissions(trans, target_library_item, permissions)
        if user:
            item_class = None
            for item_class, permission_class in self.library_item_assocs:
                if isinstance(target_library_item, item_class):
                    break
            if item_class:
                # Make sure user's private role is included
                private_role = self.model.security_agent.get_private_user_role(user)
                for name, action in self.permitted_actions.items():
                    if not permission_class.filter_by(role_id=private_role.id, action=action.action).first():
                        lp = permission_class(action.action, target_library_item, private_role)
                        self.sa_session.add(lp)
                        self.sa_session.flush()
            else:
                raise Exception('Invalid class (%s) specified for target_library_item (%s)' %
                                (target_library_item.__class__, target_library_item.__class__.__name__))

    def get_permitted_libraries(self, trans, user, actions):
        """
        This method is historical (it is not currently used), but may be useful again at some
        point.  It returns a dictionary whose keys are library objects and whose values are a
        comma-separated string of folder ids.  This method works with the show_library_item()
        method below, and it returns libraries for which the received user has permission to
        perform the received actions.  Here is an example call to this method to return all
        libraries for which the received user has LIBRARY_ADD permission::

            libraries = trans.app.security_agent.get_permitted_libraries( trans, user,
                [ trans.app.security_agent.permitted_actions.LIBRARY_ADD ] )
        """
        all_libraries = trans.sa_session.query(trans.app.model.Library) \
                                        .filter(trans.app.model.Library.table.c.deleted == false()) \
                                        .order_by(trans.app.model.Library.name)
        roles = user.all_roles()
        actions_to_check = actions
        # The libraries dictionary looks like: { library : '1,2' }, library : '3' }
        # Its keys are the libraries that should be displayed for the current user and whose values are a
        # string of comma-separated folder ids, of the associated folders the should NOT be displayed.
        # The folders that should not be displayed may not be a complete list, but it is ultimately passed
        # to the calling method to keep from re-checking the same folders when the library / folder
        # select lists are rendered.
        libraries = {}
        for library in all_libraries:
            can_show, hidden_folder_ids = self.show_library_item(self, roles, library, actions_to_check)
            if can_show:
                libraries[library] = hidden_folder_ids
        return libraries

    def show_library_item(self, user, roles, library_item, actions_to_check, hidden_folder_ids=''):
        """
        This method must be sent an instance of Library() or LibraryFolder().  Recursive execution produces a
        comma-separated string of folder ids whose folders do NOT meet the criteria for showing. Along with
        the string, True is returned if the current user has permission to perform any 1 of actions_to_check
        on library_item. Otherwise, cycle through all sub-folders in library_item until one is found that meets
        this criteria, if it exists.  This method does not necessarily scan the entire library as it returns
        when it finds the first library_item that allows user to perform any one action in actions_to_check.
        """
        for action in actions_to_check:
            if self.allow_action(roles, action, library_item):
                return True, hidden_folder_ids
        if isinstance(library_item, self.model.Library):
            return self.show_library_item(user, roles, library_item.root_folder, actions_to_check, hidden_folder_ids='')
        if isinstance(library_item, self.model.LibraryFolder):
            for folder in library_item.active_folders:
                can_show, hidden_folder_ids = self.show_library_item(user, roles, folder, actions_to_check, hidden_folder_ids=hidden_folder_ids)
                if can_show:
                    return True, hidden_folder_ids
                if hidden_folder_ids:
                    hidden_folder_ids = '%s,%d' % (hidden_folder_ids, folder.id)
                else:
                    hidden_folder_ids = '%d' % folder.id
        return False, hidden_folder_ids

    def get_showable_folders(self, user, roles, library_item, actions_to_check, hidden_folder_ids=[], showable_folders=[]):
        """
        This method must be sent an instance of Library(), all the folders of which are scanned to determine if
        user is allowed to perform any action in actions_to_check. The param hidden_folder_ids, if passed, should
        contain a list of folder IDs which was generated when the library was previously scanned
        using the same actions_to_check. A list of showable folders is generated. This method scans the entire library.
        """
        if isinstance(library_item, self.model.Library):
            return self.get_showable_folders(user, roles, library_item.root_folder, actions_to_check, showable_folders=[])
        if isinstance(library_item, self.model.LibraryFolder):
            if library_item.id not in hidden_folder_ids:
                for action in actions_to_check:
                    if self.allow_action(roles, action, library_item):
                        showable_folders.append(library_item)
                        break
            for folder in library_item.active_folders:
                self.get_showable_folders(user, roles, folder, actions_to_check, showable_folders=showable_folders)
        return showable_folders

    def set_entity_user_associations(self, users=[], roles=[], groups=[], delete_existing_assocs=True):
        for user in users:
            if delete_existing_assocs:
                flush_needed = False
                for a in user.non_private_roles + user.groups:
                    self.sa_session.delete(a)
                    flush_needed = True
                if flush_needed:
                    self.sa_session.flush()
            self.sa_session.refresh(user)
            for role in roles:
                # Make sure we are not creating an additional association with a PRIVATE role
                if role not in [x.role for x in user.roles]:
                    self.associate_components(user=user, role=role)
            for group in groups:
                self.associate_components(user=user, group=group)

    def set_entity_group_associations(self, groups=[], users=[], roles=[], delete_existing_assocs=True):
        for group in groups:
            if delete_existing_assocs:
                flush_needed = False
                for a in group.roles + group.users:
                    self.sa_session.delete(a)
                    flush_needed = True
                if flush_needed:
                    self.sa_session.flush()
            for role in roles:
                self.associate_components(group=group, role=role)
            for user in users:
                self.associate_components(group=group, user=user)

    def set_entity_role_associations(self, roles=[], users=[], groups=[], delete_existing_assocs=True):
        for role in roles:
            if delete_existing_assocs:
                flush_needed = False
                for a in role.users + role.groups:
                    self.sa_session.delete(a)
                    flush_needed = True
                if flush_needed:
                    self.sa_session.flush()
            for user in users:
                self.associate_components(user=user, role=role)
            for group in groups:
                self.associate_components(group=group, role=role)

    def get_component_associations(self, **kwd):
        assert len(kwd) == 2, 'You must specify exactly 2 Galaxy security components to check for associations.'
        if 'dataset' in kwd:
            if 'action' in kwd:
                return self.sa_session.query(self.model.DatasetPermissions).filter_by(action=kwd['action'].action, dataset_id=kwd['dataset'].id).first()
        elif 'user' in kwd:
            if 'group' in kwd:
                return self.sa_session.query(self.model.UserGroupAssociation).filter_by(group_id=kwd['group'].id, user_id=kwd['user'].id).first()
            elif 'role' in kwd:
                return self.sa_session.query(self.model.UserRoleAssociation).filter_by(role_id=kwd['role'].id, user_id=kwd['user'].id).first()
        elif 'group' in kwd:
            if 'role' in kwd:
                return self.sa_session.query(self.model.GroupRoleAssociation).filter_by(role_id=kwd['role'].id, group_id=kwd['group'].id).first()
        raise Exception('No valid method of associating provided components: %s' % kwd)

    def check_folder_contents(self, user, roles, folder, hidden_folder_ids=''):
        """
        This method must always be sent an instance of LibraryFolder().  Recursive execution produces a
        comma-separated string of folder ids whose folders do NOT meet the criteria for showing.  Along
        with the string, True is returned if the current user has permission to access folder. Otherwise,
        cycle through all sub-folders in folder until one is found that meets this criteria, if it exists.
        This method does not necessarily scan the entire library as it returns when it finds the first
        folder that is accessible to user.
        """
        # If a folder is writeable, it's accessable and we need not go further
        if self.can_add_library_item(roles, folder):
            return True, ''
        action = self.permitted_actions.DATASET_ACCESS

        lddas = self.sa_session.query(self.model.LibraryDatasetDatasetAssociation) \
                               .join("library_dataset") \
                               .filter(self.model.LibraryDataset.folder == folder) \
                               .join("dataset") \
                               .options(eagerload_all("dataset.actions")) \
                               .all()

        for ldda in lddas:
            ldda_access_permissions = self.get_item_actions(action, ldda.dataset)
            if not ldda_access_permissions:
                # Dataset is public
                return True, hidden_folder_ids
            for ldda_access_permission in ldda_access_permissions:
                if ldda_access_permission.role in roles:
                    # The current user has access permission on the dataset
                    return True, hidden_folder_ids
        for sub_folder in folder.active_folders:
            can_access, hidden_folder_ids = self.check_folder_contents(user, roles, sub_folder, hidden_folder_ids=hidden_folder_ids)
            if can_access:
                return True, hidden_folder_ids
            if hidden_folder_ids:
                hidden_folder_ids = '%s,%d' % (hidden_folder_ids, sub_folder.id)
            else:
                hidden_folder_ids = '%d' % sub_folder.id
        return False, hidden_folder_ids

    def can_access_request_type(self, roles, request_type):
        action = self.permitted_actions.REQUEST_TYPE_ACCESS
        request_type_actions = []
        for permission in request_type.actions:
            if permission.action == action.action:
                request_type_actions.append(permission)
        if not request_type_actions:
            return True
        ret_val = False
        for request_type_action in request_type_actions:
            if request_type_action.role in roles:
                ret_val = True
                break
        return ret_val

    def set_request_type_permissions(self, request_type, permissions={}):
        # Set new permissions on request_type, eliminating all current permissions
        for role_assoc in request_type.actions:
            self.sa_session.delete(role_assoc)
        # Add the new permissions on request_type
        permission_class = self.model.RequestTypePermissions
        flush_needed = False
        for action, roles in permissions.items():
            if isinstance(action, Action):
                action = action.action
            for role_assoc in [permission_class(action, request_type, role) for role in roles]:
                self.sa_session.add(role_assoc)
                flush_needed = True
        if flush_needed:
            self.sa_session.flush()


class HostAgent(RBACAgent):
    """
    A simple security agent which allows access to datasets based on host.
    This exists so that externals sites such as UCSC can gain access to
    datasets which have permissions which would normally prevent such access.
    """
    # TODO: Make sites user configurable
    sites = Bunch(
        ucsc_main=('hgw1.cse.ucsc.edu', 'hgw2.cse.ucsc.edu', 'hgw3.cse.ucsc.edu', 'hgw4.cse.ucsc.edu',
                   'hgw5.cse.ucsc.edu', 'hgw6.cse.ucsc.edu', 'hgw7.cse.ucsc.edu', 'hgw8.cse.ucsc.edu'),
        ucsc_test=('hgwdev.cse.ucsc.edu', ),
        ucsc_archaea=('lowepub.cse.ucsc.edu', )
    )

    def __init__(self, model, permitted_actions=None):
        self.model = model
        if permitted_actions:
            self.permitted_actions = permitted_actions

    @property
    def sa_session(self):
        """Returns a SQLAlchemy session"""
        return self.model.context

    def allow_action(self, addr, action, **kwd):
        if 'dataset' in kwd and action == self.permitted_actions.DATASET_ACCESS:
            hda = kwd['dataset']
            if action == self.permitted_actions.DATASET_ACCESS and action.action not in [dp.action for dp in hda.dataset.actions]:
                log.debug('Allowing access to public dataset with hda: %i.' % hda.id)
                return True  # dataset has no roles associated with the access permission, thus is already public
            hdadaa = self.sa_session.query(self.model.HistoryDatasetAssociationDisplayAtAuthorization) \
                                    .filter_by(history_dataset_association_id=hda.id).first()
            if not hdadaa:
                log.debug('Denying access to private dataset with hda: %i.  No hdadaa record for this dataset.' % hda.id)
                return False  # no auth
            # We could just look up the reverse of addr, but then we'd also
            # have to verify it with the forward address and special case any
            # IPs (instead of hosts) in the server list.
            #
            # This would be improved by caching, but that's what the OS's name
            # service cache daemon is for (you ARE running nscd, right?).
            for server in HostAgent.sites.get(hdadaa.site, []):
                # We're going to search in order, but if the remote site is load
                # balancing their connections (as UCSC does), this is okay.
                try:
                    if socket.gethostbyname(server) == addr:
                        break  # remote host is in the server list
                except (socket.error, socket.gaierror):
                    pass  # can't resolve, try next
            else:
                log.debug('Denying access to private dataset with hda: %i.  Remote addr is not a valid server for site: %s.' % (hda.id, hdadaa.site))
                return False  # remote addr is not in the server list
            if (datetime.utcnow() - hdadaa.update_time) > timedelta(seconds=60):
                log.debug('Denying access to private dataset with hda: %i.  Authorization was granted, but has expired.' % hda.id)
                return False  # not authz'd in the last 60 seconds
            log.debug('Allowing access to private dataset with hda: %i.  Remote server is: %s.' % (hda.id, server))
            return True
        else:
            raise Exception('The dataset access permission is the only valid permission in the host security agent.')

    def set_dataset_permissions(self, hda, user, site):
        hdadaa = self.sa_session.query(self.model.HistoryDatasetAssociationDisplayAtAuthorization) \
                                .filter_by(history_dataset_association_id=hda.id).first()
        if hdadaa:
            hdadaa.update_time = datetime.utcnow()
        else:
            hdadaa = self.model.HistoryDatasetAssociationDisplayAtAuthorization(hda=hda, user=user, site=site)
        self.sa_session.add(hdadaa)
        self.sa_session.flush()


def get_permitted_actions(filter=None):
    '''Utility method to return a subset of RBACAgent's permitted actions'''
    if filter is None:
        return RBACAgent.permitted_actions
    tmp_bunch = Bunch()
    [tmp_bunch.__dict__.__setitem__(k, v) for k, v in RBACAgent.permitted_actions.items() if k.startswith(filter)]
    return tmp_bunch
