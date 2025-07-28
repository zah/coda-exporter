"""
Coda Workspace Exporter

A complete and high-fidelity extraction tool for Coda workspaces.
This script exports all documents, tables, views, pages, and metadata
from a Coda workspace to a structured local format.

Based on the specification in docs/PROJECT_OVERVIEW.md
"""

import os
import json
import time
import requests
import shutil
import re
import logging
from typing import Dict, List, Optional, Generator, Any
from dotenv import load_dotenv


class CodaAPIError(Exception):
    """Custom exception for Coda API errors"""
    pass


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """
    Convert a human-readable name to a safe filename.
    Preserves readability while ensuring filesystem compatibility.
    """
    # Remove or replace problematic characters
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', name)
    safe_name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_name)  # Remove control characters
    safe_name = safe_name.strip()
    safe_name = re.sub(r'\s+', '_', safe_name)  # Replace spaces with underscores
    safe_name = re.sub(r'_+', '_', safe_name)  # Collapse multiple underscores
    safe_name = safe_name.strip('_')  # Remove leading/trailing underscores

    # Ensure it's not empty and not too long
    if not safe_name:
        safe_name = "untitled"

    if len(safe_name) > max_length:
        safe_name = safe_name[:max_length].rstrip('_')

    return safe_name


def setup_logging(log_file: str = None) -> logging.Logger:
    """Setup structured logging for the exporter"""
    logger = logging.getLogger('coda_exporter')
    logger.setLevel(logging.INFO)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class CodaAPI:
    """
    Simple abstraction over the Coda API v1.
    Handles authentication, rate limiting, pagination, and error handling.
    """

    def __init__(self, api_token: str, logger: logging.Logger = None):
        self.api_token = api_token
        self.base_url = "https://coda.io/apis/v1"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.logger = logger or logging.getLogger(__name__)

    def _make_request(self, method: str, endpoint: str, max_retries: int = 3, **kwargs) -> Dict[str, Any]:
        """Make a request to the Coda API with error handling, timeouts, and retry logic"""
        url = f"{self.base_url}{endpoint}"
        
        # Set default timeout if not provided
        if 'timeout' not in kwargs:
            kwargs['timeout'] = (10, 30)  # (connect timeout, read timeout) in seconds

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff: 2^attempt seconds
                    backoff_time = 2 ** attempt
                    self.logger.info(f"Retrying {method} {endpoint} (attempt {attempt + 1}/{max_retries + 1}) after {backoff_time}s backoff")
                    time.sleep(backoff_time)
                
                self.logger.debug(f"Making {method} request to {endpoint} (attempt {attempt + 1})")
                response = requests.request(method, url, headers=self.headers, **kwargs)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue  # Retry this attempt

                response.raise_for_status()

                # Add small delay to respect rate limits
                time.sleep(0.1)

                # Handle both JSON responses and plain text (for exports)
                if response.headers.get('content-type', '').startswith('application/json'):
                    return response.json()
                else:
                    return {"content": response.text}

            except requests.exceptions.Timeout as e:
                error_msg = f"Timeout for {method} {endpoint} (attempt {attempt + 1}/{max_retries + 1}): {e}"
                self.logger.warning(error_msg)
                if attempt == max_retries:
                    self.logger.error(f"Final timeout error: {error_msg}")
                    raise CodaAPIError(f"Request timed out after {max_retries + 1} attempts: {e}")
                continue  # Retry

            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error for {method} {endpoint} (attempt {attempt + 1}/{max_retries + 1}): {e}"
                self.logger.warning(error_msg)
                if attempt == max_retries:
                    self.logger.error(f"Final connection error: {error_msg}")
                    raise CodaAPIError(f"Connection failed after {max_retries + 1} attempts: {e}")
                continue  # Retry

            except requests.exceptions.HTTPError as e:
                error_msg = f"HTTP {response.status_code} error for {method} {endpoint}"
                if response.status_code == 401:
                    error_msg += " - Invalid API token"
                elif response.status_code == 403:
                    error_msg += " - Access forbidden (check permissions)"
                elif response.status_code == 404:
                    error_msg += " - Resource not found"
                elif response.status_code >= 500:
                    error_msg += " - Server error (try again later)"
                    # Retry on server errors
                    if attempt < max_retries:
                        self.logger.warning(f"{error_msg} - Retrying...")
                        continue

                try:
                    error_detail = response.json()
                    if 'message' in error_detail:
                        error_msg += f": {error_detail['message']}"
                except:
                    pass

                self.logger.error(error_msg)
                raise CodaAPIError(error_msg)

            except requests.exceptions.RequestException as e:
                error_msg = f"Network error for {method} {endpoint} (attempt {attempt + 1}/{max_retries + 1}): {e}"
                self.logger.warning(error_msg)
                if attempt == max_retries:
                    self.logger.error(f"Final network error: {error_msg}")
                    raise CodaAPIError(f"Network error after {max_retries + 1} attempts: {e}")
                continue  # Retry

        # This should never be reached due to the logic above, but just in case
        raise CodaAPIError(f"Unexpected error: max retries exceeded for {method} {endpoint}")

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request"""
        return self._make_request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a POST request"""
        return self._make_request("POST", endpoint, json=data)

    def paginate(self, endpoint: str, params: Optional[Dict] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Handle pagination automatically and yield all items
        """
        if params is None:
            params = {}

        next_page_token = None

        while True:
            if next_page_token:
                params['pageToken'] = next_page_token

            response = self.get(endpoint, params)

            # Yield all items from this page
            items = response.get('items', [])
            for item in items:
                yield item

            # Check if there are more pages
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

            print("    Fetching next page...")

    def whoami(self) -> Dict[str, Any]:
        """Get current user info to verify token"""
        return self.get("/whoami")

    def list_docs(self, **params) -> Generator[Dict[str, Any], None, None]:
        """List all documents with pagination"""
        return self.paginate("/docs", params)

    def get_doc(self, doc_id: str) -> Dict[str, Any]:
        """Get document metadata"""
        return self.get(f"/docs/{doc_id}")

    def list_pages(self, doc_id: str) -> Generator[Dict[str, Any], None, None]:
        """List all pages in a document"""
        return self.paginate(f"/docs/{doc_id}/pages")

    def list_tables(self, doc_id: str) -> Generator[Dict[str, Any], None, None]:
        """List all tables and views in a document"""
        return self.paginate(f"/docs/{doc_id}/tables")

    def get_table(self, doc_id: str, table_id: str) -> Dict[str, Any]:
        """Get table metadata"""
        return self.get(f"/docs/{doc_id}/tables/{table_id}")

    def list_columns(self, doc_id: str, table_id: str) -> Generator[Dict[str, Any], None, None]:
        """List all columns in a table"""
        return self.paginate(f"/docs/{doc_id}/tables/{table_id}/columns")

    def get_column(self, doc_id: str, table_id: str, column_id: str) -> Dict[str, Any]:
        """Get detailed column metadata including format information"""
        return self.get(f"/docs/{doc_id}/tables/{table_id}/columns/{column_id}")

    def list_rows(self, doc_id: str, table_id: str, value_format: str = "rich") -> Generator[Dict[str, Any], None, None]:
        """List all rows in a table with rich formatting to preserve links"""
        params = {"valueFormat": value_format}
        return self.paginate(f"/docs/{doc_id}/tables/{table_id}/rows", params)

    def export_page(self, doc_id: str, page_id: str, output_format: str) -> str:
        """
        Export page content and return the final content as string.
        Handles the async nature of the export API.
        """
        # 1. Initiate export
        export_data = self.post(f"/docs/{doc_id}/pages/{page_id}/export", {
            "outputFormat": output_format
        })

        request_id = export_data['id']
        status_url = export_data['href']
        
        self.logger.debug(f"Initiated export for page {page_id}, request_id: {request_id}")
        self.logger.debug(f"Status URL: {status_url}")

        # 2. Poll for completion with improved error handling
        max_attempts = 40  # 2 minutes with 3-second intervals
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        for attempt in range(max_attempts):
            # Use the relative endpoint from the doc/page structure
            status_endpoint = f"/docs/{doc_id}/pages/{page_id}/export/{request_id}"
            
            try:
                status_data = self.get(status_endpoint)
                consecutive_failures = 0  # Reset failure count on success
                
                if status_data['status'] == 'complete':
                    download_url = status_data['downloadLink']
                    self.logger.debug(f"Export complete for page {page_id}, download URL: {download_url}")
                    break
                elif status_data['status'] == 'failed':
                    error_msg = status_data.get('error', 'Unknown error')
                    raise CodaAPIError(f"Page export failed: {error_msg}")
                    
                # Log progress every 10 attempts
                if attempt % 10 == 0 and attempt > 0:
                    self.logger.debug(f"Page export {page_id} still {status_data.get('status', 'unknown')}, attempt {attempt + 1}/{max_attempts}")
                    
            except CodaAPIError as e:
                consecutive_failures += 1
                
                if "404" in str(e) and attempt < 5:
                    # Sometimes the export isn't immediately available, wait a bit longer
                    self.logger.debug(f"Export not yet available for page {page_id}, retrying in 5 seconds...")
                    time.sleep(5)
                    continue
                elif consecutive_failures >= max_consecutive_failures:
                    raise CodaAPIError(f"Too many consecutive failures ({consecutive_failures}) polling page export {page_id}: {e}")
                else:
                    self.logger.warning(f"Polling error for page {page_id} (failure {consecutive_failures}/{max_consecutive_failures}): {e}")
                    time.sleep(5)  # Wait longer on errors
                    continue

            time.sleep(3)
        else:
            raise CodaAPIError(f"Page export timed out after {max_attempts * 3} seconds")

        # 3. Download content with timeout and retry
        max_download_retries = 3
        for download_attempt in range(max_download_retries):
            try:
                response = requests.get(download_url, timeout=(10, 60))  # 60s for large downloads
                response.raise_for_status()
                return response.text
            except requests.exceptions.Timeout as e:
                if download_attempt < max_download_retries - 1:
                    self.logger.warning(f"Download timeout for page {page_id}, retrying...")
                    time.sleep(2 ** download_attempt)  # Exponential backoff
                    continue
                else:
                    raise CodaAPIError(f"Download timed out after {max_download_retries} attempts: {e}")
            except requests.exceptions.RequestException as e:
                if download_attempt < max_download_retries - 1:
                    self.logger.warning(f"Download error for page {page_id}, retrying...")
                    time.sleep(2 ** download_attempt)
                    continue
                else:
                    raise CodaAPIError(f"Download failed after {max_download_retries} attempts: {e}")


class CodaExporter:
    """
    Main exporter class that orchestrates the complete export process
    according to the specification in PROJECT_OVERVIEW.md
    """

    def __init__(self, api_token: str, output_dir: str = "output", silent_mode: bool = False, logger: logging.Logger = None):
        self.logger = logger or logging.getLogger(__name__)
        self.api = CodaAPI(api_token, self.logger)
        self.output_dir = output_dir
        self.export_dir = os.path.join(output_dir, "coda-export")  # Coda export subdirectory
        self.export_formats = ["markdown", "html"]  # Configurable page export formats
        self.silent_mode = silent_mode

    def _print(self, message: str, force: bool = False):
        """Print message only if not in silent mode, or if forced (for errors)"""
        if not self.silent_mode or force:
            print(message)

    def setup_export_directory(self):
        """Prepare clean export directory structure"""
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Clean up previous coda export if it exists
        if os.path.exists(self.export_dir):
            self._print(f"Removing previous coda export: {self.export_dir}")
            shutil.rmtree(self.export_dir)

        os.makedirs(self.export_dir, exist_ok=True)
        if not self.silent_mode:
            self._print(f"Created export directory structure:")
            self._print(f"  📁 {self.output_dir}/")
            self._print(f"    📁 coda-export/  ← Coda data will be stored here")
            self._print(f"    📁 obsidian-vault/  ← Future transformation output")

    def verify_connection(self):
        """Verify API token works"""
        try:
            user_info = self.api.whoami()
            user_name = user_info.get('name', 'Unknown')
            self.logger.info(f"Connected to Coda API as: {user_name}")
            self._print(f"Successfully connected to Coda API as: {user_name}")
            return True
        except CodaAPIError as e:
            self.logger.error(f"Coda API connection failed: {e}")
            print(f"❌ Error connecting to Coda API: {e}")  # Always show errors
            return False
        except Exception as e:
            self.logger.exception("Unexpected error during API connection verification")
            print(f"❌ Unexpected error connecting to Coda API: {e}")  # Always show errors
            return False

    def export_workspace_structure(self) -> List[Dict[str, Any]]:
        """
        Export the master list of all documents in the workspace.
        Saves to docs.json in the root export directory.
        """
        self._print("\n=== 1. EXPORTING WORKSPACE STRUCTURE ===")
        self.logger.info("Starting workspace structure export")

        docs_list = []
        doc_count = 0

        try:
            for doc in self.api.list_docs():
                doc_summary = {
                    "id": doc["id"],
                    "name": doc["name"],
                    "owner": doc.get("owner"),
                    "ownerName": doc.get("ownerName"),
                    "createdAt": doc.get("createdAt"),
                    "updatedAt": doc.get("updatedAt"),
                    "href": doc.get("href"),
                    "browserLink": doc.get("browserLink")
                }
                docs_list.append(doc_summary)
                doc_count += 1
                self.logger.debug(f"Found document: {doc['name']} ({doc['id']})")
                if not self.silent_mode:
                    self._print(f"  Discovered doc #{doc_count}: {doc['name']} ({doc['id']})")

        except CodaAPIError as e:
            error_msg = f"API error while fetching documents: {e}"
            self.logger.error(error_msg)
            print(f"❌ {error_msg}")  # Always show errors
            return []
        except Exception as e:
            error_msg = f"Unexpected error fetching documents: {e}"
            self.logger.exception(error_msg)
            print(f"❌ {error_msg}")  # Always show errors
            return []

        # Save master docs list
        docs_file = os.path.join(self.export_dir, "docs.json")
        try:
            with open(docs_file, "w", encoding="utf-8") as f:
                json.dump(docs_list, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Saved metadata for {len(docs_list)} documents")
            self._print(f"✓ Saved metadata for {len(docs_list)} documents to docs.json")
        except Exception as e:
            error_msg = f"Error saving docs.json: {e}"
            self.logger.error(error_msg)
            print(f"❌ {error_msg}")  # Always show errors

        return docs_list

    def export_document(self, doc_id: str):
        """
        Export all data for a single document according to the specification:
        - Document metadata (doc_meta.json)
        - All tables with full row data and column metadata
        - All views with their configuration (metadata only)
        - All pages exported in configured formats
        """
        self._print(f"\n=== 2. EXPORTING DOCUMENT: {doc_id} ===")

        # Create document directory structure
        doc_dir = os.path.join(self.export_dir, doc_id)
        tables_dir = os.path.join(doc_dir, "tables")
        views_dir = os.path.join(doc_dir, "views")
        pages_dir = os.path.join(doc_dir, "pages")

        os.makedirs(tables_dir, exist_ok=True)
        os.makedirs(views_dir, exist_ok=True)
        os.makedirs(pages_dir, exist_ok=True)

        try:
            # Export document metadata
            doc_meta = self.api.get_doc(doc_id)
            doc_meta_file = os.path.join(doc_dir, "doc_meta.json")
            with open(doc_meta_file, "w", encoding="utf-8") as f:
                json.dump(doc_meta, f, indent=2, ensure_ascii=False)
            self._print(f"  ✓ Saved document metadata: {doc_meta.get('name', 'Unknown')}")

            # Process all tables and views
            self._export_tables_and_views(doc_id, tables_dir, views_dir)

            # Process all pages
            self._export_pages(doc_id, pages_dir)

        except Exception as e:
            print(f"  ✗ ERROR processing document {doc_id}: {e}")  # Always show errors
            # Stop on first error for debugging
            raise Exception(f"STOPPING ON FIRST ERROR: Error processing document {doc_id}: {e}") from e

    def _export_tables_and_views(self, doc_id: str, tables_dir: str, views_dir: str):
        """Export all tables and views for a document"""
        self._print("  --- Tables and Views ---")

        try:
            for item in self.api.list_tables(doc_id):
                item_type = item.get("type", "table")
                item_name = item.get("name", "Unknown")
                item_id = item["id"]

                if item_type == "view":
                    self._export_view(doc_id, item, views_dir)
                else:
                    self._export_table(doc_id, item, tables_dir)

        except Exception as e:
            print(f"    ✗ Error listing tables/views: {e}")  # Always show errors

    def _export_table(self, doc_id: str, table_info: Dict, tables_dir: str):
        """Export a single table with full row data and column metadata"""
        table_id = table_info["id"]
        table_name = table_info.get("name", "Unknown")

        self._print(f"    📋 Table: {table_name} ({table_id})")
        self.logger.info(f"Exporting table: {table_name} ({table_id})")

        try:
            # Export comprehensive table metadata first (following spec completeness requirement)
            enhanced_table_meta = {
                **table_info,  # Base metadata from list_tables
                "export_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "export_note": "Enhanced with complete metadata per PROJECT_OVERVIEW spec"
            }

            # Get additional detailed table metadata if it's a real table (not a view)
            if table_info.get("type") == "table":
                try:
                    detailed_table = self.api.get_table(doc_id, table_id)
                    enhanced_table_meta.update({
                        "detailed_metadata": detailed_table,
                        "rowCount": detailed_table.get("rowCount"),
                        "displayColumn": detailed_table.get("displayColumn"),
                        "tableType": detailed_table.get("tableType"),
                        "filter": detailed_table.get("filter"),
                        "sorts": detailed_table.get("sorts", [])
                    })
                except Exception as e:
                    self.logger.warning(f"Could not get detailed table metadata for {table_id}: {e}")

            table_meta_file = os.path.join(tables_dir, f"{table_id}_meta.json")
            with open(table_meta_file, "w", encoding="utf-8") as f:
                json.dump(enhanced_table_meta, f, indent=2, ensure_ascii=False)

            # Export enhanced column metadata (including complete format information per spec)
            columns = list(self.api.list_columns(doc_id, table_id))

            # Enhance columns with detailed format information
            enhanced_columns = []
            for column in columns:
                try:
                    # Get detailed column info including complete format details
                    detailed_column = self.api.get_column(doc_id, table_id, column["id"])
                    enhanced_column = {
                        **column,  # Base column info
                        "detailed_format": detailed_column.get("format"),  # Complete ColumnFormat object
                        "calculated": detailed_column.get("calculated"),
                        "formula": detailed_column.get("formula"),
                        "defaultValue": detailed_column.get("defaultValue"),
                        "display": detailed_column.get("display"),
                        "full_column_details": detailed_column  # Complete API response
                    }
                    enhanced_columns.append(enhanced_column)
                    self.logger.debug(f"Enhanced column {column.get('name')} with format type: {detailed_column.get('format', {}).get('type')}")
                except Exception as e:
                    # Fall back to basic column info if detailed fetch fails
                    self.logger.warning(f"Could not get detailed format for column {column.get('name')}: {e}")
                    enhanced_columns.append(column)

            columns_file = os.path.join(tables_dir, f"{table_id}_columns.json")
            with open(columns_file, "w", encoding="utf-8") as f:
                json.dump(enhanced_columns, f, indent=2, ensure_ascii=False)

            # Export all row data with rich formatting
            rows = list(self.api.list_rows(doc_id, table_id, value_format="rich"))
            rows_file = os.path.join(tables_dir, f"{table_id}.json")
            with open(rows_file, "w", encoding="utf-8") as f:
                json.dump(rows, f, indent=2, ensure_ascii=False)

            self._print(f"      ✓ Saved {len(enhanced_columns)} columns (with detailed formats) and {len(rows)} rows")
            self.logger.info(f"Table {table_name}: {len(enhanced_columns)} columns, {len(rows)} rows")

        except Exception as e:
            error_msg = f"Error exporting table {table_name}: {e}"
            print(f"      ✗ {error_msg}")  # Always show errors
            self.logger.error(error_msg)

    def _export_view(self, doc_id: str, view_info: Dict, views_dir: str):
        """Export view metadata (configuration only, not data)"""
        view_id = view_info["id"]
        view_name = view_info.get("name", "Unknown")

        self._print(f"    🔍 View: {view_name} ({view_id})")
        self.logger.info(f"Exporting view: {view_name} ({view_id})")

        try:
            # Get detailed view configuration
            view_details = self.api.get_table(doc_id, view_id)

            # Extract ALL relevant metadata for transformation (following spec)
            view_meta = {
                "id": view_details["id"],
                "name": view_details["name"],
                "type": view_details.get("type"),
                "tableType": view_details.get("tableType"),
                "layout": view_details.get("layout"),
                "parentTable": view_details.get("parentTable"),
                "displayColumn": view_details.get("displayColumn"),
                "filter": view_details.get("filter"),  # Complete FormulaDetail object
                "sorts": view_details.get("sorts", []),
                "rowCount": view_details.get("rowCount"),
                "viewId": view_details.get("viewId"),
                "createdAt": view_details.get("createdAt"),
                "updatedAt": view_details.get("updatedAt"),
                "browserLink": view_details.get("browserLink"),
                "href": view_details.get("href"),
                "original_view_data": view_details  # Complete API response
            }

            view_meta_file = os.path.join(views_dir, f"{view_id}_meta.json")
            with open(view_meta_file, "w", encoding="utf-8") as f:
                json.dump(view_meta, f, indent=2, ensure_ascii=False)

            self._print(f"      ✓ Saved view configuration")
            self.logger.info(f"View {view_name}: layout={view_meta.get('layout')}, rows={view_meta.get('rowCount')}")

        except Exception as e:
            error_msg = f"Error exporting view {view_name}: {e}"
            print(f"      ✗ {error_msg}")  # Always show errors
            self.logger.error(error_msg)

    def _export_pages(self, doc_id: str, pages_dir: str):
        """Export all pages in the configured formats with human-readable filenames"""
        self._print("  --- Pages ---")

        pages_metadata = []

        try:
            for page in self.api.list_pages(doc_id):
                page_id = page["id"]
                page_name = page.get("name", "Unknown")

                self.logger.info(f"Exporting page: {page_name} ({page_id})")
                self._print(f"    📄 Page: {page_name} ({page_id})")

                # Create safe filename from page name
                safe_filename = sanitize_filename(page_name)

                # Store comprehensive page metadata for downstream use
                page_meta = {
                    "id": page_id,
                    "name": page_name,
                    "safe_filename": safe_filename,
                    "subtitle": page.get("subtitle"),
                    "iconName": page.get("iconName"),
                    "image": page.get("image"),
                    "contentType": page.get("contentType"),
                    "createdAt": page.get("createdAt"),
                    "updatedAt": page.get("updatedAt"),
                    "browserLink": page.get("browserLink"),
                    "href": page.get("href"),
                    "original_page_data": page  # Full API response for completeness
                }
                pages_metadata.append(page_meta)

                # Export page in all configured formats
                for export_format in self.export_formats:
                    try:
                        # Check if page is exportable (only canvas pages can be exported)
                        content_type = page.get("contentType", "")
                        if content_type != "canvas":
                            if not self.silent_mode:
                                self._print(f"      Skipping {export_format} (page type '{content_type}' not exportable)")
                            self.logger.debug(f"Skipping page {page_id} export - content type '{content_type}' not supported")
                            continue

                        if not self.silent_mode:
                            self._print(f"      Exporting as {export_format}...")
                        self.logger.debug(f"Exporting page {page_id} as {export_format}")

                        content = self.api.export_page(doc_id, page_id, export_format)

                        file_extension = "md" if export_format == "markdown" else "html"

                        # Use human-readable filename (updated approach per spec)
                        filename = f"{safe_filename}.{file_extension}"
                        output_file = os.path.join(pages_dir, filename)

                        with open(output_file, "w", encoding="utf-8") as f:
                            f.write(content)

                        # Update metadata to include filename
                        page_meta[f"{export_format}_filename"] = filename

                        if not self.silent_mode:
                            self._print(f"        ✓ Saved {export_format} content as {filename}")
                        self.logger.info(f"Saved page content: {filename} (id: {page_id})")

                    except Exception as e:
                        error_msg = f"Error exporting {export_format} for page {page_name}: {e}"
                        print(f"        ✗ {error_msg}")  # Always show errors
                        self.logger.error(error_msg)
                        # Stop on first error for debugging
                        raise Exception(f"STOPPING ON FIRST ERROR: {error_msg}") from e

            # Save pages metadata for downstream use
            pages_meta_file = os.path.join(pages_dir, "pages_metadata.json")
            with open(pages_meta_file, "w", encoding="utf-8") as f:
                json.dump(pages_metadata, f, indent=2, ensure_ascii=False)

            self._print(f"      ✓ Saved pages metadata ({len(pages_metadata)} pages)")
            self.logger.info(f"Saved metadata for {len(pages_metadata)} pages")

        except Exception as e:
            error_msg = f"Error listing pages for doc {doc_id}: {e}"
            print(f"    ✗ {error_msg}")  # Always show errors
            self.logger.error(error_msg)
            # Stop on first error for debugging
            raise Exception(f"STOPPING ON FIRST ERROR: {error_msg}") from e

    def create_archive(self):
        """Create a zip archive of the coda export"""
        self._print("\n=== 3. CREATING ARCHIVE ===")

        try:
            # Create archive in the output directory
            archive_path = os.path.join(self.output_dir, "coda-export")
            shutil.make_archive(archive_path, 'zip', self.export_dir)
            self._print(f"✓ Created {archive_path}.zip")
        except Exception as e:
            print(f"✗ Could not create zip archive: {e}")  # Always show errors

    def run_export(self):
        """Run the complete export process"""
        self._print("🚀 Starting Coda Workspace Export", force=True)
        self._print("=" * 50, force=True)

        # Setup
        self.setup_export_directory()

        if not self.verify_connection():
            return False

        # Export workspace structure
        docs_list = self.export_workspace_structure()
        if not docs_list:
            print("❌ No documents found. Export cancelled.")  # Always show errors
            return False

        # Export each document
        for doc_info in docs_list:
            self.export_document(doc_info["id"])
            time.sleep(1)  # Small delay between documents

        # Create archive
        self.create_archive()

        self._print("\n" + "=" * 50, force=True)
        self._print("🎉 EXPORT COMPLETE!", force=True)
        self._print(f"📁 Output directory: {self.output_dir}/", force=True)
        self._print(f"📁 Coda data: {self.export_dir}/", force=True)
        self._print(f"📦 Archive: {self.output_dir}/coda-export.zip", force=True)
        if not self.silent_mode:
            self._print("\nNext step: Use a transformation agent to convert this data")
            self._print("to your target knowledge base format (see PROJECT_OVERVIEW.md)")
            self._print(f"The transformation output should go to: {self.output_dir}/obsidian-vault/")

        return True


def main():
    """Main entry point"""
    # Load configuration
    load_dotenv()
    api_token = os.getenv("CODA_API_TOKEN")
    output_dir = os.getenv("OUTPUT_DIR", "output")  # Default to "output"
    silent_mode = os.getenv("SILENT_MODE", "true").lower() in ("true", "1", "yes")  # Default to silent

    if not api_token or api_token == "YOUR_API_TOKEN_HERE":
        print("❌ Error: CODA_API_TOKEN not found or not set.")
        print("Please create a .env file with your Coda API token:")
        print("CODA_API_TOKEN=your_token_here")
        return

    # Set up logging
    log_file = os.path.join(output_dir, "coda-export.log")
    os.makedirs(output_dir, exist_ok=True)
    logger = setup_logging(log_file)

    logger.info("Starting Coda workspace export")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Silent mode: {silent_mode}")

    try:
        # Run export
        exporter = CodaExporter(api_token, output_dir, silent_mode=silent_mode, logger=logger)
        success = exporter.run_export()

        if success:
            logger.info("Export completed successfully")
        else:
            logger.error("Export failed")
            print("❌ Export failed. Please check the errors above and the log file.")
            exit(1)

    except Exception as e:
        logger.exception("Unexpected error during export")
        print(f"❌ Unexpected error: {e}")
        print(f"📋 Full details in log file: {log_file}")
        exit(1)


if __name__ == "__main__":
    main()

