"""
Migration script to add the run and sample_run_association tables.
"""
from __future__ import print_function

import datetime
import logging

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, MetaData, Table

now = datetime.datetime.utcnow
log = logging.getLogger(__name__)
metadata = MetaData()

Run_table = Table("run", metadata,
                  Column("id", Integer, primary_key=True),
                  Column("create_time", DateTime, default=now),
                  Column("update_time", DateTime, default=now, onupdate=now),
                  Column("form_definition_id", Integer, ForeignKey("form_definition.id"), index=True),
                  Column("form_values_id", Integer, ForeignKey("form_values.id"), index=True),
                  Column("deleted", Boolean, index=True, default=False))

RequestTypeRunAssociation_table = Table("request_type_run_association", metadata,
                                        Column("id", Integer, primary_key=True),
                                        Column("request_type_id", Integer, ForeignKey("request_type.id"), index=True, nullable=False),
                                        Column("run_id", Integer, ForeignKey("run.id"), index=True, nullable=False))

SampleRunAssociation_table = Table("sample_run_association", metadata,
                                   Column("id", Integer, primary_key=True),
                                   Column("sample_id", Integer, ForeignKey("sample.id"), index=True, nullable=False),
                                   Column("run_id", Integer, ForeignKey("run.id"), index=True, nullable=False))


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    try:
        Run_table.create()
    except Exception:
        log.exception("Creating Run_table table failed.")
    try:
        RequestTypeRunAssociation_table.create()
    except Exception:
        log.exception("Creating RequestTypeRunAssociation table failed.")
    try:
        SampleRunAssociation_table.create()
    except Exception:
        log.exception("Creating SampleRunAssociation table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    # Load existing tables
    metadata.reflect()
    try:
        SampleRunAssociation_table.drop()
    except Exception:
        log.exception("Dropping SampleRunAssociation table failed.")
    try:
        RequestTypeRunAssociation_table.drop()
    except Exception:
        log.exception("Dropping RequestTypeRunAssociation table failed.")
    try:
        Run_table.drop()
    except Exception:
        log.exception("Dropping Run_table table failed.")
