{
  description = "River, a non-monolithic wayland compositor";

  # Nixpkgs / NixOS version to use.
  inputs.nixpkgs.url = "nixpkgs/nixos-unstable";
  inputs.river-src.url = "github:riverwm/river";
  inputs.river-src.flake = false;

  outputs =
    { self, nixpkgs, river-src }:
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

          pywm = pkgs.python3Packages.buildPythonApplication {
            pname = "pywm";
            version = "0.1.0";

            src = ./pywm;

            format = "other";

            installPhase = ''
              mkdir -p $out/${pkgs.python3.sitePackages}/pywm
              cp -r * $out/${pkgs.python3.sitePackages}/pywm/

              mkdir -p $out/bin
              cat > $out/bin/pywm <<EOF
              #!${pkgs.python3}/bin/python3
              import sys
              from pywm.riverwm import main
              sys.exit(main())
              EOF
              chmod +x $out/bin/pywm
            '';

            meta = {
              description = "Python window manager for River Wayland compositor";
              license = pkgs.lib.licenses.isc;
              maintainers = with pkgs.lib.maintainers; [ pinpox ];
              mainProgram = "pywm";
              platforms = pkgs.lib.platforms.linux;
            };
          };

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

          river-pywm = pkgs.writeShellScriptBin "river-pywm" ''
            set -e

            # Start River compositor with custom init script in the background
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

            # Start pywm window manager
            echo "Starting pywm window manager..."
            ${self.packages.${system}.pywm}/bin/pywm
            EXIT_CODE=$?

            # When pywm exits, kill River
            echo "Shutting down River compositor..."
            kill $RIVER_PID 2>/dev/null || true
            wait $RIVER_PID 2>/dev/null || true

            exit $EXIT_CODE
          '';

          # Nested version that runs in a window for testing
          river-pywm-nested = pkgs.writeShellScriptBin "river-pywm-nested" ''
            set -e

            # Check if we're already in a Wayland or X11 session
            if [ -z "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
              echo "Error: Not running in a graphical session"
              echo "Please run this from within Wayland or X11"
              exit 1
            fi

            echo "Starting River compositor in nested mode..."
            echo "Key bindings: Alt + Return (terminal), Alt + Q (close), Alt + Shift + Q (quit)"
            echo ""

            # Use cage to create a windowed environment for River
            ${pkgs.cage}/bin/cage -d -- ${self.packages.${system}.river}/bin/river -c "${self.packages.${system}.pywm}/bin/pywm"
          '';

          default = self.packages.${system}.river;
        }
      );

      # Apps for nix run
      apps = forAllSystems (system: {
        river-pywm = {
          type = "app";
          program = "${self.packages.${system}.river-pywm}/bin/river-pywm";
        };
        nested = {
          type = "app";
          program = "${self.packages.${system}.river-pywm-nested}/bin/river-pywm-nested";
        };
        default = self.apps.${system}.nested;
      });
    };
}
