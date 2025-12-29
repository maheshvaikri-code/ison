# Changelog

## [1.0.1] - 2025-12-29

### Changed
- **Default Alignment**: `dumps()` now defaults to `align_columns=false` for token efficiency
- **Delimiter Support**: Added `delimiter` parameter to `dumps()` function

## [1.0.0] - 2025-12-25

### Initial Release
- ISON v1.0 Parser for C++17
- Header-only library
- Full support for ISON and ISONL formats
- Reference syntax (`:id`, `:type:id`, `:RELATIONSHIP:id`)
- Type inference and annotations
- Quoted string handling with escape sequences
- JSON export
- ISONL streaming support
- Compatible with llama.cpp and modern C++ projects
