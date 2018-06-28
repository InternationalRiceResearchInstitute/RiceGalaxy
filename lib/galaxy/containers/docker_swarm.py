"""
Docker Swarm mode interface
"""
from __future__ import absolute_import

import logging

from galaxy.containers import docker_swarm_manager
from galaxy.containers.docker import DockerCLIInterface, DockerInterface
from galaxy.containers.docker_decorators import docker_columns, docker_json
from galaxy.containers.docker_model import (
    CPUS_CONSTRAINT,
    DockerNode,
    DockerService,
    DockerTask,
    IMAGE_CONSTRAINT,
)
from galaxy.exceptions import ContainerRunError


log = logging.getLogger(__name__)


class DockerSwarmInterface(DockerInterface):

    container_class = DockerService
    conf_defaults = {
        'ignore_volumes': False,
        'node_prefix': None,
        'service_create_image_constraint': False,
        'service_create_cpus_constraint': False,
        'resolve_image_digest': False,
        'managed': True,
        'manager_autostart': True,
    }
    publish_port_list_required = True
    supports_volumes = False

    def validate_config(self):
        super(DockerSwarmInterface, self).validate_config()
        self._node_prefix = self._conf.node_prefix

    def run_in_container(self, command, image=None, **kwopts):
        """Run a service like a detached container
        """
        kwopts['replicas'] = '1'
        kwopts['restart_condition'] = 'none'
        if kwopts.get('publish_all_ports', False):
            # not supported for services
            # TODO: inspect image (or query registry if possible) for port list
            if kwopts.get('publish_port_random', False) or kwopts.get('ports', False):
                # assume this covers for publish_all_ports
                del kwopts['publish_all_ports']
            else:
                raise ContainerRunError(
                    "Publishing all ports is not supported in Docker swarm"
                    " mode, use `publish_port_random` or `ports`",
                    image=image,
                    command=command
                )
        if not kwopts.get('detach', True):
            raise ContainerRunError(
                "Running attached containers is not supported in Docker swarm mode",
                image=image,
                command=command
            )
        elif kwopts.get('detach', None):
            del kwopts['detach']
        if kwopts.get('volumes', None):
            if self._conf.ignore_volumes:
                log.warning(
                    "'volumes' kwopt is set and not supported in Docker swarm "
                    "mode, volumes will not be passed (set 'ignore_volumes: "
                    "False' in containers config to fail instead): %s" % kwopts['volumes']
                )
                del kwopts['volumes']
            else:
                raise ContainerRunError(
                    "'volumes' kwopt is set and not supported in Docker swarm "
                    "mode (set 'ignore_volumes: True' in containers config to "
                    "warn instead): %s" % kwopts['volumes'],
                    image=image,
                    command=command
                )
        service = self.service_create(command, image=image, **kwopts)
        self._run_swarm_manager()
        return service

    #
    # helpers
    #

    def _run_swarm_manager(self):
        if self._conf.managed and self._conf.manager_autostart:
            docker_swarm_manager.main(argv=['--containers-config-file', self.containers_config_file, '--swarm', self.key], fork=True)

    def _get_image(self, image):
        """Get the image string, either from the argument, or from the
        configured interface default if ``image`` is ``None``. Optionally
        resolve the image to its digest if ``resolve_image_digest`` is set in
        the interface configuration.

        If the image has not been pulled, the repo digest cannot be determined
        and the image name will be returned.

        :type   image:  str or None
        :param  image:  image id or name

        :returns:       image name or image repo digest
        """
        if not image:
            image = self._conf.image
        assert image is not None, "No image supplied as parameter and no image set as default in config, cannot create service"
        if self._conf.resolve_image_digest:
            image = self.image_repodigest(image)
        return image

    def _objects_by_attribute(self, generator, attribute_name):
        rval = {}
        for obj in generator:
            attr = getattr(obj, attribute_name)
            if attr not in rval:
                rval[attr] = []
            rval[attr].append(obj)
        return rval

    #
    # docker object generators
    #

    def services(self, id=None, name=None):
        for service_dict in self.service_ls(id=id, name=name):
            service_id = service_dict['ID']
            service_name = service_dict['NAME']
            if not service_name.startswith(self._name_prefix):
                continue
            task_list = self.service_ps(service_id)
            yield DockerService.from_cli(self, service_dict, task_list)

    def service(self, id=None, name=None):
        try:
            return self.services(id=id, name=name).next()
        except StopIteration:
            return None

    def services_in_state(self, desired, current):
        for service in self.services():
            if service.in_state(desired, current):
                yield service

    def service_tasks(self, service):
        for task_dict in self.service_ps(service.id):
            if task_dict['NAME'].strip().startswith('\_'):
                continue    # historical task
            yield DockerTask.from_cli(self, task_dict, service=service)

    def nodes(self, id=None, name=None):
        for node_dict in self.node_ls(id=id, name=name):
            node_id = node_dict['ID'].strip(' *')
            node_name = node_dict['HOSTNAME']
            if self._node_prefix and not node_name.startswith(self._node_prefix):
                continue
            task_list = filter(lambda x: x['NAME'].startswith(self._name_prefix), self.node_ps(node_id))
            yield DockerNode.from_cli(self, node_dict, task_list)

    def node(self, name):
        try:
            return self.nodes(id=id, name=name).next()
        except StopIteration:
            return None

    def nodes_in_state(self, status, availability):
        for node in self.nodes():
            if node.in_state(status, availability):
                yield node

    #
    # higher level queries
    #

    def services_waiting(self):
        return self.services_in_state('Running', 'Pending')

    def services_waiting_by_constraints(self):
        return self._objects_by_attribute(self.services_waiting(), 'constraints')

    def services_completed(self):
        return self.services_in_state('Shutdown', 'Complete')

    def nodes_active(self):
        return self.nodes_in_state('Ready', 'Active')

    def nodes_active_by_constraints(self):
        return self._objects_by_attribute(self.nodes_active(), 'labels_as_constraints')

    #
    # operations
    #

    def services_clean(self):
        cleaned_services = []
        services = [x for x in self.services_completed()]  # returns a generator, should probably fix this
        if services:
            cleaned_service_ids = self.service_rm([x.id for x in services]).splitlines()
            cleaned_services = filter(lambda x: x.id in cleaned_service_ids, services)
        return cleaned_services


class DockerSwarmCLIInterface(DockerSwarmInterface, DockerCLIInterface):

    container_type = 'docker_swarm_cli'
    option_map = {
        # `service create` options
        'constraint': {'flag': '--constraint', 'type': 'list_of_kovtrips'},
        'replicas': {'flag': '--replicas', 'type': 'string'},
        'restart_condition': {'flag': '--restart-condition', 'type': 'string'},
        'environment': {'flag': '--env', 'type': 'list_of_kvpairs'},
        'name': {'flag': '--name', 'type': 'string'},
        'publish_port_random': {'flag': '--publish', 'type': 'string'},
        'cpu_limit': {'flag': '--limit-cpu', 'type': 'string'},
        'mem_limit': {'flag': '--limit-memory', 'type': 'string'},
        'cpu_reservation': {'flag': '--reserve-cpu', 'type': 'string'},
        'mem_reservation': {'flag': '--reserve-memory', 'type': 'string'},
        # `service update` options
        'label_add': {'flag': '--label-add', 'type': 'list_of_kvpairs'},
        'label_rm': {'flag': '--label-rm', 'type': 'list_of_kvpairs'},
        'availability': {'flag': '--availability', 'type': 'string'},
    }

    def _filter_by_id_or_name(self, id, name):
        if id:
            return '--filter id={}'.format(id)
        elif name:
            return '--filter name={}'.format(name)
        return None

    #
    # docker subcommands
    #

    def service_create(self, command, image=None, **kwopts):
        if ('service_create_image_constraint' in self._conf or 'service_create_cpus_constraint' in self._conf) and 'constraint' not in kwopts:
            kwopts['constraint'] = []
        image = self._get_image(image)
        if self._conf.service_create_image_constraint:
            kwopts['constraint'].append((IMAGE_CONSTRAINT, '==', image))
        if self._conf.service_create_cpus_constraint:
            cpus = kwopts.get('reserve_cpus', kwopts.get('limit_cpus', '1'))
            kwopts['constraint'].append((CPUS_CONSTRAINT, '==', cpus))
        if self._conf.cpus:
            kwopts['cpu_limit'] = self._conf.cpus
            kwopts['cpu_reservation'] = self._conf.cpus
        if self._conf.memory:
            kwopts['mem_limit'] = self._conf.memory
            kwopts['mem_reservation'] = self._conf.memory
        self.set_kwopts_name(kwopts)
        args = '{kwopts} {image} {command}'.format(
            kwopts=self._stringify_kwopts(kwopts),
            image=image if image else '',
            command=command if command else '',
        ).strip()
        service_id = self._run_docker(subcommand='service create', args=args, verbose=True)
        return DockerService.from_id(self, service_id)

    @docker_json
    def service_inspect(self, service_id):
        return self._run_docker(subcommand='service inspect', args=service_id)

    @docker_columns
    def service_ls(self, id=None, name=None):
        return self._run_docker(subcommand='service ls', args=self._filter_by_id_or_name(id, name))

    @docker_columns
    def service_ps(self, service_id):
        return self._run_docker(subcommand='service ps', args='--no-trunc {}'.format(service_id))

    def service_rm(self, service_ids):
        service_ids = ' '.join(service_ids)
        return self._run_docker(subcommand='service rm', args=service_ids)

    @docker_json
    def node_inspect(self, node_id):
        return self._run_docker(subcommand='node inspect', args=node_id)

    @docker_columns
    def node_ls(self, id=None, name=None):
        return self._run_docker(subcommand='node ls', args=self._filter_by_id_or_name(id, name))

    @docker_columns
    def node_ps(self, node_id):
        return self._run_docker(subcommand='node ps', args='--no-trunc {}'.format(node_id))

    def node_update(self, node_id, **kwopts):
        return self._run_docker(subcommand='node update', args='{kwopts} {node_id}'.format(
            kwopts=self._stringify_kwopts(kwopts),
            node_id=node_id
        ))

    @docker_json
    def task_inspect(self, task_id):
        return self._run_docker(subcommand="inspect", args=task_id)


class DockerSwarmAPIInterface(DockerSwarmCLIInterface):

    container_type = 'docker_swarm'
