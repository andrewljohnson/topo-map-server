# Map view notes

Tap the note icon at the top right. Opening the drawer captures the map before the keyboard opens. Write a note and choose **Copy note + bounds**, then paste it into a message.

Copied JSON includes the note, capture time, WGS84 bounds (west/south/east/north), center, zoom, bearing, pitch, viewport size in CSS pixels, the four screen corners, and dataset IDs. Longitudes preserve the visible world copy and may exceed ±180° across the date line. No screenshot or GPS reading is captured.

The snapshot stays fixed while typing or reopening the drawer. **Use current view** updates the camera while retaining the note. One draft is kept locally in browser storage, plus a document-directory file on mobile. Nothing is sent automatically.

Mobile copying uses Expo Clipboard via the WebView bridge and confirms native success. Browser copying uses the clipboard API. Failures expose selectable text for manual copying. Layout uses safe-area insets and the visual viewport for the keyboard.

Tests cover frozen snapshots, wrapped bounds, tilt/rotation, draft persistence, recapture and clipboard failure. Live MapLibre browser QA verifies the native-message contract and actual browser clipboard contents.
