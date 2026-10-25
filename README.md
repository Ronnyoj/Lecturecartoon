# LectureCartoon Classroom Preview (GitHub Pages)

This is a static browser preview designed for GitHub Pages. It includes a classroom scene, male/female browser speech preview, presenter choices, and a basic talking indicator while speech plays.

## Important limitations
- GitHub Pages serves static files only; it cannot run the Flask Python API or render MP4 files.
- The buttons that need `/api/...` backend endpoints (uploads, outline generation, rendering, export library) require the full Flask application on a Python host such as Render.
- Browser voice availability varies by device/browser. The voice gender selection is best-effort, not guaranteed.
- The talking indicator is an approximate preview, not exact word/phoneme-synchronized lip sync.
- This package does not remove image backgrounds with AI. It adds a clean classroom frame and soft visual blending only. Real background removal needs a segmentation model or external service.
