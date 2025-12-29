# Changelog

## [1.0.1] - 2025-12-29

### Changed
- **Default Alignment**: `dumps()` now defaults to `alignColumns=false` for token efficiency
- **Delimiter Option**: New `delimiter` parameter in `dumps(doc, { delimiter: ' ' })` for custom column separators

### Fixed
- Serializer now uses configurable delimiter instead of hardcoded space

## [1.0.0] - 2025-12-25

### Initial Release
- ISON v1.0 Parser for TypeScript
- Full TypeScript type definitions
- Full support for ISON and ISONL formats
- Reference syntax (`:id`, `:type:id`, `:RELATIONSHIP:id`)
- Type inference and annotations
- Quoted string handling with escape sequences
- JSON export via `toJson()`
- ISONL streaming support
- Works in Node.js and browser environments
- Zero runtime dependencies
