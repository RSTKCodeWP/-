#!/bin/bash
# Close any Chrome window/tab holding a Betaflight Configurator session.
#
# Surgical: only touches windows whose title contains "Betaflight" or
# "BLHeli" or "Configurator". Other Chrome work is untouched.
#
# Returns 0 on success (whether or not a window was closed), 1 if the
# osascript itself failed.
#
# Used as a pre-flight by /bfflash, /betafleetcheck, /satest when lsof shows
# Chrome holds /dev/cu.usbmodem* — automated equivalent of the operator
# clicking Disconnect in Configurator.

set -u

# Quiet mode by default; pass -v for chatty.
VERBOSE=0
while getopts "v" opt; do
  case $opt in
    v) VERBOSE=1 ;;
  esac
done

log() { [[ $VERBOSE -eq 1 ]] && echo "[close_bf_configurator] $*" >&2; }

osascript <<'OSA' 2>/dev/null
on titleMatches(t)
  if t contains "Betaflight" then return true
  if t contains "BLHeli" then return true
  if t contains "Configurator" then return true
  return false
end titleMatches

set closedCount to 0
tell application "System Events"
  set chromeApps to (every process whose name contains "Chrome")
end tell

tell application "Google Chrome"
  if not (it is running) then return 0
  set winList to every window
  repeat with w in winList
    try
      set tabList to every tab of w
      repeat with t in tabList
        try
          set tt to (title of t)
          if my titleMatches(tt) then
            close t
            set closedCount to closedCount + 1
          end if
        end try
      end repeat
    end try
  end repeat
end tell

return closedCount
OSA

rc=$?
log "exit $rc"
exit $rc
