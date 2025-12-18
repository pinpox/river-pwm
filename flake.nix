{
  description = "River, a non-monolithic wayland compositor";

  # Nixpkgs / NixOS version to use.
  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";
  inputs.river-src.url = "github:riverwm/river";
  inputs.river-src.flake = false;

  outputs =
    {
      self,
      nixpkgs,
      river-src,
    }:
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

          # Python library package
          pwm-lib = pkgs.python3Packages.buildPythonPackage {
            pname = "pwm";
            version = "0.1.0";
            src = ./.;

            format = "setuptools";

            meta = {
              description = "Python library for River window management protocol";
              license = pkgs.lib.licenses.isc;
              maintainers = with pkgs.lib.maintainers; [ pinpox ];
            };
          };

          # Executable with example configuration
          pwm = pkgs.writers.writePython3Bin "pwm" {
            libraries = [ self.packages.${system}.pwm-lib ];
            flakeIgnore = [
              "E265"
              "E501"
            ];
          } (builtins.readFile ./pwm.py);

          river = pkgs.stdenv.mkDerivation (finalAttrs: {
            pname = "river";
            inherit version;

            outputs = [
              "out"
              "man"
            ];

            src = river-src;

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

          river-pwm = pkgs.writeShellScriptBin "river-pwm" ''
            set -e

            # Detect if running in nested mode (inside another compositor)
            if [ -n "$WAYLAND_DISPLAY" ] || [ -n "$DISPLAY" ]; then
              echo "Starting River compositor in nested mode..."
              echo "Key bindings: Alt + Return (terminal), Alt + Q (close), Alt + Shift + Q (quit)"
              echo ""

              # River auto-detects nested mode and runs in a window
              exec ${self.packages.${system}.river}/bin/river -c "${self.packages.${system}.pwm}/bin/pwm"
            else
              # Running on bare metal - start River in background then pwm
              echo "Starting River compositor..."
              ${self.packages.${system}.river}/bin/river -c "exit 0" &
              RIVER_PID=$!

              # Wait for River to be ready by checking for the Wayland socket
              echo "Waiting for River to initialize..."
              for i in {1..30}; do
                if [ -n "$WAYLAND_DISPLAY" ] && [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
                  echo "River is ready (display: $WAYLAND_DISPLAY)"
                  break
                fi
                sleep 0.5
              done

              # Start pwm window manager
              echo "Starting pwm window manager..."
              ${self.packages.${system}.pwm}/bin/pwm
              EXIT_CODE=$?

              # When pwm exits, kill River
              echo "Shutting down River compositor..."
              kill $RIVER_PID 2>/dev/null || true
              wait $RIVER_PID 2>/dev/null || true

              exit $EXIT_CODE
            fi
          '';

          default = self.packages.${system}.river-pwm;
        }
      );
    };
}
