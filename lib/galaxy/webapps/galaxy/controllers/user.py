"""
Contains the user interface in the Universe class
"""

import logging
import random
import socket
import urllib
from datetime import datetime, timedelta

from markupsafe import escape
from sqlalchemy import and_, or_, func, true
from galaxy import model
from galaxy import util
from galaxy import web
from galaxy.queue_worker import send_local_control_task
from galaxy.security.validate_user_input import (transform_publicname,
                                                 validate_email,
                                                 validate_password,
                                                 validate_publicname)
from galaxy.util import biostar, hash_util
from galaxy.web import url_for
from galaxy.web.base.controller import (BaseUIController,
                                        CreatesApiKeysMixin,
                                        CreatesUsersMixin,
                                        UsesFormDefinitionsMixin)
from galaxy.web.form_builder import CheckboxField
from galaxy.web.framework.helpers import grids, time_ago

log = logging.getLogger(__name__)

REQUIRE_LOGIN_TEMPLATE = """
<p>
    This %s has been configured such that only users who are logged in may use it.%s
</p>
"""

PASSWORD_RESET_TEMPLATE = """
To reset your Galaxy password for the instance at %s use the following link,
which will expire %s.

%s

If you did not make this request, no action is necessary on your part, though
you may want to notify an administrator.

If you're having trouble using the link when clicking it from email client, you
can also copy and paste it into your browser.
"""


class UserOpenIDGrid(grids.Grid):
    use_panels = False
    title = "OpenIDs linked to your account"
    model_class = model.UserOpenID
    template = '/user/openid_manage.mako'
    default_filter = {"openid": "All"}
    default_sort_key = "-create_time"
    columns = [
        grids.TextColumn("OpenID URL", key="openid", link=(lambda x: dict(action='openid_auth', login_button="Login", openid_url=x.openid if not x.provider else '', openid_provider=x.provider, auto_associate=True))),
        grids.GridColumn("Created", key="create_time", format=time_ago),
    ]
    operations = [
        grids.GridOperation("Delete", async_compatible=True),
    ]

    def build_initial_query(self, trans, **kwd):
        return trans.sa_session.query(self.model_class).filter(self.model_class.user_id == trans.user.id)


class User(BaseUIController, UsesFormDefinitionsMixin, CreatesUsersMixin, CreatesApiKeysMixin):
    user_openid_grid = UserOpenIDGrid()
    installed_len_files = None

    @web.expose
    def openid_auth(self, trans, **kwd):
        '''Handles user request to access an OpenID provider'''
        if not trans.app.config.enable_openid:
            return trans.show_error_message('OpenID authentication is not enabled in this instance of Galaxy')
        message = 'Unspecified failure authenticating via OpenID'
        auto_associate = util.string_as_bool(kwd.get('auto_associate', False))
        use_panels = util.string_as_bool(kwd.get('use_panels', False))
        consumer = trans.app.openid_manager.get_consumer(trans)
        openid_url = kwd.get('openid_url', '')
        openid_provider = kwd.get('openid_provider', '')
        if openid_url:
            openid_provider_obj = trans.app.openid_providers.new_provider_from_identifier(openid_url)
        elif openid_provider:
            openid_provider_obj = trans.app.openid_providers.get(openid_provider)
        else:
            message = 'An OpenID provider was not specified'
        redirect = kwd.get('redirect', '').strip()
        if not redirect:
            redirect = ' '
        if openid_provider_obj:
            process_url = trans.request.base.rstrip('/') + url_for(controller='user', action='openid_process', redirect=redirect, openid_provider=openid_provider, auto_associate=auto_associate)  # None of these values can be empty, or else a verification error will occur
            request = None
            try:
                request = consumer.begin(openid_provider_obj.op_endpoint_url)
                if request is None:
                    message = 'No OpenID services are available at %s' % openid_provider_obj.op_endpoint_url
            except Exception as e:
                message = 'Failed to begin OpenID authentication: %s' % str(e)
            if request is not None:
                trans.app.openid_manager.add_sreg(trans, request, required=openid_provider_obj.sreg_required, optional=openid_provider_obj.sreg_optional)
                if request.shouldSendRedirect():
                    redirect_url = request.redirectURL(
                        trans.request.base, process_url)
                    trans.app.openid_manager.persist_session(trans, consumer)
                    return trans.response.send_redirect(redirect_url)
                else:
                    form = request.htmlMarkup(trans.request.base, process_url, form_tag_attrs={'id': 'openid_message', 'target': '_top'})
                    trans.app.openid_manager.persist_session(trans, consumer)
                    return form
        return trans.response.send_redirect(url_for(controller='user',
                                                    action='login',
                                                    redirect=redirect,
                                                    use_panels=use_panels,
                                                    message=message,
                                                    status='error'))

    @web.expose
    def openid_process(self, trans, **kwd):
        '''Handle's response from OpenID Providers'''
        if not trans.app.config.enable_openid:
            return trans.show_error_message('OpenID authentication is not enabled in this instance of Galaxy')
        auto_associate = util.string_as_bool(kwd.get('auto_associate', False))
        action = 'login'
        if trans.user:
            action = 'openid_manage'
        if trans.app.config.support_url is not None:
            contact = '<a href="%s">support</a>' % trans.app.config.support_url
        else:
            contact = 'support'
        message = 'Verification failed for an unknown reason.  Please contact %s for assistance.' % (contact)
        status = 'error'
        consumer = trans.app.openid_manager.get_consumer(trans)
        info = consumer.complete(kwd, trans.request.url)
        display_identifier = info.getDisplayIdentifier()
        redirect = kwd.get('redirect', '').strip()
        openid_provider = kwd.get('openid_provider', None)
        if info.status == trans.app.openid_manager.FAILURE and display_identifier:
            message = "Login via OpenID failed.  The technical reason for this follows, please include this message in your email if you need to %s to resolve this problem: %s" % (contact, info.message)
            return trans.response.send_redirect(url_for(controller='user',
                                                        action=action,
                                                        use_panels=True,
                                                        redirect=redirect,
                                                        message=message,
                                                        status='error'))
        elif info.status == trans.app.openid_manager.SUCCESS:
            if info.endpoint.canonicalID:
                display_identifier = info.endpoint.canonicalID
            openid_provider_obj = trans.app.openid_providers.get(openid_provider)
            user_openid = trans.sa_session.query(trans.app.model.UserOpenID).filter(trans.app.model.UserOpenID.table.c.openid == display_identifier).first()
            if not openid_provider_obj and user_openid and user_openid.provider:
                openid_provider_obj = trans.app.openid_providers.get(user_openid.provider)
            if not openid_provider_obj:
                openid_provider_obj = trans.app.openid_providers.new_provider_from_identifier(display_identifier)
            if not user_openid:
                user_openid = trans.app.model.UserOpenID(session=trans.galaxy_session, openid=display_identifier)
            if not user_openid.user:
                user_openid.session = trans.galaxy_session
            if not user_openid.provider and openid_provider:
                user_openid.provider = openid_provider
            if trans.user:
                if user_openid.user and user_openid.user.id != trans.user.id:
                    message = "The OpenID <strong>%s</strong> is already associated with another Galaxy account, <strong>%s</strong>.  Please disassociate it from that account before attempting to associate it with a new account." % (escape(display_identifier), escape(user_openid.user.email))
                if not trans.user.active and trans.app.config.user_activation_on:  # Account activation is ON and the user is INACTIVE.
                    if (trans.app.config.activation_grace_period != 0):  # grace period is ON
                        if self.is_outside_grace_period(trans, trans.user.create_time):  # User is outside the grace period. Login is disabled and he will have the activation email resent.
                            message, status = self.resend_verification_email(trans, trans.user.email, trans.user.username)
                        else:  # User is within the grace period, let him log in.
                            pass
                    else:  # Grace period is off. Login is disabled and user will have the activation email resent.
                        message, status = self.resend_verification_email(trans, trans.user.email, trans.user.username)
                elif not user_openid.user or user_openid.user == trans.user:
                    if openid_provider_obj.id:
                        user_openid.provider = openid_provider_obj.id
                    user_openid.session = trans.galaxy_session
                    if not openid_provider_obj.never_associate_with_user:
                        if not auto_associate and (user_openid.user and user_openid.user.id == trans.user.id):
                            message = "The OpenID <strong>%s</strong> is already associated with your Galaxy account, <strong>%s</strong>." % (escape(display_identifier), escape(trans.user.email))
                            status = "warning"
                        else:
                            message = "The OpenID <strong>%s</strong> has been associated with your Galaxy account, <strong>%s</strong>." % (escape(display_identifier), escape(trans.user.email))
                            status = "done"
                        user_openid.user = trans.user
                        trans.sa_session.add(user_openid)
                        trans.sa_session.flush()
                        trans.log_event("User associated OpenID: %s" % display_identifier)
                    else:
                        message = "The OpenID <strong>%s</strong> cannot be used to log into your Galaxy account, but any post authentication actions have been performed." % escape(openid_provider_obj.name)
                        status = "info"
                    openid_provider_obj.post_authentication(trans, trans.app.openid_manager, info)
                    if redirect:
                        message = '%s<br>Click <a href="%s"><strong>here</strong></a> to return to the page you were previously viewing.' % (message, escape(self.__get_redirect_url(redirect)))
                if redirect and status != "error":
                    return trans.response.send_redirect(self.__get_redirect_url(redirect))
                return trans.response.send_redirect(url_for(controller='user',
                                                     action='openid_manage',
                                                     use_panels=True,
                                                     redirect=redirect,
                                                     message=message,
                                                     status=status))
            elif user_openid.user:
                trans.handle_user_login(user_openid.user)
                trans.log_event("User logged in via OpenID: %s" % display_identifier)
                openid_provider_obj.post_authentication(trans, trans.app.openid_manager, info)
                if not redirect:
                    redirect = url_for('/')
                redirect = self.__get_redirect_url(redirect)
                return trans.response.send_redirect(redirect)
            trans.sa_session.add(user_openid)
            trans.sa_session.flush()
            message = "OpenID authentication was successful, but you need to associate your OpenID with a Galaxy account."
            sreg_resp = trans.app.openid_manager.get_sreg(info)
            try:
                sreg_username_name = openid_provider_obj.use_for.get('username')
                username = sreg_resp.get(sreg_username_name, '')
            except AttributeError:
                username = ''
            try:
                sreg_email_name = openid_provider_obj.use_for.get('email')
                email = sreg_resp.get(sreg_email_name, '')
            except AttributeError:
                email = ''
            # OpenID success, but user not logged in, and not previously associated
            return trans.response.send_redirect(url_for(controller='user',
                                                 action='openid_associate',
                                                 use_panels=True,
                                                 redirect=redirect,
                                                 username=username,
                                                 email=email,
                                                 message=message,
                                                 status='warning'))
        elif info.status == trans.app.openid_manager.CANCEL:
            message = "Login via OpenID was cancelled by an action at the OpenID provider's site."
            status = "warning"
        elif info.status == trans.app.openid_manager.SETUP_NEEDED:
            if info.setup_url:
                return trans.response.send_redirect(info.setup_url)
            else:
                message = "Unable to log in via OpenID.  Setup at the provider is required before this OpenID can be used.  Please visit your provider's site to complete this step."
        return trans.response.send_redirect(url_for(controller='user',
                                                    action=action,
                                                    use_panels=True,
                                                    redirect=redirect,
                                                    message=message,
                                                    status=status))

    @web.expose
    def openid_associate(self, trans, cntrller='user', **kwd):
        '''Associates a user with an OpenID log in'''
        if not trans.app.config.enable_openid:
            return trans.show_error_message('OpenID authentication is not enabled in this instance of Galaxy')
        use_panels = util.string_as_bool(kwd.get('use_panels', False))
        message = escape(kwd.get('message', ''))
        status = kwd.get('status', 'done')
        email = kwd.get('email', '')
        username = kwd.get('username', '')
        redirect = kwd.get('redirect', '').strip()
        params = util.Params(kwd)
        is_admin = cntrller == 'admin' and trans.user_is_admin()
        openids = trans.galaxy_session.openids
        user = None
        if not openids:
            return trans.show_error_message('You have not successfully completed an OpenID authentication in this session.  You can do so on the <a href="%s">login</a> page.' % url_for(controller='user', action='login', use_panels=use_panels))
        elif is_admin:
            return trans.show_error_message('Associating OpenIDs with accounts cannot be done by administrators.')
        if kwd.get('login_button', False):
            message, status, user, success = self.__validate_login(trans, **kwd)
            if success:
                openid_objs = []
                for openid in openids:
                    openid_provider_obj = trans.app.openid_providers.get(openid.provider)
                    if not openid_provider_obj or not openid_provider_obj.never_associate_with_user:
                        openid.user = user
                        trans.sa_session.add(openid)
                        trans.log_event("User associated OpenID: %s" % openid.openid)
                    if openid_provider_obj and openid_provider_obj.has_post_authentication_actions():
                        openid_objs.append(openid_provider_obj)
                trans.sa_session.flush()
                if len(openid_objs) == 1:
                    return trans.response.send_redirect(url_for(controller='user', action='openid_auth', openid_provider=openid_objs[0].id, redirect=redirect, auto_associate=True))
                elif openid_objs:
                    message = 'You have authenticated with several OpenID providers, please click the following links to execute the post authentication actions. '
                    message = "%s<br/><ul>" % (message)
                    for openid in openid_objs:
                        message = '%s<li><a href="%s" target="_blank">%s</a></li>' % (message, url_for(controller='user', action='openid_auth', openid_provider=openid.id, redirect=redirect, auto_associate=True), openid.name)
                    message = "%s</ul>" % (message)
                    return trans.response.send_redirect(url_for(controller='user',
                                                                action='openid_manage',
                                                                use_panels=use_panels,
                                                                redirect=redirect,
                                                                message=message,
                                                                status='info'))
                if redirect:
                    return trans.response.send_redirect(redirect)
                return trans.response.send_redirect(url_for(controller='user',
                                                            action='openid_manage',
                                                            use_panels=use_panels,
                                                            redirect=redirect,
                                                            message=message,
                                                            status='info'))
        if kwd.get('create_user_button', False):
            password = kwd.get('password', '')
            confirm = kwd.get('confirm', '')
            subscribe = params.get('subscribe', '')
            subscribe_checked = CheckboxField.is_checked(subscribe)
            error = ''
            if not trans.app.config.allow_user_creation and not trans.user_is_admin():
                error = 'User registration is disabled.  Please contact your local Galaxy administrator for an account.'
            else:
                # Check email and password validity
                error = self.__validate(trans, params, email, password, confirm, username)
                if not error:
                    # all the values are valid
                    message, status, user, success = self.__register(trans,
                                                                     cntrller,
                                                                     subscribe_checked,
                                                                     **kwd)
                    if success:
                        openid_objs = []
                        for openid in openids:
                            openid_provider_obj = trans.app.openid_providers.get(openid.provider)
                            if not openid_provider_obj:
                                openid_provider_obj = trans.app.openid_providers.new_provider_from_identifier(openid.identifier)
                            if not openid_provider_obj.never_associate_with_user:
                                openid.user = user
                                trans.sa_session.add(openid)
                                trans.log_event("User associated OpenID: %s" % openid.openid)
                            if openid_provider_obj.has_post_authentication_actions():
                                openid_objs.append(openid_provider_obj)
                        trans.sa_session.flush()
                        if len(openid_objs) == 1:
                            return trans.response.send_redirect(url_for(controller='user', action='openid_auth', openid_provider=openid_objs[0].id, redirect=redirect, auto_associate=True))
                        elif openid_objs:
                            message = 'You have authenticated with several OpenID providers, please click the following links to execute the post authentication actions. '
                            message = "%s<br/><ul>" % (message)
                            for openid in openid_objs:
                                message = '%s<li><a href="%s" target="_blank">%s</a></li>' % (message, url_for(controller='user', action='openid_auth', openid_provider=openid.id, redirect=redirect, auto_associate=True), openid.name)
                            message = "%s</ul>" % (message)
                            return trans.response.send_redirect(url_for(controller='user',
                                                                        action='openid_manage',
                                                                        use_panels=True,
                                                                        redirect=redirect,
                                                                        message=message,
                                                                        status='info'))
                        if redirect:
                            return trans.response.send_redirect(redirect)
                        return trans.response.send_redirect(url_for(controller='user',
                                                                    action='openid_manage',
                                                                    use_panels=use_panels,
                                                                    redirect=redirect,
                                                                    message=message,
                                                                    status='info'))
                else:
                    message = error
                    status = 'error'
        return trans.fill_template('/user/openid_associate.mako',
                                   cntrller=cntrller,
                                   email=email,
                                   password='',
                                   confirm='',
                                   username=transform_publicname(trans, username),
                                   header='',
                                   use_panels=use_panels,
                                   redirect=redirect,
                                   refresh_frames=[],
                                   message=message,
                                   status=status,
                                   active_view="user",
                                   subscribe_checked=False,
                                   openids=openids)

    @web.expose
    @web.require_login('manage OpenIDs')
    def openid_disassociate(self, trans, **kwd):
        '''Disassociates a user with an OpenID'''
        if not trans.app.config.enable_openid:
            return trans.show_error_message('OpenID authentication is not enabled in this instance of Galaxy')
        params = util.Params(kwd)
        ids = params.get('id', None)
        message = params.get('message', None)
        status = params.get('status', None)
        use_panels = params.get('use_panels', False)
        user_openids = []
        if not ids:
            message = 'You must select at least one OpenID to disassociate from your Galaxy account.'
            status = 'error'
        else:
            ids = util.listify(params.id)
            for id in ids:
                id = trans.security.decode_id(id)
                user_openid = trans.sa_session.query(trans.app.model.UserOpenID).get(int(id))
                if not user_openid or (trans.user.id != user_openid.user_id):
                    message = 'The selected OpenID(s) are not associated with your Galaxy account.'
                    status = 'error'
                    user_openids = []
                    break
                user_openids.append(user_openid)
            if user_openids:
                deleted_urls = []
                for user_openid in user_openids:
                    trans.sa_session.delete(user_openid)
                    deleted_urls.append(user_openid.openid)
                trans.sa_session.flush()
                for deleted_url in deleted_urls:
                    trans.log_event("User disassociated OpenID: %s" % deleted_url)
                message = '%s OpenIDs were disassociated from your Galaxy account.' % len(ids)
                status = 'done'
        return trans.response.send_redirect(url_for(controller='user',
                                                    action='openid_manage',
                                                    use_panels=use_panels,
                                                    message=message,
                                                    status=status))

    @web.expose
    @web.require_login('manage OpenIDs')
    def openid_manage(self, trans, **kwd):
        '''Manage OpenIDs for user'''
        if not trans.app.config.enable_openid:
            return trans.show_error_message('OpenID authentication is not enabled in this instance of Galaxy')
        use_panels = kwd.get('use_panels', False)
        if 'operation' in kwd:
            operation = kwd['operation'].lower()
            if operation == "delete":
                return trans.response.send_redirect(url_for(controller='user',
                                                            action='openid_disassociate',
                                                            use_panels=use_panels,
                                                            id=kwd['id']))
        kwd['redirect'] = kwd.get('redirect', url_for(controller='user', action='openid_manage', use_panels=True)).strip()
        kwd['openid_providers'] = trans.app.openid_providers
        return self.user_openid_grid(trans, **kwd)

    @web.expose
    def login(self, trans, refresh_frames=[], **kwd):
        '''Handle Galaxy Log in'''
        referer = trans.request.referer or ''
        redirect = self.__get_redirect_url(kwd.get('redirect', referer).strip())
        redirect_url = ''  # always start with redirect_url being empty
        use_panels = util.string_as_bool(kwd.get('use_panels', False))
        message = kwd.get('message', '')
        status = kwd.get('status', 'done')
        header = ''
        user = trans.user
        login = kwd.get('login', '')
        if user:
            # Already logged in.
            redirect_url = redirect
            message = 'You are already logged in.'
            status = 'info'
        elif kwd.get('login_button', False):
            if trans.webapp.name == 'galaxy' and not refresh_frames:
                if trans.app.config.require_login:
                    refresh_frames = ['masthead', 'history', 'tools']
                else:
                    refresh_frames = ['masthead', 'history']
            csrf_check = trans.check_csrf_token()
            if csrf_check:
                return csrf_check
            message, status, user, success = self.__validate_login(trans, **kwd)
            if success:
                redirect_url = redirect
        if not user and trans.app.config.require_login:
            if trans.app.config.allow_user_creation:
                create_account_str = "  If you don't already have an account, <a href='%s'>you may create one</a>." % \
                    web.url_for(controller='user', action='create', cntrller='user')
                if trans.webapp.name == 'galaxy':
                    header = REQUIRE_LOGIN_TEMPLATE % ("Galaxy instance", create_account_str)
                else:
                    header = REQUIRE_LOGIN_TEMPLATE % ("Galaxy tool shed", create_account_str)
            else:
                if trans.webapp.name == 'galaxy':
                    header = REQUIRE_LOGIN_TEMPLATE % ("Galaxy instance", "")
                else:
                    header = REQUIRE_LOGIN_TEMPLATE % ("Galaxy tool shed", "")
        return trans.fill_template('/user/login.mako',
                                   login=login,
                                   header=header,
                                   use_panels=use_panels,
                                   redirect_url=redirect_url,
                                   redirect=redirect,
                                   refresh_frames=refresh_frames,
                                   message=message,
                                   status=status,
                                   openid_providers=trans.app.openid_providers,
                                   form_input_auto_focus=True,
                                   active_view="user")

    def __validate_login(self, trans, **kwd):
        """Validates numerous cases that might happen during the login time."""
        status = kwd.get('status', 'error')
        login = kwd.get('login', '')
        password = kwd.get('password', '')
        referer = trans.request.referer or ''
        redirect = kwd.get('redirect', referer).strip()
        success = False
        user = trans.sa_session.query(trans.app.model.User).filter(or_(
            trans.app.model.User.table.c.email == login,
            trans.app.model.User.table.c.username == login
        )).first()
        log.debug("trans.app.config.auth_config_file: %s" % trans.app.config.auth_config_file)
        if not user:
            autoreg = trans.app.auth_manager.check_auto_registration(trans, login, password)
            if autoreg[0]:
                kwd['email'] = autoreg[1]
                kwd['username'] = autoreg[2]
                message = " ".join([validate_email(trans, kwd['email']),
                                    validate_publicname(trans, kwd['username'])]).rstrip()
                if not message:
                    message, status, user, success = self.__register(trans, 'user', False, **kwd)
                    if success:
                        # The handle_user_login() method has a call to the history_set_default_permissions() method
                        # (needed when logging in with a history), user needs to have default permissions set before logging in
                        trans.handle_user_login(user)
                        trans.log_event("User (auto) created a new account")
                        trans.log_event("User logged in")
                    else:
                        message = "Auto-registration failed, contact your local Galaxy administrator. %s" % message
                else:
                    message = "Auto-registration failed, contact your local Galaxy administrator. %s" % message
            else:
                message = "No such user or invalid password"
        elif user.deleted:
            message = "This account has been marked deleted, contact your local Galaxy administrator to restore the account."
            if trans.app.config.error_email_to is not None:
                message += ' Contact: %s' % trans.app.config.error_email_to
        elif user.external:
            message = "This account was created for use with an external authentication method, contact your local Galaxy administrator to activate it."
            if trans.app.config.error_email_to is not None:
                message += ' Contact: %s' % trans.app.config.error_email_to
        elif not trans.app.auth_manager.check_password(user, password):
            message = "Invalid password"
        elif trans.app.config.user_activation_on and not user.active:  # activation is ON and the user is INACTIVE
            if (trans.app.config.activation_grace_period != 0):  # grace period is ON
                if self.is_outside_grace_period(trans, user.create_time):  # User is outside the grace period. Login is disabled and he will have the activation email resent.
                    message, status = self.resend_verification_email(trans, user.email, user.username)
                else:  # User is within the grace period, let him log in.
                    message, success, status = self.proceed_login(trans, user, redirect)
            else:  # Grace period is off. Login is disabled and user will have the activation email resent.
                message, status = self.resend_verification_email(trans, user.email, user.username)
        else:  # activation is OFF
            pw_expires = trans.app.config.password_expiration_period
            if pw_expires and user.last_password_change < datetime.today() - pw_expires:
                # Password is expired, we don't log them in.
                trans.response.send_redirect(web.url_for(controller='user',
                                                         action='change_password',
                                                         message='Your password has expired. Please change it to access Galaxy.',
                                                         redirect_home=True,
                                                         status='error'))
            message, success, status = self.proceed_login(trans, user, redirect)
            if pw_expires and user.last_password_change < datetime.today() - timedelta(days=pw_expires.days / 10):
                # If password is about to expire, modify message to state that.
                expiredate = datetime.today() - user.last_password_change + pw_expires
                message = 'You are now logged in as %s. Your password will expire in %s days.<br>You can <a target="_top" href="%s">go back to the page you were visiting</a> or <a target="_top" href="%s">go to the home page</a>.' % \
                          (expiredate.days, user.email, redirect, url_for('/'))
                status = 'warning'
        return (message, status, user, success)

    def proceed_login(self, trans, user, redirect):
        """
        Function processes user login. It is called in case all the login requirements are valid.
        """
        message = ''
        trans.handle_user_login(user)
        if trans.webapp.name == 'galaxy':
            trans.log_event("User logged in")
            message = 'You are now logged in as %s.<br>You can <a target="_top" href="%s">go back to the page you were visiting</a> or <a target="_top" href="%s">go to the home page</a>.' % \
                (user.email, redirect, url_for('/'))
            if trans.app.config.require_login:
                message += '  <a target="_top" href="%s">Click here</a> to continue to the home page.' % web.url_for(controller="root", action="welcome")
        success = True
        status = 'done'
        return message, success, status

    @web.expose
    def resend_verification(self, trans):
        """
        Exposed function for use outside of the class. E.g. when user click on the resend link in the masthead.
        """
        message, status = self.resend_verification_email(trans, None, None)
        if status == 'done':
            return trans.show_ok_message(message)
        else:
            return trans.show_error_message(message)

    def resend_verification_email(self, trans, email, username):
        """
        Function resends the verification email in case user wants to log in with an inactive account or he clicks the resend link.
        """
        if email is None:  # User is coming from outside registration form, load email from trans
            email = trans.user.email
        if username is None:  # User is coming from outside registration form, load email from trans
            username = trans.user.username
        is_activation_sent = self.send_verification_email(trans, email, username)
        if is_activation_sent:
            message = 'This account has not been activated yet. The activation link has been sent again. Please check your email address <b>%s</b> including the spam/trash folder.<br><a target="_top" href="%s">Return to the home page</a>.' % (escape(email), url_for('/'))
            status = 'error'
        else:
            message = 'This account has not been activated yet but we are unable to send the activation link. Please contact your local Galaxy administrator.<br><a target="_top" href="%s">Return to the home page</a>.' % url_for('/')
            status = 'error'
            if trans.app.config.error_email_to is not None:
                message += '<br>Error contact: %s' % trans.app.config.error_email_to
        return message, status

    def is_outside_grace_period(self, trans, create_time):
        """
        Function checks whether the user is outside the config-defined grace period for inactive accounts.
        """
        #  Activation is forced and the user is not active yet. Check the grace period.
        activation_grace_period = trans.app.config.activation_grace_period
        delta = timedelta(hours=int(activation_grace_period))
        time_difference = datetime.utcnow() - create_time
        return (time_difference > delta or activation_grace_period == 0)

    @web.expose
    def logout(self, trans, logout_all=False, **kwd):
        if trans.webapp.name == 'galaxy':
            csrf_check = trans.check_csrf_token()
            if csrf_check:
                return csrf_check

            if trans.app.config.require_login:
                refresh_frames = ['masthead', 'history', 'tools']
            else:
                refresh_frames = ['masthead', 'history']
            if trans.user:
                # Queue a quota recalculation (async) task -- this takes a
                # while sometimes, so we don't want to block on logout.
                send_local_control_task(trans.app,
                                        'recalculate_user_disk_usage',
                                        {'user_id': trans.security.encode_id(trans.user.id)})
            # Since logging an event requires a session, we'll log prior to ending the session
            trans.log_event("User logged out")
        else:
            refresh_frames = ['masthead']
        trans.handle_user_logout(logout_all=logout_all)
        message = 'You have been logged out.<br>To log in again <a target="_top" href="%s">go to the home page</a>.' % \
            (url_for('/'))
        if biostar.biostar_logged_in(trans):
            biostar_url = biostar.biostar_logout(trans)
            if biostar_url:
                # TODO: It would be better if we automatically logged this user out of biostar
                message += '<br>To logout of Biostar, please click <a href="%s" target="_blank">here</a>.' % (biostar_url)
        if trans.app.config.use_remote_user and trans.app.config.remote_user_logout_href:
            trans.response.send_redirect(trans.app.config.remote_user_logout_href)
        else:
            return trans.fill_template('/user/logout.mako',
                                       refresh_frames=refresh_frames,
                                       message=message,
                                       status='done',
                                       active_view="user")

    @web.expose
    def create(self, trans, cntrller='user', redirect_url='', refresh_frames=[], **kwd):
        params = util.Params(kwd)
        # If the honeypot field is not empty we are dealing with a bot.
        honeypot_field = params.get('bear_field', '')
        if honeypot_field != '':
            return trans.show_error_message("You've been flagged as a possible bot. If you are not, please try registering again and fill the form out carefully. <a target=\"_top\" href=\"%s\">Go to the home page</a>.") % url_for('/')

        message = util.restore_text(params.get('message', ''))
        status = params.get('status', 'done')
        use_panels = util.string_as_bool(kwd.get('use_panels', True))
        email = util.restore_text(params.get('email', ''))
        # Do not sanitize passwords, so take from kwd
        # instead of params ( which were sanitized )
        password = kwd.get('password', '')
        confirm = kwd.get('confirm', '')
        username = util.restore_text(params.get('username', ''))
        subscribe = params.get('subscribe', '')
        subscribe_checked = CheckboxField.is_checked(subscribe)
        referer = trans.request.referer or ''
        redirect = kwd.get('redirect', referer).strip()
        is_admin = cntrller == 'admin' and trans.user_is_admin
        if not trans.app.config.allow_user_creation and not trans.user_is_admin():
            message = 'User registration is disabled.  Please contact your local Galaxy administrator for an account.'
            if trans.app.config.error_email_to is not None:
                message += ' Contact: %s' % trans.app.config.error_email_to
            status = 'error'
        else:
            # check user is allowed to register
            message, status = trans.app.auth_manager.check_registration_allowed(email, username, password)
            if message == '':
                if not refresh_frames:
                    if trans.webapp.name == 'galaxy':
                        if trans.app.config.require_login:
                            refresh_frames = ['masthead', 'history', 'tools']
                        else:
                            refresh_frames = ['masthead', 'history']
                    else:
                        refresh_frames = ['masthead']
                # Create the user, save all the user info and login to Galaxy
                if params.get('create_user_button', False):
                    csrf_check = trans.check_csrf_token()
                    if csrf_check:
                        return csrf_check

                    # Check email and password validity
                    message = self.__validate(trans, params, email, password, confirm, username)
                    if not message:
                        # All the values are valid
                        message, status, user, success = self.__register(trans,
                                                                         cntrller,
                                                                         subscribe_checked,
                                                                         **kwd)
                        if trans.webapp.name == 'tool_shed':
                            redirect_url = url_for('/')
                        if success and not is_admin:
                            # The handle_user_login() method has a call to the history_set_default_permissions() method
                            # (needed when logging in with a history), user needs to have default permissions set before logging in
                            trans.handle_user_login(user)
                            trans.log_event("User created a new account")
                            trans.log_event("User logged in")
                        if success and is_admin:
                            message = 'Created new user account (%s)' % escape(user.email)
                            trans.response.send_redirect(web.url_for(controller='admin',
                                                                     action='users',
                                                                     cntrller=cntrller,
                                                                     message=message,
                                                                     status=status))
                    else:
                        status = 'error'
        if trans.webapp.name == 'galaxy':
            #  Warning message that is shown on the registration page.
            registration_warning_message = trans.app.config.registration_warning_message
        else:
            registration_warning_message = None
        return trans.fill_template('/user/register.mako',
                                   cntrller=cntrller,
                                   email=email,
                                   username=transform_publicname(trans, username),
                                   subscribe_checked=subscribe_checked,
                                   use_panels=use_panels,
                                   redirect=redirect,
                                   redirect_url=redirect_url,
                                   refresh_frames=refresh_frames,
                                   registration_warning_message=registration_warning_message,
                                   message=message,
                                   status=status)

    def __register(self, trans, cntrller, subscribe_checked, **kwd):
        email = util.restore_text(kwd.get('email', ''))
        password = kwd.get('password', '')
        username = util.restore_text(kwd.get('username', ''))
        message = escape(kwd.get('message', ''))
        status = kwd.get('status', 'done')
        is_admin = cntrller == 'admin' and trans.user_is_admin()
        user = self.create_user(trans=trans, email=email, username=username, password=password)
        error = ''
        success = True
        if trans.webapp.name == 'galaxy':
            if subscribe_checked:
                # subscribe user to email list
                if trans.app.config.smtp_server is None:
                    error = "Now logged in as " + user.email + ". However, subscribing to the mailing list has failed because mail is not configured for this Galaxy instance. <br>Please contact your local Galaxy administrator."
                else:
                    body = 'Join Mailing list.\n'
                    to = trans.app.config.mailing_join_addr
                    frm = email
                    subject = 'Join Mailing List'
                    try:
                        util.send_mail(frm, to, subject, body, trans.app.config)
                    except Exception:
                        log.exception('Subscribing to the mailing list has failed.')
                        error = "Now logged in as " + user.email + ". However, subscribing to the mailing list has failed."
            if not error and not is_admin:
                # The handle_user_login() method has a call to the history_set_default_permissions() method
                # (needed when logging in with a history), user needs to have default permissions set before logging in
                trans.handle_user_login(user)
                trans.log_event("User created a new account")
                trans.log_event("User logged in")
            elif not error:
                trans.response.send_redirect(web.url_for(controller='admin',
                                                         action='users',
                                                         message='Created new user account (%s)' % user.email,
                                                         status=status))
        if error:
            message = error
            status = 'error'
            success = False
        else:
            if trans.webapp.name == 'galaxy' and trans.app.config.user_activation_on:
                is_activation_sent = self.send_verification_email(trans, email, username)
                if is_activation_sent:
                    message = 'Now logged in as %s.<br>Verification email has been sent to your email address. Please verify it by clicking the activation link in the email.<br>Please check your spam/trash folder in case you cannot find the message.<br><a target="_top" href="%s">Return to the home page.</a>' % (escape(user.email), url_for('/'))
                    success = True
                else:
                    message = 'Unable to send activation email, please contact your local Galaxy administrator.'
                    if trans.app.config.error_email_to is not None:
                        message += ' Contact: %s' % trans.app.config.error_email_to
                    success = False
            else:  # User activation is OFF, proceed without sending the activation email.
                message = 'Now logged in as %s.<br><a target="_top" href="%s">Return to the home page.</a>' % (escape(user.email), url_for('/'))
                success = True
        return (message, status, user, success)

    def send_verification_email(self, trans, email, username):
        """
        Send the verification email containing the activation link to the user's email.
        """
        if username is None:
            username = trans.user.username
        activation_link = self.prepare_activation_link(trans, escape(email))

        host = trans.request.host.split(':')[0]
        if host in ['localhost', '127.0.0.1', '0.0.0.0']:
            host = socket.getfqdn()
        body = ("Hello %s,\n\n"
                "In order to complete the activation process for %s begun on %s at %s, please click on the following link to verify your account:\n\n"
                "%s \n\n"
                "By clicking on the above link and opening a Galaxy account you are also confirming that you have read and agreed to Galaxy's Terms and Conditions for use of this service (%s). This includes a quota limit of one account per user. Attempts to subvert this limit by creating multiple accounts or through any other method may result in termination of all associated accounts and data.\n\n"
                "Please contact us if you need help with your account at: %s. You can also browse resources available at: %s. \n\n"
                "More about the Galaxy Project can be found at galaxyproject.org\n\n"
                "Your Galaxy Team" % (escape(username), escape(email),
                                      datetime.utcnow().strftime("%D"),
                                      trans.request.host, activation_link,
                                      trans.app.config.terms_url,
                                      trans.app.config.error_email_to,
                                      trans.app.config.instance_resource_url))
        to = email
        frm = trans.app.config.email_from or 'galaxy-no-reply@' + host
        subject = 'Galaxy Account Activation'
        try:
            util.send_mail(frm, to, subject, body, trans.app.config)
            return True
        except Exception:
            log.exception('Unable to send the activation email.')
            return False

    def prepare_activation_link(self, trans, email):
        """
        Prepare the account activation link for the user.
        """
        activation_token = self.get_activation_token(trans, email)
        activation_link = url_for(controller='user', action='activate', activation_token=activation_token, email=email, qualified=True)
        return activation_link

    def get_activation_token(self, trans, email):
        """
        Check for the activation token. Create new activation token and store it in the database if no token found.
        """
        user = trans.sa_session.query(trans.app.model.User).filter(trans.app.model.User.table.c.email == email).first()
        activation_token = user.activation_token
        if activation_token is None:
            activation_token = hash_util.new_secure_hash(str(random.getrandbits(256)))
            user.activation_token = activation_token
            trans.sa_session.add(user)
            trans.sa_session.flush()
        return activation_token

    @web.expose
    def activate(self, trans, **kwd):
        """
        Check whether token fits the user and then activate the user's account.
        """
        params = util.Params(kwd, sanitize=False)
        email = urllib.unquote(params.get('email', None))
        activation_token = params.get('activation_token', None)

        if email is None or activation_token is None:
            #  We don't have the email or activation_token, show error.
            return trans.show_error_message("You are using an invalid activation link. Try to log in and we will send you a new activation email. <br><a href='%s'>Go to login page.</a>") % web.url_for(controller="root", action="index")
        else:
            # Find the user
            user = trans.sa_session.query(trans.app.model.User).filter(trans.app.model.User.table.c.email == email).first()
            # If the user is active already don't try to activate
            if user.active is True:
                return trans.show_ok_message("Your account is already active. Nothing has changed. <br><a href='%s'>Go to login page.</a>") % web.url_for(controller='root', action='index')
            if user.activation_token == activation_token:
                user.activation_token = None
                user.active = True
                trans.sa_session.add(user)
                trans.sa_session.flush()
                return trans.show_ok_message("Your account has been successfully activated! <br><a href='%s'>Go to login page.</a>") % web.url_for(controller='root', action='index')
            else:
                #  Tokens don't match. Activation is denied.
                return trans.show_error_message("You are using an invalid activation link. Try to log in and we will send you a new activation email. <br><a href='%s'>Go to login page.</a>") % web.url_for(controller='root', action='index')
        return

    @web.expose
    def reset_password(self, trans, email=None, **kwd):
        """Reset the user's password. Send an email with token that allows a password change."""
        if trans.app.config.smtp_server is None:
            return trans.show_error_message("Mail is not configured for this Galaxy instance "
                                            "and password reset information cannot be sent. "
                                            "Please contact your local Galaxy administrator.")
        message = None
        status = 'done'
        if kwd.get('reset_password_button', False):
            message = validate_email(trans, email, check_dup=False)
            if not message:
                # Default to a non-userinfo-leaking response message
                message = ("Your reset request for %s has been received.  "
                           "Please check your email account for more instructions.  "
                           "If you do not receive an email shortly, please contact an administrator." % (escape(email)))
                reset_user = trans.sa_session.query(trans.app.model.User).filter(trans.app.model.User.table.c.email == email).first()
                if not reset_user:
                    # Perform a case-insensitive check only if the user wasn't found
                    reset_user = trans.sa_session.query(trans.app.model.User).filter(func.lower(trans.app.model.User.table.c.email) == func.lower(email)).first()
                if reset_user:
                    prt = trans.app.model.PasswordResetToken(reset_user)
                    trans.sa_session.add(prt)
                    trans.sa_session.flush()
                    host = trans.request.host.split(':')[0]
                    if host in ['localhost', '127.0.0.1', '0.0.0.0']:
                        host = socket.getfqdn()
                    reset_url = url_for(controller='user',
                                        action="change_password",
                                        token=prt.token, qualified=True)
                    body = PASSWORD_RESET_TEMPLATE % (host, prt.expiration_time.strftime(trans.app.config.pretty_datetime_format),
                                                      reset_url)
                    frm = trans.app.config.email_from or 'galaxy-no-reply@' + host
                    subject = 'Galaxy Password Reset'
                    try:
                        util.send_mail(frm, email, subject, body, trans.app.config)
                        trans.sa_session.add(reset_user)
                        trans.sa_session.flush()
                        trans.log_event("User reset password: %s" % email)
                    except Exception:
                        log.exception('Unable to reset password.')
        return trans.fill_template('/user/reset_password.mako',
                                   message=message,
                                   status=status)

    def __validate(self, trans, params, email, password, confirm, username):
        # If coming from the tool shed webapp, we'll require a public user name
        if trans.webapp.name == 'tool_shed':
            if not username:
                return "A public user name is required in the tool shed."
            if username in ['repos']:
                return "The term <b>%s</b> is a reserved word in the tool shed, so it cannot be used as a public user name." % escape(username)
        message = "\n".join([validate_email(trans, email),
                             validate_password(trans, password, confirm),
                             validate_publicname(trans, username)]).rstrip()
        return message

    @web.expose
    @web.require_login("to get most recently used tool")
    @web.json_pretty
    def get_most_recently_used_tool_async(self, trans):
        """ Returns information about the most recently used tool. """

        # Get most recently used tool.
        query = trans.sa_session.query(self.app.model.Job.tool_id).join(self.app.model.History) \
                                .filter(self.app.model.History.user == trans.user) \
                                .order_by(self.app.model.Job.create_time.desc()).limit(1)
        tool_id = query[0][0]  # Get first element in first row of query.
        tool = self.get_toolbox().get_tool(tool_id)

        # Return tool info.
        tool_info = {"id": tool.id,
                     "link": url_for(controller='tool_runner', tool_id=tool.id),
                     "target": tool.target,
                     "name": tool.name,  # TODO: translate this using _()
                     "minsizehint": tool.uihints.get('minwidth', -1),
                     "description": tool.description}
        return tool_info

    @web.expose
    def set_user_pref_async(self, trans, pref_name, pref_value):
        """ Set a user preference asynchronously. If user is not logged in, do nothing. """
        if trans.user:
            trans.log_action(trans.get_user(), "set_user_pref", "", {pref_name: pref_value})
            trans.user.preferences[pref_name] = pref_value
            trans.sa_session.flush()

    @web.expose
    def log_user_action_async(self, trans, action, context, params):
        """ Log a user action asynchronously. If user is not logged in, do nothing. """
        if trans.user:
            trans.log_action(trans.get_user(), action, context, params)

    def __get_redirect_url(self, redirect):
        root_url = url_for('/', qualified=True)
        # compare urls, to prevent a redirect from pointing (directly) outside of galaxy
        # or to enter a logout/login loop
        if not util.compare_urls(root_url, redirect, compare_path=False) or util.compare_urls(url_for(controller='user', action='logout', qualified=True), redirect):
            log.warning('Redirect URL is outside of Galaxy, will redirect to Galaxy root instead: %s', redirect)
            redirect = root_url
        elif util.compare_urls(url_for(controller='user', action='logout', qualified=True), redirect):
            redirect = root_url
        return redirect

    @web.expose
    def change_password(self, trans, token=None, **kwd):
        """
        Provides a form with which one can change their password.  If token is
        provided, don't require current password.

        NOTE: This endpoint has been temporarily returned to the user
        controller, and will go away once there is a suitable replacement.
        """
        status = None
        message = kwd.get('message', '')
        user = None
        if kwd.get('change_password_button', False):
            password = kwd.get('password', '')
            confirm = kwd.get('confirm', '')
            current = kwd.get('current', '')
            token_result = None
            if token:
                # If a token was supplied, validate and set user
                token_result = trans.sa_session.query(trans.app.model.PasswordResetToken).get(token)
                if token_result and token_result.expiration_time > datetime.utcnow():
                    user = token_result.user
                else:
                    return trans.show_error_message("Invalid or expired password reset token, please request a new one.")
            else:
                # The user is changing their own password, validate their current password
                (ok, message) = trans.app.auth_manager.check_change_password(trans.user, current)
                if ok:
                    user = trans.user
                else:
                    status = 'error'
            if user:
                # Validate the new password
                message = validate_password(trans, password, confirm)
                if message:
                    status = 'error'
                else:
                    # Save new password
                    user.set_password_cleartext(password)
                    # if we used a token, invalidate it and log the user in.
                    if token_result:
                        trans.handle_user_login(token_result.user)
                        token_result.expiration_time = datetime.utcnow()
                        trans.sa_session.add(token_result)
                    # Invalidate all other sessions
                    for other_galaxy_session in trans.sa_session.query(trans.app.model.GalaxySession) \
                                                     .filter(and_(trans.app.model.GalaxySession.table.c.user_id == user.id,
                                                                  trans.app.model.GalaxySession.table.c.is_valid == true(),
                                                                  trans.app.model.GalaxySession.table.c.id != trans.galaxy_session.id)):
                        other_galaxy_session.is_valid = False
                        trans.sa_session.add(other_galaxy_session)
                    trans.sa_session.add(user)
                    trans.sa_session.flush()
                    trans.log_event("User change password")
                    if kwd.get('display_top', False) == 'True':
                        return trans.response.send_redirect(url_for('/', message='Password has been changed'))
                    else:
                        return trans.show_ok_message('The password has been changed and any other existing Galaxy sessions have been logged out (but jobs in histories in those sessions will not be interrupted).')
        # Yes, this intentionally uses the template moved to tool_shed for right now, until it is removed.
        return trans.fill_template('/webapps/tool_shed/user/change_password.mako',
                                   token=token,
                                   status=status,
                                   message=message,
                                   display_top=kwd.get('redirect_home', False))

    @web.expose
    @web.require_admin
    def edit_info(self, trans, cntrller, **kwd):
        """
        TEMPORARY ENDPOINT - added back to support admin-level user info
        editing prior to adminjs.  This is code that was prematurely removed
        from the user controller when the user-side editing functionality was
        replaced.

        The method manage_user_info, which follows this, should also be removed
        at that time.

        Edit user information = username, email or password.
        """
        params = util.Params(kwd)
        is_admin = cntrller == 'admin' and trans.user_is_admin()
        message = util.restore_text(params.get('message', ''))
        status = params.get('status', 'done')
        user_id = params.get('user_id', None)
        if user_id and is_admin:
            user = trans.sa_session.query(trans.app.model.User).get(trans.security.decode_id(user_id))
        elif user_id and (not trans.user or trans.user.id != trans.security.decode_id(user_id)):
            message = 'Invalid user id'
            status = 'error'
            user = None
        else:
            user = trans.user
        if user and params.get('login_info_button', False):
            # Editing email and username
            email = util.restore_text(params.get('email', ''))
            username = util.restore_text(params.get('username', '')).lower()

            # Validate the new values for email and username
            message = validate_email(trans, email, user)
            if not message and username:
                message = validate_publicname(trans, username, user)
            if message:
                status = 'error'
            else:
                if (user.email != email):
                    # The user's private role name must match the user's login ( email )
                    private_role = trans.app.security_agent.get_private_user_role(user)
                    private_role.name = email
                    private_role.description = 'Private role for ' + email
                    # Change the email itself
                    user.email = email
                    trans.sa_session.add_all((user, private_role))
                    trans.sa_session.flush()
                    if trans.webapp.name == 'galaxy' and trans.app.config.user_activation_on:
                        user.active = False
                        trans.sa_session.add(user)
                        trans.sa_session.flush()
                        is_activation_sent = self.send_verification_email(trans, user.email, user.username)
                        if is_activation_sent:
                            message = 'The login information has been updated with the changes.<br>Verification email has been sent to your new email address. Please verify it by clicking the activation link in the email.<br>Please check your spam/trash folder in case you cannot find the message.'
                        else:
                            message = 'Unable to send activation email, please contact your local Galaxy administrator.'
                            if trans.app.config.error_email_to is not None:
                                message += ' Contact: %s' % trans.app.config.error_email_to
                if (user.username != username):
                    user.username = username
                    trans.sa_session.add(user)
                    trans.sa_session.flush()
                message = 'The login information has been updated with the changes.'
        elif user and params.get('edit_user_info_button', False):
            # Edit user information - webapp MUST BE 'galaxy'
            user_type_fd_id = params.get('user_type_fd_id', 'none')
            if user_type_fd_id not in ['none']:
                user_type_form_definition = trans.sa_session.query(trans.app.model.FormDefinition).get(trans.security.decode_id(user_type_fd_id))
            elif user.values:
                user_type_form_definition = user.values.form_definition
            else:
                # User was created before any of the user_info forms were created
                user_type_form_definition = None
            if user_type_form_definition:
                values = self.get_form_values(trans, user, user_type_form_definition, **kwd)
            else:
                values = {}
            flush_needed = False
            if user.values:
                # Editing the user info of an existing user with existing user info
                user.values.content = values
                trans.sa_session.add(user.values)
                flush_needed = True
            elif values:
                form_values = trans.model.FormValues(user_type_form_definition, values)
                trans.sa_session.add(form_values)
                user.values = form_values
                flush_needed = True
            if flush_needed:
                trans.sa_session.add(user)
                trans.sa_session.flush()
            message = "The user information has been updated with the changes."
        if user and trans.webapp.name == 'galaxy' and is_admin:
            kwd['user_id'] = trans.security.encode_id(user.id)
        kwd['id'] = user_id
        if message:
            kwd['message'] = util.sanitize_text(message)
        if status:
            kwd['status'] = status
        return trans.response.send_redirect(web.url_for(controller='user',
                                                        action='manage_user_info',
                                                        cntrller=cntrller,
                                                        **kwd))
