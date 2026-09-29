# Frontend UI refresh — 2026-09-28

Applied the supplied AssureX logos and their teal/cyan/blue/ink palette. The user's later logo instruction supersedes the design document's lime palette; Poppins, top navigation, compact rounded cards and responsive layouts remain.

Claim detail pages now include a shared summary card: logo, product age, warranty dates/status, fault category, recorded repair count and document-type chips. Data comes from existing workflow, documents and product service-history endpoints. Uploaded receipts appear as Invoice; file contents and predictions are excluded from this card. Loading, unavailable and empty states are distinct.

React Toastify handles save confirmations and displayed request errors. Form field errors remain alongside the form. Removed custom toast rendering and duplicate success banners. Simplified selected customer-facing copy and added mobile claim-list cards.

Validation: production build passed; 4 existing frontend unit tests passed; ESLint passed. Existing mixed static/dynamic Claims import warning remains non-fatal.

Browser checks used a temporary isolated Axios adapter with sample data because the backend was not running. Verified desktop summary at 1440px, mobile summary at 390px, document chips, dashboard rendering and a Toastify Message sent confirmation. Screenshots contain sample data. No live end-to-end/backend regression run was performed. The temporary preview files were removed afterward.

Backend source, API contracts, model artifacts and database records were not changed.
