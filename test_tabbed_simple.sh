# Simple test script for tabbed layout

echo "=== Tabbed Layout Test ==="
echo ""
echo "This script will:"
echo "1. Start pwm in nested River"
echo "2. Monitor for TabDecoration errors"
echo "3. Show instructions for manual testing"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run pwm and grep for tab-related output
nix run . -- --border-width 3 2>&1 | tee /tmp/pwm-test.log | grep --line-buffered -i "tab\|error\|exception" &
PID=$!

# Wait a bit for startup
sleep 3

echo ""
echo "=== Manual Testing Instructions ==="
echo ""
echo "1. Switch to tabbed layout:"
echo "   Press: Alt+Space (multiple times until you see 'tabbed' in status)"
echo ""
echo "2. Open some windows:"
echo "   Press: Alt+Return (3-4 times to open terminals)"
echo ""
echo "3. Test tab navigation:"
echo "   Press: Alt+Tab (cycle forward through tabs)"
echo "   Press: Alt+Shift+Tab (cycle backward)"
echo ""
echo "4. Expected behavior:"
echo "   - Tab bar appears at top"
echo "   - Only focused window is visible"
echo "   - Tab titles show window names"
echo "   - Focused tab has different background color"
echo ""
echo "5. Check for errors:"
echo "   - No 'TabDecoration: Error' messages should appear"
echo "   - Tab bar should render smoothly"
echo ""
echo "Press Ctrl+C when done testing"
echo ""

# Wait for user to finish
wait $PID

echo ""
echo "=== Test Log Saved ==="
echo "Full log: /tmp/pwm-test.log"
echo ""
