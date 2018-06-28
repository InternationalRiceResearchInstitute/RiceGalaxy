"""
This script creates a request.folder_id column which is a foreign
key to the library_folder table. This also adds a 'type' and 'layout' column
to the form_definition table.
"""
from __future__ import print_function

import logging
import sys

from migrate import ForeignKeyConstraint
from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.exc import NoSuchTableError

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import JSONType, TrimmedString

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter(format)
handler.setFormatter(formatter)
log.addHandler(handler)
metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    # Load existing tables
    metadata.reflect()
    # Create the folder_id column
    try:
        Request_table = Table("request", metadata, autoload=True)
    except NoSuchTableError:
        Request_table = None
        log.debug("Failed loading table request")
    if Request_table is not None:
        try:
            col = Column("folder_id", Integer, index=True)
            col.create(Request_table, index_name='ix_request_folder_id')
            assert col is Request_table.c.folder_id
        except Exception:
            log.exception("Adding column 'folder_id' to request table failed.")
        try:
            LibraryFolder_table = Table("library_folder", metadata, autoload=True)
        except NoSuchTableError:
            LibraryFolder_table = None
            log.debug("Failed loading table library_folder")
        # Add 1 foreign key constraint to the library_folder table
        if migrate_engine.name != 'sqlite' and Request_table is not None and LibraryFolder_table is not None:
            try:
                cons = ForeignKeyConstraint([Request_table.c.folder_id],
                                            [LibraryFolder_table.c.id],
                                            name='request_folder_id_fk')
                # Create the constraint
                cons.create()
            except Exception:
                log.exception("Adding foreign key constraint 'request_folder_id_fk' to table 'library_folder' failed.")
    # Create the type column in form_definition
    try:
        FormDefinition_table = Table("form_definition", metadata, autoload=True)
    except NoSuchTableError:
        FormDefinition_table = None
        log.debug("Failed loading table form_definition")
    if FormDefinition_table is not None:
        try:
            col = Column("type", TrimmedString(255), index=True)
            col.create(FormDefinition_table, index_name='ix_form_definition_type')
            assert col is FormDefinition_table.c.type
        except Exception:
            log.exception("Adding column 'type' to form_definition table failed.")
        try:
            col = Column("layout", JSONType())
            col.create(FormDefinition_table)
            assert col is FormDefinition_table.c.layout
        except Exception:
            log.exception("Adding column 'layout' to form_definition table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    pass
