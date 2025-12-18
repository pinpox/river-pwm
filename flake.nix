{
  description = "River, a non-monolithic wayland compositor";

  # Nixpkgs / NixOS version to use.
  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let

      # to work with older version of flakes
      lastModifiedDate = self.lastModifiedDate or self.lastModified or "19700101";

      # Generate a user-friendly version number.
      version = builtins.substring 0 8 lastModifiedDate;

      # Helper function to generate an attrset '{ x86_64-linux = f "x86_64-linux"; ... }'.
      forAllSystems = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed;

      # Nixpkgs instantiated for supported system types.
      nixpkgsFor = forAllSystems (system: import nixpkgs { inherit system; });

    in
    {

      # Provide some binary packages for selected system types.
      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgsFor.${system};
        in
        {

          default = pkgs.stdenv.mkDerivation (finalAttrs: {
            pname = "river";
            inherit version;

            outputs = [
              "out"
              "man"
            ];

            src = pkgs.fetchFromGitHub {
              owner = "riverwm";
              repo = "river";
              rev = "673f8772479b2adf6eb1d812cb54d7623d800dc1";
              hash = "sha256-MeMjk0i773nYzDSwhKBMEpfEt+8Pqgy4Z+b+YM+c8s0=";
            };

            deps = pkgs.callPackage ./build.zig.zon.nix { };

            nativeBuildInputs = with pkgs; [
              pkg-config
              wayland-scanner
              xwayland
              zig_0_15.hook
              scdoc
            ];

            buildInputs = with pkgs; [
              libGL
              libevdev
              libinput
              libxkbcommon
              pixman
              udev
              wayland
              wayland-protocols
              wlroots_0_19
              xorg.libX11
            ];

            dontConfigure = true;

            zigBuildFlags = [
              "--system"
              "${finalAttrs.deps}"
              "-Dman-pages"
              "-Dxwayland"
            ];

            postInstall = ''
              install contrib/river.desktop -Dt $out/share/wayland-sessions
            '';

            passthru = {
              providedSessions = [ "river" ];
            };

            meta = {
              homepage = "https://isaacfreund.com/software/river/";
              description = "A non-monolithic Wayland compositor";
              longDescription = ''
                Note: This is the development version (0.4.x) with significant changes
                from the 0.3.x series. For the stable 0.3.x behavior, use river-classic.
              '';
              license = pkgs.lib.licenses.gpl3Plus;
              maintainers = with pkgs.lib.maintainers; [
                adamcstephens
                moni
                rodrgz
                pinpox
              ];
              mainProgram = "river";
              platforms = pkgs.lib.platforms.linux;
            };
          });
        }
      );
    };
}
