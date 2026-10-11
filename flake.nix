{
  description = "手元の git リポジトリ群と GitHub の Issue を、自分だけが読む静的なコードブラウザにする";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-darwin" ];
      forEach = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
      codeview = pkgs: pkgs.python3Packages.buildPythonApplication {
        pname = "codeview";
        version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).project.version;
        pyproject = true;
        src = ./.;
        build-system = [ pkgs.python3Packages.setuptools ];
        dependencies = with pkgs.python3Packages; [ pygments markdown ];
        # 利用者の PATH の git・gh を優先する（gh を config dir ごとに包んでいる環境がある）
        makeWrapperArgs = [ "--suffix" "PATH" ":" (pkgs.lib.makeBinPath [ pkgs.git pkgs.gh ]) ];
        # テストは git で見本のリポを作るので、サンドボックスの外（CI と devShell）で回す
        doCheck = false;
      };
    in
    {
      packages = forEach (pkgs: { default = codeview pkgs; });

      devShells = forEach (pkgs: {
        default = pkgs.mkShell {
          packages = [
            (pkgs.python3.withPackages (ps: [ ps.pygments ps.markdown ps.pytest ]))
            pkgs.git
            pkgs.gh
          ];
          shellHook = ''export PYTHONPATH="$PWD''${PYTHONPATH:+:$PYTHONPATH}"'';
        };
      });
    };
}
