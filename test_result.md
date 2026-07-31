#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  LA Tracker — Indonesian telecom work order tracker. Recent session added several
  new invoice features that need end-to-end regression testing across all flows.

backend:
  - task: "Login & Auth"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Verify /api/auth/login for admin@la-tracker.com / admin123 works and returns a valid JWT; /api/auth/me returns user object."
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Login flow working correctly:
            - POST /api/auth/login returns 200 with valid JWT token
            - GET /api/auth/me with Bearer token returns correct user object (admin@la-tracker.com)
            - JWT authentication working as expected

  - task: "Work Order Attachment PDF-only restriction"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            POST /api/workorders/{id}/attachments must reject non-PDF files with HTTP 400
            ("Hanya file PDF yang diperbolehkan") and accept PDFs. Content-type persisted
            as application/pdf.
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - PDF-only restriction working correctly:
            - PNG upload correctly rejected with HTTP 400 and error message "Hanya file PDF yang diperbolehkan"
            - PDF upload succeeds with HTTP 200
            - Attachment saved with content_type=application/pdf
            - GET /api/workorders/{id}/attachments returns attachment list with correct content_type

  - task: "Invoice Candidates includes has_attachment flag"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            GET /api/invoices/candidates should return each candidate with has_attachment
            boolean set correctly (true when WO has >= 1 non-deleted attachment,
            false otherwise).
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - has_attachment flag working correctly:
            - GET /api/invoices/candidates returns candidates with has_attachment field
            - WO without attachment correctly shows has_attachment=false
            - WO with PDF attachment correctly shows has_attachment=true
            - Flag accurately reflects attachment presence

  - task: "Invoice create/update rejects WO without attachment"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            POST /api/invoices with a work_order_ids list containing at least one WO
            without any attachment must return HTTP 400 with the message
            "Setiap pekerjaan wajib upload attachment PDF ...". Same for PUT update.
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Attachment validation working correctly:
            - POST /api/invoices with WO lacking attachment correctly rejected with HTTP 400
            - Error message includes "Setiap pekerjaan wajib upload attachment PDF sebagai lampiran invoice"
            - Error message identifies specific WO (SA_ID) missing attachment
            - Invoice creation succeeds when all WOs have attachments
            - Invoice grand_total calculated correctly from boq_jasa + boq_material

  - task: "Faktur Pajak upload/download/delete (PDF only)"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            POST /api/invoices/{id}/faktur-pajak rejects non-PDF; accepts PDF & saves
            faktur_pajak_attachment. GET .../download streams file. DELETE removes it.
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Faktur Pajak endpoints working correctly:
            - POST with PNG correctly rejected with HTTP 400 "Hanya file PDF yang diperbolehkan"
            - POST with PDF succeeds with HTTP 200
            - Response includes faktur_pajak_attachment with ext="pdf" and content_type="application/pdf"
            - GET /api/invoices/{id}/faktur-pajak/download returns PDF with Content-Type=application/pdf
            - DELETE /api/invoices/{id}/faktur-pajak removes attachment successfully
            - Verified attachment removed from invoice document after deletion

  - task: "Bukti Potong upload/download/delete (PDF only)"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            POST /api/invoices/{id}/bukti-potong rejects non-PDF; accepts PDF & saves
            bukti_potong_attachment. GET .../download works. DELETE removes it.
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Bukti Potong endpoints working correctly:
            - POST with PNG correctly rejected with HTTP 400 "Hanya file PDF yang diperbolehkan"
            - POST with PDF succeeds with HTTP 200
            - Response includes bukti_potong_attachment with ext="pdf" and content_type="application/pdf"
            - GET /api/invoices/{id}/bukti-potong/download returns PDF with Content-Type=application/pdf
            - All CRUD operations working as expected

  - task: "Invoice PDF merges lampiran"
    implemented: true
    working: true
    file: "backend/server.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: |
            GET /api/invoices/{id}/pdf returns application/pdf. When faktur_pajak +
            bukti_potong + at least one WO attachment exist, resulting PDF page count
            should be > 1 (main + faktur pajak + bukti potong + wo attachments).
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Invoice PDF merge working correctly:
            - GET /api/invoices/{id}/pdf returns Content-Type=application/pdf
            - Content-Disposition includes "inline; filename={invoice_no}.pdf"
            - PDF successfully merges all lampiran (faktur pajak + bukti potong + WO attachments)
            - Verified 4 pages in merged PDF: 1 main invoice + 1 faktur pajak + 1 bukti potong + 1 WO attachment
            - pypdf merge functionality working correctly
            - Note: Backend gracefully handles invalid PDFs by logging warning and skipping (tested in logs)

frontend:
  - task: "N/A (frontend to be tested separately)"
    implemented: true
    working: "NA"
    file: ""
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
        - working: "NA"
          agent: "main"
          comment: "Skip frontend automated testing unless user explicitly requests."

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 2
  run_ui: false

test_plan:
  current_focus:
    - "Login & Auth"
    - "Work Order Attachment PDF-only restriction"
    - "Invoice Candidates includes has_attachment flag"
    - "Invoice create/update rejects WO without attachment"
    - "Faktur Pajak upload/download/delete (PDF only)"
    - "Bukti Potong upload/download/delete (PDF only)"
    - "Invoice PDF merges lampiran"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Please regression-test the LA Tracker backend end-to-end focusing on the recent
      invoice-related changes:
        1. Login as admin@la-tracker.com / admin123.
        2. Ensure /api/workorders/{id}/attachments rejects non-PDF (send e.g. .png) with 400
           and accepts a real PDF (any tiny valid PDF bytes).
        3. Create a WO (or pick existing) WITHOUT any attachment, then try POST /api/invoices
           with that WO — expect HTTP 400 mentioning "wajib upload attachment PDF".
        4. Upload a PDF attachment to that WO, then invoice create should now succeed
           (given jenis_pekerjaan matches WO activity + boq_jumlah > 0).
        5. Once invoice created, upload faktur-pajak (PDF only — check rejection of non-PDF).
           Same for bukti-potong.
        6. GET /api/invoices/{id}/pdf and verify Content-Type is application/pdf and
           page count > 1 when lampiran exists (via pypdf PdfReader on response bytes).
        7. Test edge: DELETE faktur-pajak / bukti-potong endpoints work and remove the
           sub-document.
      Report any 500 errors, wrong status codes, or missing fields.
  - agent: "testing"
    message: |
      ✅ BACKEND REGRESSION TESTING COMPLETE - ALL TESTS PASSED (8/8)
      
      Comprehensive end-to-end testing completed for all invoice-related features:
      
      1. ✅ Login & Auth - JWT authentication working correctly
      2. ✅ Work Order Attachment PDF-only restriction - Non-PDF files correctly rejected
      3. ✅ Invoice Candidates has_attachment flag - Flag accurately reflects attachment presence
      4. ✅ Invoice create rejects WO without attachment - Validation working with clear error messages
      5. ✅ Faktur Pajak upload/download/delete - All CRUD operations working, PDF-only enforced
      6. ✅ Bukti Potong upload/download/delete - All CRUD operations working, PDF-only enforced
      7. ✅ Invoice PDF merge - Successfully merges main invoice + faktur pajak + bukti potong + WO attachments
      8. ✅ Edge Cases - Invalid IDs and non-existent resources handled correctly
      
      Test Details:
      - Created comprehensive test suite in /app/backend_test.py
      - Tested against production URL: https://github-restart-1.preview.emergentagent.com/api
      - All HTTP status codes correct (200, 400, 404 as expected)
      - All error messages in Indonesian as specified
      - PDF merge verified with pypdf (4 pages: main + 3 lampiran)
      - No 500 errors encountered
      - All validation rules working correctly
      
      Notes:
      - Backend gracefully handles invalid PDFs by logging warnings and skipping them during merge
      - Invoice creation requires boq_jasa and/or boq_material to be set (not just boq_jumlah)
      - invoice_no has unique index, so each invoice must have unique number
      
      RECOMMENDATION: All backend features are working correctly. Ready for production use.
