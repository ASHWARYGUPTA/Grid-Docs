#!/bin/bash
# Helper script to copy screenshots from agent session to Next.js public directory
BRAIN_DIR="/home/ash/.gemini/antigravity/brain/3cfb74c0-af0c-49ea-9634-0daef902882b"
PUBLIC_DIR="frontend/public"

mkdir -p "$PUBLIC_DIR"

echo "Copying captured screenshots from agent session..."

cp "$BRAIN_DIR/live_monitor_1782195932983.png" "$PUBLIC_DIR/live_monitor.png"
cp "$BRAIN_DIR/live_monitor_transit_1782195949358.png" "$PUBLIC_DIR/live_monitor_transit.png"
cp "$BRAIN_DIR/close_learn_dialog_1782196134745.png" "$PUBLIC_DIR/close_learn_dialog.png"
cp "$BRAIN_DIR/planned_events_wizard_1782196221281.png" "$PUBLIC_DIR/planned_events_wizard.png"
cp "$BRAIN_DIR/hotspots_analytics_1782196261837.png" "$PUBLIC_DIR/hotspots_analytics.png"
cp "$BRAIN_DIR/governance_console_1782196280933.png" "$PUBLIC_DIR/governance_console.png"
cp "$BRAIN_DIR/citizen_reporting_1782196295350.png" "$PUBLIC_DIR/citizen_reporting.png"

echo "Copy complete!"
echo "Note: For the 'hotspots_analytics_detail.png' image (which you uploaded directly), please save it to '$PUBLIC_DIR/hotspots_analytics_detail.png'."
