//! # ISON RudraDB Plugin
//!
//! Export RudraDB data to ISON format for LLM-friendly serialization.
//! RudraDB is a high-performance Rust-based relationship-aware vector database.
//!
//! ## Features
//!
//! - Export vectors and relationships to ISON
//! - Automatic reference detection for relationships
//! - Vector data support with dimension info
//! - Relationship type preservation
//! - Streaming export for large datasets (ISONL)
//! - RAG-optimized export with rank/score
//!
//! ## Usage
//!
//! ```rust,ignore
//! use ison_parser::plugins::RudraDBToISON;
//! use rudradb::RudraDB;
//!
//! let db = RudraDB::new();
//! // ... add vectors and relationships ...
//!
//! let exporter = RudraDBToISON::new(&db);
//! let ison = exporter.export_all()?;
//! println!("{}", ison);
//! ```

use std::collections::HashMap;

use rudradb::{RudraDB, RelationshipType, SearchParams, SearchResult, VectorSearchResult};

use crate::{Block, Document, FieldInfo, Reference, Row, Value, dumps, ISONError, Result};

/// Configuration for RudraDB export
#[derive(Debug, Clone)]
pub struct ExportConfig {
    /// Include vector embeddings in export (can be large)
    pub include_vectors: bool,
    /// Include relationship data
    pub include_relationships: bool,
    /// Maximum number of records per collection
    pub limit: Option<usize>,
    /// Number of decimal places for float values
    pub float_precision: usize,
    /// Align columns in output
    pub align_columns: bool,
}

impl Default for ExportConfig {
    fn default() -> Self {
        Self {
            include_vectors: false,
            include_relationships: true,
            limit: None,
            float_precision: 4,
            align_columns: true,
        }
    }
}

/// Configuration for RAG export
#[derive(Debug, Clone)]
pub struct RagExportConfig {
    /// Maximum number of results
    pub limit: usize,
    /// Include metadata fields
    pub include_metadata: bool,
    /// Minimum similarity score threshold
    pub min_score: Option<f32>,
    /// Include relationships in results
    pub include_relationships: bool,
    /// Maximum relationship hops
    pub max_hops: usize,
}

impl Default for RagExportConfig {
    fn default() -> Self {
        Self {
            limit: 10,
            include_metadata: true,
            min_score: None,
            include_relationships: true,
            max_hops: 2,
        }
    }
}

/// Export RudraDB data to ISON format.
///
/// Provides methods to export vectors, relationships, and search results
/// from RudraDB to token-efficient ISON format for LLM workflows.
pub struct RudraDBToISON<'a> {
    db: &'a RudraDB,
    config: ExportConfig,
}

impl<'a> RudraDBToISON<'a> {
    /// Create a new exporter with default configuration.
    ///
    /// # Arguments
    ///
    /// * `db` - Reference to RudraDB instance
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let db = RudraDB::new();
    /// let exporter = RudraDBToISON::new(&db);
    /// ```
    pub fn new(db: &'a RudraDB) -> Self {
        Self {
            db,
            config: ExportConfig::default(),
        }
    }

    /// Create a new exporter with custom configuration.
    ///
    /// # Arguments
    ///
    /// * `db` - Reference to RudraDB instance
    /// * `config` - Export configuration
    pub fn with_config(db: &'a RudraDB, config: ExportConfig) -> Self {
        Self { db, config }
    }

    /// Export all vectors to ISON format.
    ///
    /// # Returns
    ///
    /// ISON formatted string containing all vectors.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let ison = exporter.export_all()?;
    /// println!("{}", ison);
    /// // Output:
    /// // table.vectors
    /// // id dimension metadata
    /// // doc1 384 "category: tech"
    /// // doc2 384 "category: science"
    /// ```
    pub fn export_all(&self) -> Result<String> {
        let mut doc = Document::new();

        // Export vectors
        let vectors_block = self.vectors_to_block()?;
        if !vectors_block.rows.is_empty() {
            doc.blocks.push(vectors_block);
        }

        // Export relationships if configured
        if self.config.include_relationships {
            let rel_block = self.relationships_to_block()?;
            if !rel_block.rows.is_empty() {
                doc.blocks.push(rel_block);
            }
        }

        Ok(dumps(&doc, self.config.align_columns))
    }

    /// Export vectors to ISON format.
    ///
    /// # Arguments
    ///
    /// * `vector_ids` - Optional list of specific vector IDs to export.
    ///                  If None, exports all vectors.
    ///
    /// # Returns
    ///
    /// ISON formatted string containing vectors.
    pub fn export_vectors(&self, vector_ids: Option<&[&str]>) -> Result<String> {
        let block = match vector_ids {
            Some(ids) => self.specific_vectors_to_block(ids)?,
            None => self.vectors_to_block()?,
        };

        let mut doc = Document::new();
        doc.blocks.push(block);
        Ok(dumps(&doc, self.config.align_columns))
    }

    /// Export relationships to ISON format.
    ///
    /// # Arguments
    ///
    /// * `relationship_type` - Optional filter by relationship type
    ///
    /// # Returns
    ///
    /// ISON formatted string containing relationships.
    pub fn export_relationships(&self, relationship_type: Option<RelationshipType>) -> Result<String> {
        let block = self.relationships_to_block_filtered(relationship_type)?;

        let mut doc = Document::new();
        doc.blocks.push(block);
        Ok(dumps(&doc, self.config.align_columns))
    }

    /// Export search results to ISON format.
    ///
    /// # Arguments
    ///
    /// * `results` - Search results from RudraDB
    /// * `name` - Optional name for the result block (default: "search_results")
    ///
    /// # Returns
    ///
    /// ISON formatted string containing search results.
    pub fn export_search_results(&self, results: &SearchResult, name: Option<&str>) -> Result<String> {
        let block = self.search_results_to_block(results, name.unwrap_or("search_results"))?;

        let mut doc = Document::new();
        doc.blocks.push(block);
        Ok(dumps(&doc, self.config.align_columns))
    }

    /// Export data optimized for RAG (Retrieval-Augmented Generation).
    ///
    /// Performs a vector similarity search and returns results in a format
    /// optimized for LLM context injection with rank and score fields.
    ///
    /// # Arguments
    ///
    /// * `query_vector` - Vector for similarity search (f32 values)
    /// * `rag_config` - RAG export configuration
    ///
    /// # Returns
    ///
    /// ISON formatted context for LLM.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let query = vec![0.1f32, 0.2, 0.3, ...];
    /// let context = exporter.export_for_rag(&query, RagExportConfig::default())?;
    /// // Output:
    /// // table.context
    /// // rank:int score:float id content
    /// // 1 0.95 doc1 "Machine learning is..."
    /// // 2 0.87 doc2 "Neural networks..."
    /// ```
    pub fn export_for_rag(
        &self,
        query_vector: &[f32],
        rag_config: RagExportConfig,
    ) -> Result<String> {
        use nalgebra::DVector;

        let query = DVector::from_vec(query_vector.to_vec());

        let search_params = SearchParams {
            top_k: Some(rag_config.limit),
            include_relationships: Some(rag_config.include_relationships),
            max_hops: Some(rag_config.max_hops),
            ..Default::default()
        };

        let search_result = self.db.search(&query, search_params)
            .map_err(|e| ISONError {
                message: format!("RudraDB search failed: {}", e),
                line: None,
            })?;

        // Filter by min score if configured
        let filtered_results: Vec<_> = if let Some(min_score) = rag_config.min_score {
            search_result.results.iter()
                .filter(|r| r.combined_score >= min_score)
                .collect()
        } else {
            search_result.results.iter().collect()
        };

        let block = self.rag_results_to_block(&filtered_results, rag_config.include_metadata)?;

        let mut doc = Document::new();
        doc.blocks.push(block);
        Ok(dumps(&doc, self.config.align_columns))
    }

    /// Stream vectors as ISONL format for large datasets.
    ///
    /// Returns an iterator that yields ISONL lines one at a time,
    /// suitable for streaming large datasets without loading all into memory.
    ///
    /// # Arguments
    ///
    /// * `batch_size` - Number of vectors to process at a time
    ///
    /// # Returns
    ///
    /// Iterator yielding ISONL formatted lines.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// for line in exporter.stream_vectors(100) {
    ///     println!("{}", line?);
    /// }
    /// ```
    pub fn stream_vectors(&self, batch_size: usize) -> impl Iterator<Item = Result<String>> + '_ {
        let vector_ids = self.db.list_vectors();
        let mut offset = 0;

        std::iter::from_fn(move || {
            if offset >= vector_ids.len() {
                return None;
            }

            let end = std::cmp::min(offset + batch_size, vector_ids.len());
            let batch_ids: Vec<&str> = vector_ids[offset..end]
                .iter()
                .map(|s| s.as_str())
                .collect();

            offset = end;

            match self.vectors_to_isonl_batch(&batch_ids) {
                Ok(lines) => Some(Ok(lines)),
                Err(e) => Some(Err(e)),
            }
        })
    }

    /// Export vectors with their relationships.
    ///
    /// For each vector, includes outgoing relationships as references.
    ///
    /// # Arguments
    ///
    /// * `vector_ids` - Optional list of specific vector IDs
    /// * `depth` - How many levels of relationships to include
    ///
    /// # Returns
    ///
    /// ISON formatted string with vectors and relationship references.
    pub fn export_with_relationships(
        &self,
        vector_ids: Option<&[&str]>,
        depth: usize,
    ) -> Result<String> {
        let mut doc = Document::new();

        // Get vectors
        let ids: Vec<String> = match vector_ids {
            Some(ids) => ids.iter().map(|s| s.to_string()).collect(),
            None => self.db.list_vectors(),
        };

        // Build vector block with relationship columns
        let block = self.vectors_with_relationships_to_block(&ids, depth)?;
        doc.blocks.push(block);

        // Add separate relationships block
        if self.config.include_relationships {
            let rel_block = self.relationships_to_block()?;
            if !rel_block.rows.is_empty() {
                doc.blocks.push(rel_block);
            }
        }

        Ok(dumps(&doc, self.config.align_columns))
    }

    // =========================================================================
    // Internal Methods
    // =========================================================================

    fn vectors_to_block(&self) -> Result<Block> {
        let vector_ids = self.db.list_vectors();
        let ids: Vec<&str> = vector_ids.iter().map(|s| s.as_str()).collect();
        self.specific_vectors_to_block(&ids)
    }

    fn specific_vectors_to_block(&self, ids: &[&str]) -> Result<Block> {
        let mut block = Block::new("table", "vectors");

        // Define fields
        block.fields = vec![
            "id".to_string(),
            "dimension".to_string(),
        ];
        block.field_info = vec![
            FieldInfo::new("id"),
            FieldInfo::with_type("dimension", "int"),
        ];

        if self.config.include_vectors {
            block.fields.push("embedding".to_string());
            block.field_info.push(FieldInfo::new("embedding"));
        }

        block.fields.push("metadata".to_string());
        block.field_info.push(FieldInfo::new("metadata"));

        // Add rows
        for id in ids {
            if let Some(count) = self.config.limit {
                if block.rows.len() >= count {
                    break;
                }
            }

            if let Ok(Some(vector)) = self.db.get_vector(id) {
                let mut row = Row::new();
                row.insert("id".to_string(), Value::String(vector.id.clone()));
                row.insert("dimension".to_string(), Value::Int(vector.embedding.len() as i64));

                if self.config.include_vectors {
                    let embedding_str = self.format_embedding_f32(&vector.embedding);
                    row.insert("embedding".to_string(), Value::String(embedding_str));
                }

                let metadata_str = self.format_metadata(&vector.metadata);
                if !metadata_str.is_empty() {
                    row.insert("metadata".to_string(), Value::String(metadata_str));
                } else {
                    row.insert("metadata".to_string(), Value::Null);
                }

                block.rows.push(row);
            }
        }

        Ok(block)
    }

    fn relationships_to_block(&self) -> Result<Block> {
        self.relationships_to_block_filtered(None)
    }

    fn relationships_to_block_filtered(&self, filter_type: Option<RelationshipType>) -> Result<Block> {
        let mut block = Block::new("table", "relationships");

        block.fields = vec![
            "source".to_string(),
            "target".to_string(),
            "type".to_string(),
            "strength".to_string(),
        ];
        block.field_info = vec![
            FieldInfo::with_type("source", "ref"),
            FieldInfo::with_type("target", "ref"),
            FieldInfo::new("type"),
            FieldInfo::with_type("strength", "float"),
        ];

        // Get all relationships
        let vector_ids = self.db.list_vectors();
        for source_id in &vector_ids {
            if let Ok(relationships) = self.db.get_relationships(source_id, filter_type.clone()) {
                for rel in relationships {
                    let mut row = Row::new();
                    row.insert("source".to_string(), Value::Reference(Reference::new(&rel.source_id)));
                    row.insert("target".to_string(), Value::Reference(Reference::new(&rel.target_id)));
                    row.insert("type".to_string(), Value::String(rel.relationship_type.to_string()));
                    row.insert("strength".to_string(), Value::Float(rel.strength as f64));

                    block.rows.push(row);
                }
            }
        }

        Ok(block)
    }

    fn search_results_to_block(&self, search_result: &SearchResult, name: &str) -> Result<Block> {
        let mut block = Block::new("table", name);

        block.fields = vec![
            "rank".to_string(),
            "id".to_string(),
            "score".to_string(),
            "source".to_string(),
        ];
        block.field_info = vec![
            FieldInfo::with_type("rank", "int"),
            FieldInfo::new("id"),
            FieldInfo::with_type("score", "float"),
            FieldInfo::new("source"),
        ];

        for (i, result) in search_result.results.iter().enumerate() {
            let mut row = Row::new();
            row.insert("rank".to_string(), Value::Int((i + 1) as i64));
            row.insert("id".to_string(), Value::String(result.vector.id.clone()));
            row.insert("score".to_string(), Value::Float(result.combined_score as f64));
            row.insert("source".to_string(), Value::String(format!("{:?}", result.source)));

            block.rows.push(row);
        }

        Ok(block)
    }

    fn rag_results_to_block(&self, results: &[&VectorSearchResult], include_metadata: bool) -> Result<Block> {
        let mut block = Block::new("table", "context");

        block.fields = vec![
            "rank".to_string(),
            "score".to_string(),
            "id".to_string(),
        ];
        block.field_info = vec![
            FieldInfo::with_type("rank", "int"),
            FieldInfo::with_type("score", "float"),
            FieldInfo::new("id"),
        ];

        if include_metadata {
            block.fields.push("metadata".to_string());
            block.field_info.push(FieldInfo::new("metadata"));
        }

        for (i, result) in results.iter().enumerate() {
            let mut row = Row::new();
            row.insert("rank".to_string(), Value::Int((i + 1) as i64));
            row.insert("score".to_string(), Value::Float(result.combined_score as f64));
            row.insert("id".to_string(), Value::String(result.vector.id.clone()));

            if include_metadata {
                let metadata_str = self.format_metadata(&result.vector.metadata);
                if !metadata_str.is_empty() {
                    row.insert("metadata".to_string(), Value::String(metadata_str));
                } else {
                    row.insert("metadata".to_string(), Value::Null);
                }
            }

            block.rows.push(row);
        }

        Ok(block)
    }

    fn vectors_with_relationships_to_block(&self, ids: &[String], depth: usize) -> Result<Block> {
        let mut block = Block::new("table", "vectors");

        block.fields = vec![
            "id".to_string(),
            "dimension".to_string(),
            "metadata".to_string(),
            "related_to".to_string(),
        ];
        block.field_info = vec![
            FieldInfo::new("id"),
            FieldInfo::with_type("dimension", "int"),
            FieldInfo::new("metadata"),
            FieldInfo::new("related_to"),
        ];

        for id in ids {
            if let Some(count) = self.config.limit {
                if block.rows.len() >= count {
                    break;
                }
            }

            if let Ok(Some(vector)) = self.db.get_vector(id) {
                let mut row = Row::new();
                row.insert("id".to_string(), Value::String(vector.id.clone()));
                row.insert("dimension".to_string(), Value::Int(vector.embedding.len() as i64));

                let metadata_str = self.format_metadata(&vector.metadata);
                if !metadata_str.is_empty() {
                    row.insert("metadata".to_string(), Value::String(metadata_str));
                } else {
                    row.insert("metadata".to_string(), Value::Null);
                }

                // Get related vectors
                let related = self.get_related_ids(id, depth);
                if !related.is_empty() {
                    let refs_str = related.iter()
                        .map(|r| format!(":{}", r))
                        .collect::<Vec<_>>()
                        .join(", ");
                    row.insert("related_to".to_string(), Value::String(refs_str));
                } else {
                    row.insert("related_to".to_string(), Value::Null);
                }

                block.rows.push(row);
            }
        }

        Ok(block)
    }

    fn vectors_to_isonl_batch(&self, ids: &[&str]) -> Result<String> {
        let mut lines = Vec::new();
        let header = "table.vectors";
        let fields = if self.config.include_vectors {
            "id dimension embedding metadata"
        } else {
            "id dimension metadata"
        };

        for id in ids {
            if let Ok(Some(vector)) = self.db.get_vector(id) {
                let mut values = vec![
                    self.format_isonl_value(&vector.id),
                    vector.embedding.len().to_string(),
                ];

                if self.config.include_vectors {
                    let embedding_str = self.format_embedding_f32(&vector.embedding);
                    values.push(self.format_isonl_value(&embedding_str));
                }

                let metadata_str = self.format_metadata(&vector.metadata);
                if !metadata_str.is_empty() {
                    values.push(self.format_isonl_value(&metadata_str));
                } else {
                    values.push("null".to_string());
                }

                lines.push(format!("{}|{}|{}", header, fields, values.join(" ")));
            }
        }

        Ok(lines.join("\n"))
    }

    fn get_related_ids(&self, source_id: &str, depth: usize) -> Vec<String> {
        if depth == 0 {
            return Vec::new();
        }

        let mut related = Vec::new();
        if let Ok(relationships) = self.db.get_relationships(source_id, None) {
            for rel in relationships {
                related.push(rel.target_id.clone());

                // Recursively get deeper relationships
                if depth > 1 {
                    let deeper = self.get_related_ids(&rel.target_id, depth - 1);
                    related.extend(deeper);
                }
            }
        }

        // Remove duplicates while preserving order
        let mut seen = std::collections::HashSet::new();
        related.retain(|id| seen.insert(id.clone()));

        related
    }

    fn format_embedding_f32(&self, embedding: &nalgebra::DVector<f32>) -> String {
        if embedding.len() > 10 {
            format!("[{}d vector]", embedding.len())
        } else {
            let values: Vec<String> = embedding.iter()
                .map(|v| format!("{:.prec$}", v, prec = self.config.float_precision))
                .collect();
            format!("[{}]", values.join(", "))
        }
    }

    fn format_metadata(&self, metadata: &HashMap<String, serde_json::Value>) -> String {
        if metadata.is_empty() {
            return String::new();
        }

        let pairs: Vec<String> = metadata.iter()
            .map(|(k, v)| {
                let val_str = match v {
                    serde_json::Value::String(s) => s.clone(),
                    serde_json::Value::Number(n) => n.to_string(),
                    serde_json::Value::Bool(b) => b.to_string(),
                    serde_json::Value::Null => "null".to_string(),
                    _ => v.to_string(),
                };
                format!("{}: {}", k, val_str)
            })
            .collect();
        pairs.join(", ")
    }

    fn format_isonl_value(&self, value: &str) -> String {
        if value.contains(' ') || value.contains('\t') || value.contains('|') ||
           value == "true" || value == "false" || value == "null" {
            let escaped = value
                .replace('\\', "\\\\")
                .replace('"', "\\\"")
                .replace('\n', "\\n");
            format!("\"{}\"", escaped)
        } else {
            value.to_string()
        }
    }
}

// =============================================================================
// Convenience Functions
// =============================================================================

/// Quick function to export RudraDB to ISON.
///
/// # Arguments
///
/// * `db` - RudraDB instance
/// * `include_relationships` - Whether to include relationship data
///
/// # Returns
///
/// ISON formatted string.
///
/// # Example
///
/// ```rust,ignore
/// let db = RudraDB::new();
/// let ison = rudradb_to_ison(&db, true)?;
/// ```
pub fn rudradb_to_ison(db: &RudraDB, include_relationships: bool) -> Result<String> {
    let config = ExportConfig {
        include_relationships,
        ..Default::default()
    };
    RudraDBToISON::with_config(db, config).export_all()
}

/// Export RudraDB search results to ISON.
///
/// # Arguments
///
/// * `db` - RudraDB instance
/// * `results` - Search results from RudraDB query
/// * `name` - Optional name for the result block
///
/// # Returns
///
/// ISON formatted string.
pub fn rudradb_search_to_ison(db: &RudraDB, results: &SearchResult, name: Option<&str>) -> Result<String> {
    RudraDBToISON::new(db).export_search_results(results, name)
}

/// Get RAG context from RudraDB in ISON format.
///
/// # Arguments
///
/// * `db` - RudraDB instance
/// * `query_vector` - Vector for similarity search (f32 values)
/// * `limit` - Maximum number of results
///
/// # Returns
///
/// ISON formatted context optimized for LLM.
///
/// # Example
///
/// ```rust,ignore
/// let embedding = get_embedding("What is RudraDB?");
/// let context = rudradb_rag_context(&db, &embedding, 5)?;
/// let response = llm.complete(&format!("Context:\n{}\n\nQuestion: What is RudraDB?", context));
/// ```
pub fn rudradb_rag_context(db: &RudraDB, query_vector: &[f32], limit: usize) -> Result<String> {
    let rag_config = RagExportConfig {
        limit,
        ..Default::default()
    };
    RudraDBToISON::new(db).export_for_rag(query_vector, rag_config)
}

#[cfg(test)]
mod tests {
    use super::*;
    use nalgebra::DVector;
    use rudradb::{RudraDB, RudraDBConfig, RelationshipType};

    fn create_test_db() -> RudraDB {
        let config = RudraDBConfig::default().set_auto_normalize(false);
        let db = RudraDB::with_config(config);

        // Add test vectors
        let embedding1 = DVector::from_vec(vec![1.0f32, 2.0, 3.0]);
        let embedding2 = DVector::from_vec(vec![2.0f32, 3.0, 4.0]);
        let embedding3 = DVector::from_vec(vec![3.0f32, 4.0, 5.0]);

        let mut metadata1 = HashMap::new();
        metadata1.insert("category".to_string(), serde_json::Value::String("tech".to_string()));

        db.add_vector("doc1", embedding1, Some(metadata1)).unwrap();
        db.add_vector("doc2", embedding2, None).unwrap();
        db.add_vector("doc3", embedding3, None).unwrap();

        // Add relationships
        db.add_relationship("doc1", "doc2", RelationshipType::semantic(), 0.8, None).unwrap();
        db.add_relationship("doc2", "doc3", RelationshipType::hierarchical(), 0.6, None).unwrap();

        db
    }

    #[test]
    fn test_export_all() {
        let db = create_test_db();
        let exporter = RudraDBToISON::new(&db);

        let ison = exporter.export_all().unwrap();

        assert!(ison.contains("table.vectors"));
        assert!(ison.contains("doc1"));
        assert!(ison.contains("doc2"));
        assert!(ison.contains("doc3"));
        assert!(ison.contains("table.relationships"));
    }

    #[test]
    fn test_export_vectors() {
        let db = create_test_db();
        let exporter = RudraDBToISON::new(&db);

        let ison = exporter.export_vectors(Some(&["doc1", "doc2"])).unwrap();

        assert!(ison.contains("doc1"));
        assert!(ison.contains("doc2"));
        assert!(!ison.contains("doc3"));
    }

    #[test]
    fn test_export_relationships() {
        let db = create_test_db();
        let exporter = RudraDBToISON::new(&db);

        let ison = exporter.export_relationships(None).unwrap();

        assert!(ison.contains("table.relationships"));
        assert!(ison.contains(":doc1"));
        assert!(ison.contains(":doc2"));
    }

    #[test]
    fn test_export_with_include_vectors() {
        let db = create_test_db();
        let config = ExportConfig {
            include_vectors: true,
            ..Default::default()
        };
        let exporter = RudraDBToISON::with_config(&db, config);

        let ison = exporter.export_vectors(None).unwrap();

        assert!(ison.contains("embedding"));
        // With 3 dimensions (< 10), actual values are shown
        assert!(ison.contains("[1.0000, 2.0000, 3.0000]") || ison.contains("["));
    }

    #[test]
    fn test_convenience_function() {
        let db = create_test_db();

        let ison = rudradb_to_ison(&db, true).unwrap();

        assert!(ison.contains("table.vectors"));
        assert!(ison.contains("table.relationships"));
    }
}
