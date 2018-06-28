"""
This module manages loading of Galaxy webhooks.
"""
import logging
import os

import yaml

from galaxy.util import config_directories_from_setting

log = logging.getLogger(__name__)


class Webhook(object):
    def __init__(self, w_name, w_type, w_activate, w_path):
        self.name = w_name
        self.type = w_type
        self.activate = w_activate
        self.path = w_path
        self.styles = ''
        self.script = ''
        self.helper = ''
        self.config = {}

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.type,
            'activate': self.activate,
            'styles': self.styles,
            'script': self.script,
            'config': self.config
        }


class WebhooksRegistry(object):
    def __init__(self, webhooks_dirs):
        self.webhooks = []
        self.webhooks_directories = []

        for webhook_dir in config_directories_from_setting(webhooks_dirs):
            for plugin_dir in os.listdir(webhook_dir):
                path = os.path.join(webhook_dir, plugin_dir)
                if os.path.isdir(path):
                    self.webhooks_directories.append(path)

        self.load_webhooks()

    def load_webhooks(self):
        for directory in self.webhooks_directories:
            config_dir = os.path.join(directory, 'config')

            if not os.path.exists(config_dir):
                log.warning('directory not found: %s', config_dir)
                continue

            config_dir_contents = os.listdir(config_dir)
            # We are assuming that all yml/yaml files in a webhooks'
            # config directory are webhook config files.
            for config_file in config_dir_contents:
                if config_file.endswith('.yml') or config_file.endswith('.yaml'):
                    self.load_webhook_from_config(config_dir, config_file)

    def load_webhook_from_config(self, config_dir, config_file):
        try:
            with open(os.path.join(config_dir, config_file)) as file:
                config = yaml.safe_load(file)
                path = os.path.normpath(os.path.join(config_dir, '..'))
                webhook = Webhook(
                    config['name'],
                    config['type'],
                    config['activate'],
                    path,
                )

                # Read styles into a string, assuming all styles are in a
                # single file
                try:
                    styles_file = os.path.join(path, 'static/styles.css')
                    with open(styles_file, 'r') as file:
                        webhook.styles = file.read().replace('\n', '')
                except IOError:
                    pass

                # Read script into a string, assuming everything is in a
                # single file
                try:
                    script_file = os.path.join(path, 'static/script.js')
                    with open(script_file, 'r') as file:
                        webhook.script = file.read()
                except IOError:
                    pass

                # Save helper function path if it exists
                helper_path = os.path.join(path, 'helper/__init__.py')
                if os.path.isfile(helper_path):
                    webhook.helper = helper_path

                webhook.config = config
                self.webhooks.append(webhook)

        except Exception as e:
            log.exception(e)
