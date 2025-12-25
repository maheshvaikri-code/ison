//! # ISON Plugins
//!
//! Export data from databases and vector stores to ISON format.
//!
//! ## Available Plugins
//!
//! - `rudradb` - RudraDB vector database (requires `rudradb` feature)
//!
//! ## Usage
//!
//! ```rust,ignore
//! use ison_parser::plugins::RudraDBToISON;
//!
//! let exporter = RudraDBToISON::new(db);
//! let ison = exporter.export_all()?;
//! ```

#[cfg(feature = "rudradb")]
mod rudradb_plugin;

#[cfg(feature = "rudradb")]
pub use rudradb_plugin::*;
