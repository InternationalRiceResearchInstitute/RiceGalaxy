"""
Migration script to create tables for tracking workflow invocations.
"""
from __future__ import print_function

import datetime
import logging

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, Table

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)
now = datetime.datetime.utcnow
metadata = MetaData()

WorkflowInvocation_table = Table("workflow_invocation", metadata,
                                 Column("id", Integer, primary_key=True),
                                 Column("create_time", DateTime, default=now),
                                 Column("update_time", DateTime, default=now, onupdate=now),
                                 Column("workflow_id", Integer, ForeignKey("workflow.id"), index=True, nullable=False))

WorkflowInvocationStep_table = Table("workflow_invocation_step", metadata,
                                     Column("id", Integer, primary_key=True),
                                     Column("create_time", DateTime, default=now),
                                     Column("update_time", DateTime, default=now, onupdate=now),
                                     Column("workflow_invocation_id", Integer, ForeignKey("workflow_invocation.id"), index=True, nullable=False),
                                     Column("workflow_step_id", Integer, ForeignKey("workflow_step.id"), index=True, nullable=False),
                                     Column("job_id", Integer, ForeignKey("job.id"), index=True, nullable=False))

tables = [WorkflowInvocation_table, WorkflowInvocationStep_table]


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()

    for table in tables:
        try:
            table.create()
        except:
            log.warning("Failed to create table '%s', ignoring (might result in wrong schema)" % table.name)


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()

    for table in reversed(tables):
        table.drop()
