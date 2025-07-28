# Coda Workspace Exporter: Project Specification

## 1. Overview

The primary goal of the Coda Workspace Exporter is to perform a **complete and high-fidelity extraction** of all data from a Cda workspace into a structured, local, and human-readable format.

This tool is the foundational first step in a two-step migration process. Its sole responsibility is to **export**, not to transform. It creates a clean, well-documented dataset that can then be used as a reliable input for a subsequent transformation script or a task given to an AI agent.

## 2. Core Principles

* **Completeness**: The exporter must capture every possible piece of data and metadata available through the Coda API. This includes not just content, but also the relationships and logic that give the Coda workspace its structure.
* **High Fidelity**: The export must preserve the original data with as much richness as possible. This means fetching rich-text values for table cells, preserving formula strings, and capturing the exact settings of views.
* **Decoupling**: The exporter's responsibility ends when the data is successfully saved to the local file system. It should have no knowledge of the target platform (e.g., Obsidian, Logseq). This separation of concerns makes both the exporter and the future transformer easier to develop, test, and maintain.
* **Idempotency**: Running the exporter multiple times should result in the same output, overwriting the previous export to ensure a clean slate for each run.

## 3. Functional Requirements: What to Export

The exporter must systematically discover and save the following components:

#### 3.1. Workspace Structure

* **[ ] Master Doc List**: A root `docs.json` file containing a list of all documents in the workspace, including their names and IDs.

#### 3.2. Per-Document Structure

For each document discovered, the exporter must create a dedicated folder and save:

* **[ ] Document Metadata**: A `doc_meta.json` file containing all metadata for the document (owner, creation/update times, etc.).

#### 3.3. Tables (The "Databases")

* **[ ] Full Row Data**: For each table, export all rows into a `{table_id}.json` file.
    * Must handle API pagination to ensure all rows are fetched.
    * Must use the `valueFormat: 'rich'` parameter to get structured JSON for lookups (`@-references`), people, and other rich cell types. This is critical for rebuilding links later.
* **[ ] Column Formulas & Metadata**: For each table, export the metadata of all its columns into a `{table_id}_columns.json` file.
    * This must include the `formula` string for any calculated columns.
    * It should also capture column formats (e.g., currency, date, select options).

#### 3.4. Views (The "Projections")

* **[ ] View Configuration**: For each view, export its settings into a `{view_id}_meta.json` file. This is a metadata-only export. The exporter **must not** export the *data* within the view, as that is redundant. The export must include:
    * The ID of the source table (`parentTable`).
    * The exact `filter` formula string.
    * The array of `sorts` applied to the view.
    * The `layout` type (e.g., `calendar`, `card`).

#### 3.5. Pages (The "Wikis")

* **[ ] Page Content**: For each page (Coda's wiki-like documents), initiate an export for its content.
  * The tool must be configurable to export in **both Markdown and HTML** formats, saving them with human-readable filenames based on the page name (e.g., `My Important Page.md` and `My Important Page.html`).
  * When page names contain filesystem-unsafe characters, they should be sanitized while preserving readability.
  * A `pages_metadata.json` file must be created to maintain the mapping between human-readable filenames, page IDs, and full page metadata for reliable downstream processing.
  * The exporter must handle the asynchronous nature of the Coda export API by polling for completion and then downloading the final content.

## 4. Directory Structure

The exporter creates a clean, organized output structure:

```
output/
├── coda-export/           # Raw Coda data (created by exporter)
│   ├── docs.json         # Master list of all documents
│   ├── {doc_id}/         # Per-document folders
│   │   ├── doc_meta.json # Document metadata
│   │   ├── tables/       # Table data and column metadata
│   │   ├── views/        # View configurations
│   │   └── pages/        # Exported page content with human-readable names
│   │       ├── pages_metadata.json  # ID-to-name mapping
│   │       ├── Marketing Strategy.md
│   │       ├── Marketing Strategy.html
│   │       ├── Project Roadmap.md
│   │       └── Project Roadmap.html
│   └── ...
├── obsidian-vault/       # Transformed vault (created by transformation agent)
│   ├── People/           # Notes from People table
│   ├── Projects/         # Notes from Projects table
│   ├── Pages/            # Converted wiki pages
│   └── ...
└── coda-export.zip       # Archive of raw data
```

## 5. Post-Export Strategy: The Task for Another Agent

Once the `output/coda-export/` directory has been successfully created, the exporter's job is complete. The next step is the **transformation** of this data into a format suitable for a specific knowledge base.

This task should be given to a separate script or an AI agent with the following instructions:

### **Prompt for Transformation Agent**

**Note:** The following prompt is a comprehensive template. Since every Coda workspace is unique, with its own conventions for table relationships and data structure, **the user will provide a final, customized prompt to the transformation agent.** This allows for a more tailored migration that respects the specific logic of their workspace.

**Goal:** Convert the structured data in the `output/coda-export/` directory into a functional Obsidian/Logseq vault in `output/obsidian-vault/`.

**Input:** The `output/coda-export/` directory generated by the Coda Workspace Exporter.

**Core Logic:**

1.  **Build a Link Map**: Your first priority is to create an in-memory dictionary that maps Coda's unique row IDs to the intended Obsidian/Logseq note titles. Iterate through all `{table_id}.json` files. For each row, use its primary display column to generate a sanitized filename and map its Coda Row ID to this new name.
2.  **Transform Table Rows into Notes**:
    * For each object in every `{table_id}.json` file, create a new `.md` note in `output/obsidian-vault/`.
    * The columns of the row should be converted into **YAML frontmatter** at the top of the note.
    * For any cell value that was a "lookup" (a `@-reference`), use your Link Map to convert the Coda Row ID into an Obsidian `[[wiki-link]]`.
3.  **Transform Pages**:
    * Process the `{page_id}.md` files from `output/coda-export/{doc_id}/pages/`.
    * Scan the content of each file for any remaining Coda-style links or references. Use the Link Map to replace these with the correct `[[wiki-links]]`.
4.  **Recreate Views**:
    * For each `{view_id}_meta.json` file, create a new `.md` note in the vault.
    * Inside this note, create a **Dataview (for Obsidian) or Advanced Query (for Logseq)** code block.
    * Analyze the `filter` and `sorts` information from the JSON file to reconstruct the query logic. For example, a Coda filter on `Status = "Done"` should become a `WHERE status = "Done"` clause in a Dataview query.
5.  **Document Formulas**:
    * For each `{table_id}_columns.json` file, create a companion note (e.g., `My Table - Formulas.md`).
    * Copy the extracted formula strings into this note under headings for each column name. This preserves the logic for manual review or future recreation.

By following this specification, the exporter will produce a perfect, self-contained dataset, and the subsequent agent will have clear, unambiguous instructions for completing the migration.
