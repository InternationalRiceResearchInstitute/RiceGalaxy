"""
Migration script to add 'workflow' and 'history' columns for a sample.
"""
from __future__ import print_function

import logging

from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table

from galaxy.model.custom_types import JSONType

log = logging.getLogger(__name__)
metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    try:
        Sample_table = Table("sample", metadata, autoload=True)
        c1 = Column("workflow", JSONType, nullable=True)
        c2 = Column("history_id", Integer, ForeignKey("history.id"), nullable=True)
        c1.create(Sample_table)
        c2.create(Sample_table)
        assert c1 is Sample_table.c.workflow
        assert c2 is Sample_table.c.history_id
    except Exception:
        log.exception("Adding history and workflow columns to sample table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        Sample_table = Table("sample", metadata, autoload=True)
        Sample_table.c.workflow.drop()
    except Exception:
        log.exception("Dropping workflow column from sample table failed.")
    try:
        Sample_table = Table("sample", metadata, autoload=True)
        Sample_table.c.history_id.drop()
    except Exception:
        log.exception("Dropping history column from sample table failed.")
