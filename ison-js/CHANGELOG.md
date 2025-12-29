# Changelog

## [1.0.1] - 2025-12-29

### Fixed
- **ESM Build**: Fixed IIFE wrapper removal in ESM build script for proper ES module support

### Changed
- **Default Alignment**: `dumps()` now defaults to `alignColumns=false` for token efficiency

## [1.0.0] - 2025-12-25

### Initial Release
- ISON v1.0 Reference Parser for JavaScript
- Full support for ISON and ISONL formats
- Reference syntax (`:id`, `:type:id`, `:RELATIONSHIP:id`)
- Type inference (int, float, bool, string, null)
- Quoted string handling with escape sequences
- JSON to ISON and ISON to JSON conversion
- ISONL streaming support
- Works in Node.js and browser environments
- Zero dependencies
