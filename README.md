# AssureX

> AI-Assisted Warranty & Product Claim Assessment System

## Public deployment

- **Frontend (Vercel): https://assurex-gamma.vercel.app**
- [Vercel project dashboard](https://vercel.com/msaqibahmeds-projects/assurex)
- Frontend production deployment is live. Backend deployment and API connection are pending; sign-in, registration, claims, uploads and AI processing are not live yet.
- MongoDB Atlas: existing `assurex` database on `Cluster0`. Database credentials stay private; the database is not a public website.
- Render currently requires payment information before it will create even the requested free Key Value resource. Advanced backend deployment was deferred to prioritize the frontend URL.

Vercel uses the `frontend` root directory, Node.js 22, a clean `npm ci --include=optional` install, `npm run build`, and the `dist` output. React routes support direct links and refreshes. `/api` is reserved for the pending Render API connection.

AssureX is a warranty and product claim management system designed to streamline the complete journey from product registration to claim submission, document verification, AI-assisted assessment, and human review.

The system allows customers to register products, store warranty information, submit claims, upload supporting documents, extract information through OCR, receive an automated assessment, and track the final review process.

---

## 🚀 Features

### Customer Features

- Product registration
- Warranty management
- Warranty coverage tracking
- Claim creation and submission
- Document and evidence upload
- OCR-based document processing
- Automatic extraction of:
  - Serial numbers
  - Invoice details
  - Dates
  - Other document information
- Correction of extracted information
- Claim readiness checking
- AI-assisted claim assessment
- Claim status tracking
- Additional information requests
- Claim timeline
- Decision history
- Messages
- PDF evaluation report download

### Reviewer Features

- Review queue
- Assigned claim management
- Product and warranty verification
- Evidence inspection
- OCR data verification
- Rule-check inspection
- AI/model recommendation review
- Manual claim decisions
- Approve claims
- Reject claims
- Request additional information
- Decision history and reasoning

### Administrator Features

- User/account management
- Role management
- Reviewer assignment
- Claim assignment
- Warranty policy management
- Model/version management
- Audit logs
- Reports
- Service-center management

### Service Staff Features

- Service work queue
- Repair processing
- Replacement processing
- Service records
- Parts management
- Service cost tracking
- Repair/replacement notes
- Old and new serial number tracking

---

## 🔄 Claim Workflow

The overall AssureX workflow is:

```text
Customer
   ↓
Product Registration
   ↓
Warranty Information
   ↓
Claim Creation
   ↓
Document Upload
   ↓
OCR Processing
   ↓
Information Verification
   ↓
Claim Submission
   ↓
AI Assessment
   ↓
Manual Review
   ↓
Final Decision
   ↓
Evaluation Report
