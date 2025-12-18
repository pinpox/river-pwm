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

          # Nested version that runs in a window
          river-pywm-nested =
            let
              pywm-nested = pkgs.python3Packages.buildPythonApplication {
                pname = "pywm-nested";
                version = "0.1.0";
                format = "other";

                src = ./pywm;

                installPhase = ''
                  mkdir -p $out/bin
                  mkdir -p $out/${pkgs.python3.sitePackages}/pywm
                  cp -r * $out/${pkgs.python3.sitePackages}/pywm/

                  cat > $out/bin/pywm-nested <<EOF
                  #!${pkgs.python3}/bin/python3
                  import sys
                  import subprocess
                  import os
                  import threading
                  import time
                  sys.path.insert(0, "$out/${pkgs.python3.sitePackages}")
                  from pywm.riverwm import RiverWM, RiverConfig
                  from pywm.protocol import Modifiers

                  print("[pywm-nested] Starting pywm in nested mode")
                  print(f"[pywm-nested] WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY')}")
                  print(f"[pywm-nested] Terminal path: ${pkgs.foot}/bin/foot")

                  # Use Alt (MOD1) instead of Super (MOD4) for nested mode
                  config = RiverConfig(mod=Modifiers.MOD1)
                  print(f"[pywm-nested] Config created with mod={config.mod}")

                  # Hook the manager callbacks BEFORE creating RiverWM
                  # (RiverWM.__init__ calls _setup_callbacks which assigns these)
                  class TerminalSpawner:
                      def __init__(self):
                          self.spawned = False
                          self.original_on_seat_created = None

                      def on_seat_with_terminal(self, seat):
                          print(f"[pywm-nested] Seat created: {seat}", flush=True)
                          if self.original_on_seat_created:
                              self.original_on_seat_created(seat)
                          if not self.spawned:
                              self.spawned = True
                              print("[pywm-nested] Spawning terminal...", flush=True)
                              try:
                                  result = subprocess.Popen(
                                      ["${pkgs.foot}/bin/foot"],
                                      start_new_session=True
                                  )
                                  print(f"[pywm-nested] Terminal spawned with PID: {result.pid}", flush=True)
                              except Exception as e:
                                  print(f"[pywm-nested] ERROR spawning terminal: {e}", flush=True)
                                  import traceback
                                  traceback.print_exc()

                  spawner = TerminalSpawner()

                  # Create custom RiverWM that overrides _setup_callbacks
                  class RiverWMNested(RiverWM):
                      def _setup_callbacks(self):
                          super()._setup_callbacks()
                          # Now wrap the callbacks
                          spawner.original_on_seat_created = self.manager.on_seat_created
                          self.manager.on_seat_created = lambda seat: spawner.on_seat_with_terminal(seat)

                  wm = RiverWMNested(config)
                  print("[pywm-nested] RiverWM instance created")

                  # Hook _dispatch_wm_event to see if events are arriving
                  original_dispatch_wm_event = wm.manager._dispatch_wm_event
                  def dispatch_wm_event_logged(msg):
                      print(f"[pywm-nested] Received WM event! object_id={msg.object_id}, opcode={msg.opcode}", flush=True)
                      return original_dispatch_wm_event(msg)
                  wm.manager._dispatch_wm_event = dispatch_wm_event_logged

                  # Add connection logging
                  original_connect = wm.manager.connect
                  def connect_logged(*args, **kwargs):
                      print("[pywm-nested] Attempting to connect to River...", flush=True)
                      result = original_connect(*args, **kwargs)
                      print(f"[pywm-nested] Connect result: {result}", flush=True)
                      if result:
                          print(f"[pywm-nested] Connection successful!", flush=True)
                          print(f"[pywm-nested] wm_id={wm.manager.wm_id}", flush=True)
                          print(f"[pywm-nested] xkb_bindings_id={wm.manager.xkb_bindings_id}", flush=True)
                          print(f"[pywm-nested] layer_shell_id={wm.manager.layer_shell_id}", flush=True)
                          print(f"[pywm-nested] unavailable={wm.manager.unavailable}", flush=True)
                          print(f"[pywm-nested] running={wm.manager.running}", flush=True)
                      else:
                          print(f"[pywm-nested] Connection FAILED!", flush=True)
                      return result
                  wm.manager.connect = connect_logged

                  # Hook the run loop to see if it's actually running
                  original_run = wm.manager.run
                  def run_logged():
                      print("[pywm-nested] Entering event loop...")
                      loop_count = 0
                      original_run_once = wm.manager.connection.run_once
                      def run_once_logged(*args, **kwargs):
                          nonlocal loop_count
                          loop_count += 1
                          if loop_count <= 10 or loop_count % 100 == 0:
                              print(f"[pywm-nested] Event loop iteration {loop_count}, running={wm.manager.running}", flush=True)
                          result = original_run_once(*args, **kwargs)
                          if not result:
                              print(f"[pywm-nested] run_once returned False at iteration {loop_count}!", flush=True)
                              print(f"[pywm-nested] Socket valid: {wm.manager.connection.socket is not None}", flush=True)
                          return result
                      wm.manager.connection.run_once = run_once_logged
                      return original_run()
                  wm.manager.run = run_logged

                  print("[pywm-nested] Calling wm.run()...")
                  try:
                      exit_code = wm.run()
                      print(f"[pywm-nested] wm.run() returned with code {exit_code}")
                  except Exception as e:
                      print(f"[pywm-nested] EXCEPTION in wm.run(): {e}")
                      import traceback
                      traceback.print_exc()
                      exit_code = 1
                  print(f"[pywm-nested] Exiting with code {exit_code}")
                  sys.exit(exit_code)
                  EOF
                  chmod +x $out/bin/pywm-nested
                '';
              };
            in
            pkgs.writeShellScriptBin "river-pywm-nested" ''
              set -e

              # Check if we're already in a Wayland or X11 session
              if [ -z "$WAYLAND_DISPLAY" ] && [ -z "$DISPLAY" ]; then
                echo "Error: Not running in a graphical session"
                echo "Please run this from within Wayland or X11"
                exit 1
              fi

              echo "Starting River compositor in nested mode..."
              echo "Note: Using Alt as modifier key to avoid conflicts with host compositor"
              echo ""
              echo "Key bindings:"
              echo "  Alt + Return      - Open terminal"
              echo "  Alt + D           - Open launcher"
              echo "  Alt + Q           - Close window"
              echo "  Alt + Shift + Q   - Quit"
              echo ""

              # Use cage to create a windowed environment for River
              # This ensures River runs in a visible window
              if command -v ${pkgs.cage}/bin/cage &> /dev/null; then
                echo "Using cage to create windowed environment..."
                ${pkgs.cage}/bin/cage -d -- ${self.packages.${system}.river}/bin/river -c "${pywm-nested}/bin/pywm-nested"
              else
                # Fallback: River will auto-detect nested mode if WAYLAND_DISPLAY or DISPLAY is set
                ${self.packages.${system}.river}/bin/river -c "${pywm-nested}/bin/pywm-nested"
              fi
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
