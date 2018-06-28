"""
This migration script creates the new history_user_share_association table, and adds
a new boolean type column to the history table.  This provides support for sharing
histories in the same way that workflows are shared.
"""
from __future__ import print_function

import logging
import sys

from sqlalchemy import Boolean, Column, ForeignKey, Integer, MetaData, Table
from sqlalchemy.exc import NoSuchTableError

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter(format)
handler.setFormatter(formatter)
log.addHandler(handler)

metadata = MetaData()

HistoryUserShareAssociation_table = Table("history_user_share_association", metadata,
                                          Column("id", Integer, primary_key=True),
                                          Column("history_id", Integer, ForeignKey("history.id"), index=True),
                                          Column("user_id", Integer, ForeignKey("galaxy_user.id"), index=True))


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    # Load existing tables
    metadata.reflect()
    # Create the history_user_share_association table
    try:
        HistoryUserShareAssociation_table.create()
    except Exception:
        log.exception("Creating history_user_share_association table failed.")
    # Add 1 column to the history table
    try:
        History_table = Table("history", metadata, autoload=True)
    except NoSuchTableError:
        History_table = None
        log.debug("Failed loading table history")
    if History_table is not None:
        try:
            col = Column('importable', Boolean, index=True, default=False)
            col.create(History_table, index_name='ix_history_importable')
            assert col is History_table.c.importable
        except Exception:
            log.exception("Adding column 'importable' to history table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    # Load existing tables
    metadata.reflect()
    # Drop 1 column from the history table
    try:
        History_table = Table("history", metadata, autoload=True)
    except NoSuchTableError:
        History_table = None
        log.debug("Failed loading table history")
    if History_table is not None:
        try:
            col = History_table.c.importable
            col.drop()
        except Exception:
            log.exception("Dropping column 'importable' from history table failed.")
    # Drop the history_user_share_association table
    try:
        HistoryUserShareAssociation_table.drop()
    except Exception:
        log.exception("Dropping history_user_share_association table failed.")
