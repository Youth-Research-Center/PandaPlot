# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning tracks the tags published via the **Build Release Installer**
GitHub Actions workflow, not necessarily `pyproject.toml`'s version string.

When you open a PR with a user-facing change, add an entry under
`[Unreleased]`. Before running a release, a maintainer renames
`[Unreleased]` to the new version and date, and that section is pulled
into the GitHub Release notes automatically (see `.github/workflows/release_installer.yml`).

## [Unreleased]

### Added
- Stacked Bar chart type: each series stacks on top of the earlier ones at the same X (negative values stack downward), with error bars, value labels, a wizard preview, and lossless switching to and from Bar. Fits are not available on stacked charts.
- Date-typed dataset cells support text entry and calendar selection, with undo/redo and timezone-aware values preserved.
- Standalone desktop installer packaging via `pyside6-deploy`/Nuitka (`scripts/build_installer.py`, `pysidedeploy.spec`).
- `Build Release Installer` GitHub Actions workflow: builds installers for Linux, Windows, and macOS, and publishes them to a GitHub Release with SHA256 checksums under a user-supplied version tag.

### Changed
- The packaged Windows executable no longer opens a console window; logs are written to `~/.pandaplot/application.log` instead of the process's working directory.
