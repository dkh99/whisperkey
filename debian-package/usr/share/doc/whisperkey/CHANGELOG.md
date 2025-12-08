# Changelog

All notable changes to WhisperKey will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2] - 2024-12-08

### Fixed
- Added `libxcb-cursor0` dependency for Qt6 platform plugin support

## [0.3.1] - 2024-12-08

### Fixed
- Fixed Whisper model not downloading on first run (changed `local_files_only=False` to allow automatic model download)
- Updated installation docs to use `apt install` instead of `dpkg -i` for automatic dependency resolution

## [Unreleased]

### Added
- First version with working Python transcription app and GNOME Shell extension

---

## Release Notes Template

When preparing a new release, copy and fill out this template:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features and functionality

### Changed
- Changes to existing functionality
- Performance improvements
- Updated dependencies

### Deprecated
- Features that will be removed in future versions

### Removed
- Features removed in this version

### Fixed
- Bug fixes and corrections

### Security
- Security improvements and fixes
```

## Maintenance Notes

- **Version bumps**: Update version in `app/pyproject.toml` and create corresponding git tag
- **Release process**: Use `make release` to create tagged releases with packages
- **CI/CD**: GitHub Actions automatically builds and publishes releases when tags are pushed
- **Breaking changes**: Always bump major version for breaking changes
- **Dependencies**: Document significant dependency updates in changelog

## Links

- [Keep a Changelog](https://keepachangelog.com/)
- [Semantic Versioning](https://semver.org/)
- [WhisperKey Repository](https://github.com/your-username/WhisperKey)