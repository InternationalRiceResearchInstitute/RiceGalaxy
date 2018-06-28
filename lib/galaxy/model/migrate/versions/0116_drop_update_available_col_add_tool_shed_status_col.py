"""
Migration script to drop the update_available Boolean column and replace it with the tool_shed_status JSONType column in the tool_shed_repository table.
"""
from __future__ import print_function

import logging
import sys

from sqlalchemy import Boolean, Column, MetaData, Table
from sqlalchemy.exc import NoSuchTableError

from galaxy.model.custom_types import JSONType

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter(format)
handler.setFormatter(formatter)
log.addHandler(handler)

metadata = MetaData()


def engine_false(migrate_engine):
    if migrate_engine.name in ['postgres', 'postgresql']:
        return "FALSE"
    elif migrate_engine.name in ['mysql', 'sqlite']:
        return 0
    else:
        raise Exception('Unknown database type: %s' % migrate_engine.name)


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    try:
        ToolShedRepository_table = Table("tool_shed_repository", metadata, autoload=True)
    except NoSuchTableError:
        ToolShedRepository_table = None
        log.debug("Failed loading table tool_shed_repository")
    if ToolShedRepository_table is not None:
        # For some unknown reason it is no longer possible to drop a column in a migration script if using the sqlite database.
        if migrate_engine.name != 'sqlite':
            try:
                col = ToolShedRepository_table.c.update_available
                col.drop()
            except Exception:
                log.exception("Dropping column update_available from the tool_shed_repository table failed.")
        c = Column("tool_shed_status", JSONType, nullable=True)
        try:
            c.create(ToolShedRepository_table)
            assert c is ToolShedRepository_table.c.tool_shed_status
        except Exception:
            log.exception("Adding tool_shed_status column to the tool_shed_repository table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        ToolShedRepository_table = Table("tool_shed_repository", metadata, autoload=True)
    except NoSuchTableError:
        ToolShedRepository_table = None
        log.debug("Failed loading table tool_shed_repository")
    if ToolShedRepository_table is not None:
        # For some unknown reason it is no longer possible to drop a column in a migration script if using the sqlite database.
        if migrate_engine.name != 'sqlite':
            try:
                col = ToolShedRepository_table.c.tool_shed_status
                col.drop()
            except Exception:
                log.exception("Dropping column tool_shed_status from the tool_shed_repository table failed.")
            c = Column("update_available", Boolean, default=False)
            try:
                c.create(ToolShedRepository_table)
                assert c is ToolShedRepository_table.c.update_available
                migrate_engine.execute("UPDATE tool_shed_repository SET update_available=%s" % engine_false(migrate_engine))
            except Exception:
                log.exception("Adding column update_available to the tool_shed_repository table failed.")
