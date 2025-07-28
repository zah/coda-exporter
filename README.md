# Coda Workspace Exporter

This tool provides a comprehensive, API-driven method for exporting all data from a Coda workspace into a structured, local format. It is the first step in migrating from Coda to another platform like Obsidian or for creating a local backup of your work.

The script systematically discovers and downloads all Docs, Pages (in both HTML and Markdown), Tables, Views (including their settings), and Columns (including their formulas), preserving the relationships between them. The final output is a well-organized folder which is also compressed into a `.zip` file for easy sharing.

## 1. Setup Instructions

### Prerequisites

* Python 3.8 or newer.

* A Coda account with access to the workspace you wish to export.

### Installation (Standard Python)

This is the recommended method for most users.

1. **Clone or download this project.**

2. **Create and activate a virtual environment (recommended):**

```

python -m venv .venv
source .venv/bin/activate

# On Windows, use: .venv\\Scripts\\activate

```

3. **Install the required Python libraries:** The project includes a `requirements.txt` file. You can install the dependencies using `pip` or a faster alternative like `uv`.

```

# Using pip

pip install -r requirements.txt

# Or using the faster 'uv' tool

# uv pip install -r requirements.txt

```

4. **Create a `.env` file** in the same directory as the `coda_exporter.py` script. This file will securely store your API token. See the next section for how to get your token.

### Getting Your Coda API Token

You need to generate an API token from your Coda account to allow the script to access your data.

1. Log in to your Coda account.

2. Click on your profile picture/avatar in the top-right corner and go to **Account settings**.

3. Scroll down to the **API settings** section and click the **Generate API token** button.

4. Give your token a descriptive name (e.g., "Obsidian Migration Exporter").

5. Set the permissions. For this export script, **Read-only access to Docs, Pages, and Tables** is sufficient and recommended for safety.

6. Click **Create token**.

7. **Immediately copy the generated token.** This is the only time it will be shown.

8. Open the `.env` file you created and add the token like this:

```

CODA\_API\_TOKEN="12345678-abcd-1234-abcd-1234567890ab"

```

Replace the example token with the one you just copied.

## 2. How to Run the Exporter

Once your environment is active and your `.env` file is set up, run the exporter from your terminal:

```

python coda\_exporter.py

```

The script will create a `coda_export` directory, fetch all your data, and then create a `coda_export_archive.zip` file in the project root.

## 3. Structure of the Exported Data

The script will create a main directory named `coda_export/`. Inside, the data is organized hierarchically by document ID.

```

coda\_export/
├── docs.json                      \# A master list of all docs in the workspace.
│
└── {doc\_id\_1}/                    \# A folder for the first document.
├── doc\_meta.json              \# Metadata for this specific doc.
│
├── pages/
│   ├── {page\_id}.md           \# The content of each page, exported as Markdown.
│   └── {page\_id}.html         \# The content of each page, exported as HTML.
│
├── tables/
│   ├── {table\_id}.json        \# A JSON array of all rows from this table.
│   └── {table\_id}\_columns.json \# Metadata for each column, including formulas.
│
└── views/
└── {view\_id}\_meta.json    \# The configuration (filter, sort, etc.) for a view.

```

### File Contents Explained

* **`docs.json`**: A JSON array where each object is a summary of a document, including its name, ID, owner, etc.

* **`doc_meta.json`**: Detailed metadata for a single document.

* **`{table_id}.json`**: A JSON array where each object represents a row. The data is fetched with `valueFormat: 'rich'`, so lookups (`@-references`) will be structured objects containing the ID of the referenced row, which is essential for rebuilding links.

* **`{table_id}_columns.json`**: A JSON array of column objects. If a column is calculated, its `formula` property will contain the formula string.

* **`{view_id}_meta.json`**: A JSON object containing the view's configuration, such as its `filter` formula, `sorts` array, and the ID of its `parentTable`.

* **`{page_id}.md` / `{page_id}.html`**: The raw content of a "Doc" or wiki page in both formats. Note that any views on this page will be rendered as static tables; the dynamic logic is captured in the `views/` directory.

### Alternative Setup: Using Nix and direnv

For developers who prefer a fully reproducible environment, this project includes a `flake.nix` file.

* **Prerequisites**: [Nix](https://nixos.org/download.html) (with Flakes enabled) and [direnv](https://direnv.net/docs/installation.html).

* **Setup**: After cloning, simply run `direnv allow` in the project directory. Nix will build the environment, and it will be activated automatically whenever you `cd` into the folder. Then, proceed with creating your `.env` file as described above.

