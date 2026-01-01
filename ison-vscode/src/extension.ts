import * as vscode from 'vscode';

// Token counting (simplified - approximates GPT tokenization)
function countTokens(text: string): number {
    // Simple approximation: ~4 chars per token on average
    return Math.ceil(text.length / 4);
}

// ISON to JSON conversion
function isonToJson(ison: string): string {
    const result: Record<string, any[]> = {};
    let currentBlock: { name: string; fields: string[]; rows: any[] } | null = null;

    const lines = ison.split('\n');
    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        if (trimmed === '---') continue;

        // Block header
        const blockMatch = trimmed.match(/^(table|object|list)\.(\w+)$/);
        if (blockMatch) {
            if (currentBlock) {
                result[currentBlock.name] = currentBlock.rows;
            }
            currentBlock = { name: blockMatch[2], fields: [], rows: [] };
            continue;
        }

        if (!currentBlock) continue;

        // Field definitions or data
        if (currentBlock.fields.length === 0) {
            currentBlock.fields = trimmed.split(/\s+/).map(f => f.split(':')[0]);
        } else {
            const values = parseValues(trimmed);
            const row: Record<string, any> = {};
            currentBlock.fields.forEach((field, i) => {
                row[field] = values[i] ?? null;
            });
            currentBlock.rows.push(row);
        }
    }

    if (currentBlock) {
        result[currentBlock.name] = currentBlock.rows;
    }

    return JSON.stringify(result, null, 2);
}

// Parse ISON values
function parseValues(line: string): any[] {
    const values: any[] = [];
    let current = '';
    let inQuotes = false;
    let quoteChar = '';

    for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (inQuotes) {
            if (char === '\\' && i + 1 < line.length) {
                current += line[++i];
            } else if (char === quoteChar) {
                inQuotes = false;
            } else {
                current += char;
            }
        } else if (char === '"' || char === "'") {
            inQuotes = true;
            quoteChar = char;
        } else if (char === ' ' || char === '\t') {
            if (current) {
                values.push(parseValue(current));
                current = '';
            }
        } else {
            current += char;
        }
    }

    if (current) {
        values.push(parseValue(current));
    }

    return values;
}

function parseValue(str: string): any {
    if (str === 'null' || str === '~') return null;
    if (str === 'true') return true;
    if (str === 'false') return false;
    if (str.startsWith(':')) return str; // Reference
    const num = Number(str);
    if (!isNaN(num)) return num;
    return str;
}

// JSON to ISON conversion
function jsonToIson(json: string): string {
    const data = JSON.parse(json);
    const lines: string[] = [];

    for (const [name, records] of Object.entries(data)) {
        if (!Array.isArray(records) || records.length === 0) continue;

        lines.push(`table.${name}`);

        // Get fields from first record
        const fields = Object.keys(records[0] as Record<string, any>);
        lines.push(fields.join(' '));

        // Add data rows
        for (const record of records as Record<string, any>[]) {
            const values = fields.map(f => formatValue(record[f]));
            lines.push(values.join(' '));
        }

        lines.push('');
    }

    return lines.join('\n').trim();
}

function formatValue(value: any): string {
    if (value === null || value === undefined) return 'null';
    if (typeof value === 'boolean') return value.toString();
    if (typeof value === 'number') return value.toString();
    if (typeof value === 'string') {
        if (value.includes(' ') || value.includes('\t') || value.includes('\n')) {
            return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
        }
        if (value === 'true' || value === 'false' || value === 'null') {
            return `"${value}"`;
        }
        return value || '""';
    }
    return JSON.stringify(value);
}

// Status bar item for token count
let statusBarItem: vscode.StatusBarItem;

export function activate(context: vscode.ExtensionContext) {
    console.log('ISON extension activated');

    // Create status bar item
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'ison.countTokens';
    context.subscriptions.push(statusBarItem);

    // Update token count on text change
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(updateTokenCount),
        vscode.workspace.onDidChangeTextDocument(e => {
            if (vscode.window.activeTextEditor?.document === e.document) {
                updateTokenCount(vscode.window.activeTextEditor);
            }
        })
    );

    // Initial update
    updateTokenCount(vscode.window.activeTextEditor);

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('ison.convertToJson', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            try {
                const ison = editor.document.getText();
                const json = isonToJson(ison);

                const doc = await vscode.workspace.openTextDocument({
                    content: json,
                    language: 'json'
                });
                await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside);
            } catch (e: any) {
                vscode.window.showErrorMessage(`Failed to convert: ${e.message}`);
            }
        }),

        vscode.commands.registerCommand('ison.convertFromJson', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            try {
                const json = editor.document.getText();
                const ison = jsonToIson(json);

                const doc = await vscode.workspace.openTextDocument({
                    content: ison,
                    language: 'ison'
                });
                await vscode.window.showTextDocument(doc, vscode.ViewColumn.Beside);
            } catch (e: any) {
                vscode.window.showErrorMessage(`Failed to convert: ${e.message}`);
            }
        }),

        vscode.commands.registerCommand('ison.countTokens', () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const text = editor.document.getText();
            const isonTokens = countTokens(text);

            // Compare with JSON equivalent
            try {
                const json = isonToJson(text);
                const jsonTokens = countTokens(json);
                const savings = Math.round((1 - isonTokens / jsonTokens) * 100);

                vscode.window.showInformationMessage(
                    `ISON: ~${isonTokens} tokens | JSON equivalent: ~${jsonTokens} tokens | Savings: ${savings}%`
                );
            } catch {
                vscode.window.showInformationMessage(`ISON: ~${isonTokens} tokens`);
            }
        }),

        vscode.commands.registerCommand('ison.formatDocument', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const config = vscode.workspace.getConfiguration('ison');
            const alignColumns = config.get<boolean>('alignColumns', true);

            // Format the document
            const text = editor.document.getText();
            const formatted = formatIson(text, alignColumns);

            await editor.edit(editBuilder => {
                const fullRange = new vscode.Range(
                    editor.document.positionAt(0),
                    editor.document.positionAt(text.length)
                );
                editBuilder.replace(fullRange, formatted);
            });
        })
    );
}

function updateTokenCount(editor: vscode.TextEditor | undefined) {
    if (!editor || (editor.document.languageId !== 'ison' && editor.document.languageId !== 'isonl')) {
        statusBarItem.hide();
        return;
    }

    const config = vscode.workspace.getConfiguration('ison');
    if (!config.get<boolean>('showTokenCount', true)) {
        statusBarItem.hide();
        return;
    }

    const text = editor.document.getText();
    const tokens = countTokens(text);
    statusBarItem.text = `$(symbol-number) ~${tokens} tokens`;
    statusBarItem.tooltip = 'ISON Token Count (click for comparison)';
    statusBarItem.show();
}

function formatIson(text: string, alignColumns: boolean): string {
    const lines = text.split('\n');
    const result: string[] = [];
    let currentBlock: string[] = [];
    let inBlock = false;

    for (const line of lines) {
        const trimmed = line.trim();

        if (!trimmed || trimmed.startsWith('#')) {
            if (inBlock && currentBlock.length > 0) {
                result.push(...formatBlock(currentBlock, alignColumns));
                currentBlock = [];
            }
            result.push(line);
            inBlock = false;
            continue;
        }

        if (trimmed.match(/^(table|object|list)\.\w+$/)) {
            if (currentBlock.length > 0) {
                result.push(...formatBlock(currentBlock, alignColumns));
                currentBlock = [];
            }
            result.push(trimmed);
            inBlock = true;
            continue;
        }

        if (trimmed === '---') {
            if (currentBlock.length > 0) {
                result.push(...formatBlock(currentBlock, alignColumns));
                currentBlock = [];
            }
            result.push(trimmed);
            continue;
        }

        if (inBlock) {
            currentBlock.push(trimmed);
        } else {
            result.push(line);
        }
    }

    if (currentBlock.length > 0) {
        result.push(...formatBlock(currentBlock, alignColumns));
    }

    return result.join('\n');
}

function formatBlock(lines: string[], alignColumns: boolean): string[] {
    if (!alignColumns || lines.length === 0) return lines;

    // Parse all lines into columns
    const parsed = lines.map(line => parseValues(line.toString()).map(v => formatValue(v)));

    // Find max width for each column
    const maxCols = Math.max(...parsed.map(row => row.length));
    const widths: number[] = [];

    for (let col = 0; col < maxCols; col++) {
        let maxWidth = 0;
        for (const row of parsed) {
            if (row[col]) {
                maxWidth = Math.max(maxWidth, row[col].length);
            }
        }
        widths.push(maxWidth);
    }

    // Format each line with padding
    return parsed.map(row => {
        return row.map((val, i) => val.padEnd(widths[i] || 0)).join(' ').trimEnd();
    });
}

export function deactivate() {
    if (statusBarItem) {
        statusBarItem.dispose();
    }
}
