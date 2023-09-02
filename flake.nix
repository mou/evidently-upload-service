{
    inputs = {
        nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
        utils.url = "github:numtide/flake-utils";
    };

    outputs = {self, nixpkgs, utils}:
    let out = system:
    let pkgs = nixpkgs.legacyPackages."${system}";
    in {

        devShell = pkgs.mkShell {
            buildInputs = with pkgs; [
                poetry
            ];
        };

        defaultPackage = with pkgs.poetry2nix; mkPoetryApplication {
            projectDir = ./.;
            preferWheels = true;
        };

        defaultApp = utils.lib.mkApp {
            drv = self.defaultPackage."${system}";
        };

        dockerImage = pkgs.dockerTools.buildLayeredImage {
          name = "upload-service";
          contents = [ self.defaultPackage."${system}".dependencyEnv ];
          config = {
            WorkingDir = "/";
            Cmd = [ "/bin/gunicorn" "--bind" "0.0.0.0:8000" "upload_service.upload_service:app"];
          };
        };

    }; in with utils.lib; eachSystem defaultSystems out;

}
