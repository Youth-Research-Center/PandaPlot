"""Project file schema version.

Bump this whenever a migration is added to `per_item/` or `cross_item/`
that upgrades project data to a new shape. A project file's own
`schema_version` (or `0`, for any file saved before this field existed)
records what shape it's actually in; `ProjectDataManager.load()` runs the
registered migrations to bring a loaded project up to this version
before handing it back to the caller.

Also bump it when a release starts persisting data an older build would
silently ignore and drop on its next save (version 4: dataset formula
columns). `ProjectDataManager.load()` rejects files newer than the running
build, so the bump is what keeps an older build from opening, stripping and
re-saving such a project. That needs no migration function: files at the
previous version load as they are.
"""

CURRENT_SCHEMA_VERSION = 4
