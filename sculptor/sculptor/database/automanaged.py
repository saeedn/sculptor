"""
Map pydantic database models onto SQLAlchemy tables.
(Refer to the docstring in core.py for more details.)

To use this:
    - Create a pydantic model that inherits from DatabaseModel.
    - Call create_tables() with the model class.

`create_tables()` infers column definitions from the pydantic model and
registers a single mutable table (keyed by ``object_id``) with SQLAlchemy.
The actual _creation_ of the tables happens later, when the database is
initialized (via `initialize_db()` in core.py).

In case the type of a field in your pydantic model is not supported out of the box, add a new entry in _PYDANTIC_TO_SQLALCHEMY_TYPES.
"""

import inspect
from abc import ABC
from datetime import datetime
from typing import get_type_hints

from pydantic import AnyUrl
from pydantic import ConfigDict
from pydantic import Field
from pydantic import HttpUrl
from sqlalchemy import Column
from sqlalchemy import Constraint
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Table

from sculptor.database.core import METADATA
from sculptor.foundation.pydantic_serialization import SerializableModel
from sculptor.foundation.time_utils import get_current_time
from sculptor.primitives.ids import ObjectID
from sculptor.utils.type_utils import extract_leaf_types

OBJECT_ID = "object_id"
CREATED_AT = "created_at"

# List of automanaged model classes (those registered via create_tables()).
# (Gets populated by the create_tables() function, alongside METADATA.)
AUTOMANAGED_MODEL_CLASSES: set[type["DatabaseModel"]] = set()


SQLAlchemyTypes = type[String] | type[JSON] | type[Integer] | type[Float] | DateTime

# pyrefly: ignore [bad-assignment]
_PYDANTIC_TO_SQLALCHEMY_TYPES: dict[type, SQLAlchemyTypes] = {
    ObjectID: String,
    SerializableModel: JSON,
    HttpUrl: String,
    AnyUrl: String,
    int: Integer,
    float: Float,
    datetime: DateTime(timezone=True),
    str: String,
    # Add more type mappings as needed.
}


class DatabaseModel(SerializableModel, ABC):
    """Base class for database models."""

    model_config = ConfigDict(
        frozen=True,
        # We allow "arbitrary" types in order to support ObjectID.
        # In practice, the types are checked by the SQLAlchemy type mapping, anyway.
        arbitrary_types_allowed=True,
    )

    created_at: datetime = Field(default_factory=get_current_time)

    def __init_subclass__(cls) -> None:
        """
        Ensure that the subclass defines an 'object_id' attribute of type ObjectID.

        """
        super().__init_subclass__()
        hints = get_type_hints(cls)
        obj_id_type = hints.get("object_id")
        if obj_id_type is None:
            raise InvalidDatabaseModelDefinitionError(f"{cls.__name__} must define the 'object_id' attribute.")
        if not inspect.isclass(obj_id_type) or not issubclass(obj_id_type, ObjectID):
            raise InvalidDatabaseModelDefinitionError(f"'object_id' in {cls.__name__} must be a subclass of ObjectID.")

    def is_content_equal(self, other: "DatabaseModel") -> bool:
        all_fields = vars(self)
        # this is a list of fields in case you want to exclude some other fields in the future.
        excluded_fields = ("created_at",)
        return all(
            getattr(self, field) == getattr(other, field) for field in all_fields if field not in excluded_fields
        )


class UnsupportedAutomanagedTypeError(Exception):
    pass


class InvalidDatabaseModelDefinitionError(Exception):
    pass


def _get_sqlalchemy_type(pydantic_type: type) -> tuple[type | DateTime, bool]:
    if pydantic_type in _PYDANTIC_TO_SQLALCHEMY_TYPES:
        return _PYDANTIC_TO_SQLALCHEMY_TYPES[pydantic_type], False
    leaf_types = extract_leaf_types(pydantic_type)
    is_nullable = type(None) in leaf_types
    args = tuple(arg for arg in leaf_types if arg is not type(None))
    for base_type, sqlalchemy_type in _PYDANTIC_TO_SQLALCHEMY_TYPES.items():
        if all(isinstance(arg, type) and issubclass(arg, base_type) for arg in args):
            return sqlalchemy_type, is_nullable

    raise UnsupportedAutomanagedTypeError(f"Unsupported Pydantic type: {pydantic_type}")


class InvalidFieldsError(Exception):
    pass


def create_tables(
    table_name: str,
    model_cls: type[DatabaseModel],
    constraints: tuple[Constraint, ...] = (),
    monotonic_columns: frozenset[str] = frozenset(),
) -> tuple[Table, Table]:
    """Create a single mutable table for the model, keyed by ``object_id``.

    Returns the table twice: callers historically held a (snapshot, _latest)
    pair, but the two-table append-only pattern was removed — both references
    now point at the one mutable table.

    ``monotonic_columns`` may only increase (e.g. a soft-delete flag that must
    never flip back to False under a concurrent stale write); the upsert path
    enforces that with ``MAX()`` (see ``_upsert_model``).
    """
    columns: list[Column] = []
    for field_name, field in model_cls.model_fields.items():
        pydantic_type = field.annotation
        assert pydantic_type is not None, f"Field {field_name} has no type annotation"
        column_type, is_nullable = _get_sqlalchemy_type(pydantic_type)
        if field_name == CREATED_AT:
            assert not is_nullable
            columns.append(Column(field_name, column_type, nullable=False, default=field.default_factory))
        else:
            columns.append(
                Column(field_name, column_type, primary_key=(field_name == OBJECT_ID), nullable=is_nullable)
            )

    if not any(column.name == OBJECT_ID for column in columns):
        raise InvalidFieldsError(f"Field {OBJECT_ID} not found.")

    table = Table(table_name, METADATA, *columns, *constraints)
    if monotonic_columns:
        table.info["monotonic_columns"] = monotonic_columns
    AUTOMANAGED_MODEL_CLASSES.add(model_cls)
    return table, table
