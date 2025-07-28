# flake.nix
{
  description = "A development environment for the Coda to Obsidian exporter.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Python environment with common packages
        pythonEnv = pkgs.python3.withPackages (ps: [
          ps.python-dotenv
          ps.requests
          ps.pip
        ]);

      in
      {
        # The development shell that direnv will use.
        devShells.default = pkgs.mkShell {
          name = "coda-exporter-env";

          # Packages available in the shell
          packages = [
            pythonEnv
          ];

          # Environment variables can be set here if needed
          shellHook = ''
            echo "Entered Coda Exporter Nix shell."

            # Create and activate a virtual environment
            if [[ ! -d .venv ]]; then
              echo "Creating virtual environment..."
              python -m venv .venv
            fi

            source .venv/bin/activate
            echo "Virtual environment activated: $VIRTUAL_ENV"

            # Install dependencies if requirements.txt is newer than the venv
            if [[ requirements.txt -nt .venv/pyvenv.cfg ]] || [[ ! -f .venv/.requirements_installed ]]; then
              echo "Installing/updating Python dependencies..."
              pip install -r requirements.txt
              touch .venv/.requirements_installed
            fi

            if [[ -f .env ]]; then
              echo "Loading environment variables from .env"
              set -o allexport
              source .env
              set +o allexport
            fi

            echo "Python environment ready!"
          '';
        };

        # Legacy support for nix develop
        devShell = self.devShells.${system}.default;
      }
    );
}

