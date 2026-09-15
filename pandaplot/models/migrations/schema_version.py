"""Project file schema version.

Bump this whenever a migration is added to `per_item/` or `cross_item/`
that upgrades project data to a new shape. A project file's own
`schema_version` (or `0`, for any file saved before this field existed)
records what shape it's actually in; `ProjectDataManager.load()` runs the
registered migrations to bring a loaded project up to this version
before handing it back to the caller.
"""

CURRENT_SCHEMA_VERSION = 2
