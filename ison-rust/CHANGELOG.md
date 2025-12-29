# Changelog

## [1.0.1] - 2025-12-29

### Changed
- **Default Alignment**: `dumps()` now defaults to `align_columns=false` for token efficiency
- **Delimiter Support**: New `dumps_with_delimiter()` function for custom column separators

### Fixed
- `isonl_to_ison()` now uses `align_columns=false` by default for consistency

## [1.0.0] - 2025-12-25

### Initial Release
- ISON v1.0 Parser for Rust
- Zero-copy parsing where possible
- Full support for ISON and ISONL formats
- Reference syntax (`:id`, `:type:id`, `:RELATIONSHIP:id`)
- Type inference and annotations
- Quoted string handling with escape sequences
- Optional Serde integration for JSON export
- ISONL streaming support
- No unsafe code
