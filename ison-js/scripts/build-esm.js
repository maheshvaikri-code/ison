#!/usr/bin/env node
/**
 * Build script to create ESM version of ISON parser
 */

const fs = require('fs');
const path = require('path');

const srcPath = path.join(__dirname, '..', 'src', 'ison-parser.js');
const distPath = path.join(__dirname, '..', 'dist', 'ison-parser.esm.js');

let content = fs.readFileSync(srcPath, 'utf8');

// Replace the export section with ESM exports
const exportSection = `
// =============================================================================
// Export (ESM)
// =============================================================================

export {
    Reference,
    FieldInfo,
    Block,
    Document,
    ISONError,
    ISONSyntaxError,
    ISONLRecord,
    ISONLParser,
    ISONLSerializer,
    loads,
    dumps,
    fromDict,
    jsonToISON,
    isonToJSON,
    loadsISONL,
    dumpsISONL,
    isonToISONL,
    isonlToISON,
    isonlStream,
};

export const version = '1.0.1';

export default {
    Reference,
    FieldInfo,
    Block,
    Document,
    ISONError,
    ISONSyntaxError,
    ISONLRecord,
    ISONLParser,
    ISONLSerializer,
    loads,
    dumps,
    fromDict,
    jsonToISON,
    isonToJSON,
    loadsISONL,
    dumpsISONL,
    isonToISONL,
    isonlToISON,
    isonlStream,
    version: '1.0.1'
};
`;

// Remove the IIFE wrapper and existing exports
content = content.replace(/\(function\s*\(global\)\s*\{\s*'use strict';/m, '');
content = content.replace(/\}\)\(typeof window !== 'undefined' \? window : global\);\s*$/m, '');

// Remove the existing export section
content = content.replace(/\/\/ =============================================================================\n\s*\/\/ Export\n[\s\S]*$/, '');

// Add ESM exports
content = content.trim() + '\n' + exportSection;

fs.writeFileSync(distPath, content, 'utf8');
console.log('ESM build complete: dist/ison-parser.esm.js');
