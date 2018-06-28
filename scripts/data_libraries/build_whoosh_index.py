#!/usr/bin/env python
"""
Build index for full-text whoosh search of files in data libraries.

Requires configuration settings in galaxy.ini. See the whoosh settings in the
data library search section for more details.

Run from the ~/scripts/data_libraries directory:
%sh build_whoosh_index.sh
"""
from __future__ import print_function

import os
import sys

from six import text_type
from six.moves import configparser

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'lib')))

# Whoosh is compatible with Python 2.5+ Try to import Whoosh and set flag to indicate whether search is enabled.
try:
    from whoosh.filedb.filestore import FileStorage
    from whoosh.fields import Schema, STORED, TEXT
    whoosh_search_enabled = True
    schema = Schema(id=STORED, name=TEXT, info=TEXT, dbkey=TEXT, message=TEXT)
    import galaxy.model.mapping
    from galaxy import config, model
except ImportError:
    whoosh_search_enabled = False
    schema = None


def build_index(sa_session, whoosh_index_dir):
    storage = FileStorage(whoosh_index_dir)
    index = storage.create_index(schema)
    writer = index.writer()

    def to_unicode(a_basestr):
        if not isinstance(a_basestr, text_type):
            return text_type(a_basestr, 'utf-8')
        else:
            return a_basestr
    lddas_indexed = 0
    for id, name, info, dbkey, message in get_lddas(sa_session):
        writer.add_document(id=id,
                            name=to_unicode(name),
                            info=to_unicode(info),
                            dbkey=to_unicode(dbkey),
                            message=to_unicode(message))
        lddas_indexed += 1
    writer.commit()
    print("Number of active library datasets indexed: ", lddas_indexed)


def get_lddas(sa_session):
    for ldda in sa_session.query(model.LibraryDatasetDatasetAssociation).filter_by(deleted=False):
        id = ldda.id
        name = ldda.name
        info = ldda.library_dataset.get_info()
        if info and not info.startswith('upload'):
            info = info.replace('no info', '')
        else:
            info = ''
        dbkey = ldda.metadata.dbkey
        if ldda.message:
            message = ldda.message
        else:
            message = ''
        yield id, name, info, dbkey, message


def get_sa_session_and_needed_config_settings(ini_file):
    conf_parser = configparser.ConfigParser({'here': os.getcwd()})
    conf_parser.read(ini_file)
    kwds = dict()
    for key, value in conf_parser.items("app:main"):
        kwds[key] = value
    config_settings = config.Configuration(**kwds)
    db_con = config_settings.database_connection
    if not db_con:
        db_con = "sqlite:///%s?isolation_level=IMMEDIATE" % config_settings.database
    model = galaxy.model.mapping.init(config_settings.file_path, db_con, engine_options={}, create_tables=False)
    return model.context.current, config_settings


if __name__ == "__main__":
    if whoosh_search_enabled:
        ini_file = sys.argv[1]
        sa_session, config_settings = get_sa_session_and_needed_config_settings(ini_file)
        whoosh_index_dir = config_settings.whoosh_index_dir
        build_index(sa_session, whoosh_index_dir)
