# Coda API Reference for Exporter

This document provides a focused summary of Coda API endpoints relevant to the **Coda Workspace Exporter** project. It categorizes endpoints by their utility for data extraction and export purposes.

## 🎯 Critical Endpoints (Currently Used)

### Document Management
- **`GET /docs`** - List all documents in workspace
  - **Exporter Use**: Primary discovery endpoint to find all docs to export
  - **Returns**: Document IDs, names, owners, timestamps
  - **Required**: ✅ Core functionality

- **`GET /docs/{docId}`** - Get document metadata  
  - **Exporter Use**: Export complete document metadata to `doc_meta.json`
  - **Returns**: Full document details, settings, permissions info
  - **Required**: ✅ Core functionality

### Page/Section Export
- **`GET /docs/{docId}/pages`** - List all pages in document
  - **Exporter Use**: Discover all pages for content export
  - **Returns**: Page IDs, names, types, hierarchy
  - **Required**: ✅ Core functionality

- **`GET /docs/{docId}/pages/{pageIdOrName}`** - Get page metadata
  - **Exporter Use**: Extract detailed page metadata for `pages_metadata.json`
  - **Returns**: Page details, content type, creation info
  - **Required**: ✅ For complete metadata

- **`POST /docs/{docId}/pages/{pageIdOrName}/export`** - Initiate page export
  - **Exporter Use**: Start async export of page content to Markdown/HTML
  - **Returns**: Export request ID and status URL
  - **Required**: ✅ Core functionality

- **`GET /docs/{docId}/pages/{pageIdOrName}/export/{requestId}`** - Get export status
  - **Exporter Use**: Poll for completion and get download link
  - **Returns**: Export status, download URL when complete
  - **Required**: ✅ Core functionality

### Table/Database Export
- **`GET /docs/{docId}/tables`** - List all tables and views
  - **Exporter Use**: Discover all tables/views for data export
  - **Returns**: Table/view IDs, names, types, row counts
  - **Required**: ✅ Core functionality

- **`GET /docs/{docId}/tables/{tableIdOrName}`** - Get table metadata
  - **Exporter Use**: Export complete table/view configuration
  - **Returns**: Layout, filters, sorts, parent table, display column
  - **Required**: ✅ For view configurations

- **`GET /docs/{docId}/tables/{tableIdOrName}/columns`** - List table columns
  - **Exporter Use**: Get column metadata for `{table_id}_columns.json`
  - **Returns**: Column IDs, names, types, basic format info
  - **Required**: ✅ Core functionality

- **`GET /docs/{docId}/tables/{tableIdOrName}/columns/{columnIdOrName}`** - Get column details
  - **Exporter Use**: Extract complete column format information (currency, date, select options)
  - **Returns**: Detailed format config, formulas, default values
  - **Required**: ✅ For high-fidelity export

- **`GET /docs/{docId}/tables/{tableIdOrName}/rows`** - List table rows
  - **Exporter Use**: Export all row data with `valueFormat=rich` for link preservation
  - **Returns**: All row data with rich formatting for @-references
  - **Required**: ✅ Core functionality

### Authentication & Utilities
- **`GET /whoami`** - Get current user info
  - **Exporter Use**: Verify API token and log connected user
  - **Returns**: User details, workspace access
  - **Required**: ✅ For validation

## 🔍 Potentially Useful Endpoints

### Formula Discovery
- **`GET /docs/{docId}/formulas`** - List document formulas
  - **Exporter Use**: Could export standalone formulas for completeness
  - **Returns**: Formula definitions, dependencies
  - **Priority**: Medium - Additional metadata

- **`GET /docs/{docId}/formulas/{formulaIdOrName}`** - Get formula details
  - **Exporter Use**: Extract detailed formula configuration
  - **Returns**: Formula code, dependencies, usage
  - **Priority**: Medium - Enhanced completeness

### Control Elements
- **`GET /docs/{docId}/controls`** - List document controls (buttons, sliders)
  - **Exporter Use**: Export interactive element configurations
  - **Returns**: Control types, settings, formulas
  - **Priority**: Medium - Interactive elements

- **`GET /docs/{docId}/controls/{controlIdOrName}`** - Get control details
  - **Exporter Use**: Detailed control configuration
  - **Returns**: Control behavior, styling, formulas
  - **Priority**: Medium - Complete UI export

### Access Control (Enterprise)
- **`GET /docs/{docId}/acl/metadata`** - Get ACL metadata
  - **Exporter Use**: Export permission structure for enterprise workspaces
  - **Returns**: Permission model, sharing settings
  - **Priority**: Low - Enterprise-specific

- **`GET /docs/{docId}/acl/permissions`** - List document permissions
  - **Exporter Use**: Export who has access to what
  - **Returns**: User/group permissions, roles
  - **Priority**: Low - Access documentation

## ❌ Not Relevant for Export

### Modification Endpoints
- **`POST /docs`** - Create document
- **`DELETE /docs/{docId}`** - Delete document  
- **`POST /docs/{docId}/tables/{tableIdOrName}/rows`** - Create/update rows
- **`PUT /docs/{docId}/tables/{tableIdOrName}/rows/{rowIdOrName}`** - Update row
- **`DELETE /docs/{docId}/tables/{tableIdOrName}/rows/{rowIdOrName}`** - Delete row
- **`POST /docs/{docId}/tables/{tableIdOrName}/rows/{rowIdOrName}/buttons/{columnIdOrName}`** - Trigger button

### Publishing & Sharing
- **`PUT /docs/{docId}/publish`** - Publish document
- **`DELETE /docs/{docId}/publish`** - Unpublish document

### Analytics & Monitoring
- **`GET /analytics/docs`** - Document analytics
- **`GET /analytics/docs/{docId}/pages`** - Page analytics
- **`GET /analytics/docs/summary`** - Analytics summary

### Pack Management (60+ endpoints)
- All `/packs/*` endpoints - Pack development and management
- Not relevant for workspace export

### Workspace Management
- **`GET /workspaces/{workspaceId}/users`** - List workspace users
- **`PATCH /workspaces/{workspaceId}/users/role`** - Update user roles
- **`GET /workspaces/{workspaceId}/roles`** - List workspace roles

### Organizations
- **`GET /organizations/{organizationId}/goLinks`** - List Go Links
- **`POST /organizations/{organizationId}/goLinks`** - Create Go Link

### Automation
- **`POST /docs/{docId}/hooks/automation/{ruleId}`** - Trigger automation
- **`GET /mutationStatus/{requestId}`** - Get mutation status

### Domain Management
- **`GET /docs/{docId}/domains`** - List custom domains
- **`PUT /docs/{docId}/domains/{customDocDomain}`** - Set custom domain
- **`DELETE /docs/{docId}/domains/{customDocDomain}`** - Remove custom domain

## 📋 Current Implementation Status

### ✅ Fully Implemented
- Document discovery and metadata
- Page listing and export (async)
- Table/view discovery and metadata
- Column discovery with detailed formats
- Row export with rich formatting
- Authentication and validation

### 🚧 Potential Enhancements
- Formula export for standalone formulas
- Control element export
- ACL export for enterprise documentation
- Categories export for organization

### ❌ Out of Scope
- Any modification endpoints
- Analytics and monitoring
- Pack management
- Publishing and sharing
- Automation and webhooks

## 📖 Usage Notes for Exporter Maintenance

### When Adding New Features:
1. **Check this document first** to see if relevant endpoints exist
2. **Prioritize read-only endpoints** that provide additional metadata
3. **Consider enterprise vs. personal use cases** when prioritizing
4. **Test with different workspace types** (personal, team, enterprise)

### Common Patterns:
- Most endpoints support pagination with `pageToken`
- Many endpoints accept both IDs and names (e.g., `{tableIdOrName}`)
- Rich formatting is available with `valueFormat=rich` parameter
- Async operations use polling pattern (export, mutations)

### Rate Limiting:
- All endpoints respect Coda's rate limits
- Use 429 retry-after headers for backoff
- Small delays between requests help avoid limits

This reference should be updated when:
- New export requirements are identified
- Coda API adds relevant new endpoints
- Implementation priorities change
