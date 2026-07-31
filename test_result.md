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

  - task: "Work Order import template (GET /api/workorders/import/template.xlsx)"
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
            NEW endpoint. GET /api/workorders/import/template.xlsx (admin/operator only)
            should return HTTP 200 with Content-Type
            application/vnd.openxmlformats-officedocument.spreadsheetml.sheet and a
            Content-Disposition attachment filename workorders_import_template.xlsx.
            The workbook must contain a header row matching EXPORT_COLUMNS labels (e.g.
            "PELANGGAN", "BOQ JUMLAH") plus one example data row. Verify the file opens
            with openpyxl and header labels are present. Round-trip: downloading this
            template and POSTing it back to /api/workorders/import/xlsx should import the
            example row (inserted >= 1).
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Work Order import template working correctly:
            - GET /api/workorders/import/template.xlsx returns HTTP 200
            - Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
            - Content-Disposition: attachment; filename=workorders_import_template.xlsx
            - Excel file opens successfully with openpyxl
            - Header row (67 columns) contains required labels: "PELANGGAN", "BOQ JUMLAH"
            - Exactly one example data row present (row 2) with valid data
            - Round-trip test successful: downloaded template imported via POST /api/workorders/import/xlsx
            - Import returned {"inserted": 1} confirming successful import

  - task: "Invoices Excel export (GET /api/invoices/export/xlsx)"
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
            NEW endpoint. GET /api/invoices/export/xlsx returns an Excel file of invoices
            honoring optional query filters: pelanggan (regex), jenis_pekerjaan (upper),
            status (upper). Verify HTTP 200, Content-Type spreadsheet, Content-Disposition
            filename invoices.xlsx. Columns include NO INVOICE, PELANGGAN, JENIS PEKERJAAN,
            STATUS, JUMLAH WO, TOTAL JASA, TOTAL MATERIAL, GRAND TOTAL. Verify with openpyxl
            that header row present and row count matches number of invoices for a given
            filter. IMPORTANT: route must resolve BEFORE /api/invoices/{inv_id} (no 404/400
            "Invalid id"). Also confirm filter param status=OPEN only returns OPEN invoices.
        - working: true
          agent: "testing"
          comment: |
            ✅ PASS - Invoices Excel export working correctly:
            - GET /api/invoices/export/xlsx returns HTTP 200
            - Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
            - Content-Disposition: attachment; filename=invoices.xlsx
            - CRITICAL: Route NOT captured by /api/invoices/{inv_id} (no "Invalid id" or 404 error)
            - Excel file opens successfully with openpyxl
            - Header row (15 columns) contains all required labels:
              * NO INVOICE, PELANGGAN, JENIS PEKERJAAN, STATUS, JUMLAH WO
              * TOTAL JASA, TOTAL MATERIAL, GRAND TOTAL
            - Filter test with status=OPEN: row count (1) matches GET /api/invoices?status=OPEN count (1)
            - Filter functionality working correctly

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
  test_sequence: 3
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      NEW FEATURE — "More export options". Please test ONLY the two new endpoints
      (the previous invoice features already passed and are unchanged):
        1. Login as admin@la-tracker.com / admin123.
        2. GET /api/workorders/import/template.xlsx
           - Expect 200, spreadsheet content-type, filename workorders_import_template.xlsx.
           - Open bytes with openpyxl; verify header row contains labels like "PELANGGAN"
             and "BOQ JUMLAH", and there is exactly one example data row.
           - Round-trip: POST the downloaded bytes to /api/workorders/import/xlsx and
             expect {"inserted": >= 1}.
        3. GET /api/invoices/export/xlsx
           - Expect 200, spreadsheet content-type, filename invoices.xlsx.
           - Open with openpyxl; verify header labels (NO INVOICE, PELANGGAN, GRAND TOTAL...).
           - Verify it did NOT get captured by /api/invoices/{inv_id} (i.e. no 400 "Invalid id").
           - With filter ?status=OPEN, verify only OPEN invoices are included (data rows count
             matches GET /api/invoices?status=OPEN length).
      Report any 500s, wrong status codes, route-shadowing (export path captured by {inv_id}),
      or missing/blank headers.

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
      - Tested against production URL: https://project-bootstrap-18.preview.emergentagent.com/api
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

  - agent: "testing"
    message: |
      ✅ NEW ENDPOINTS TESTING COMPLETE - ALL TESTS PASSED (10/10)
      
      Successfully tested the two new export endpoints:
      
      9. ✅ Work Order import template (GET /api/workorders/import/template.xlsx)
         - HTTP 200 with correct Content-Type and Content-Disposition headers
         - Excel file contains 67-column header row with required labels (PELANGGAN, BOQ JUMLAH)
         - Exactly one example data row present
         - Round-trip test successful: template can be downloaded and re-imported
         - Import endpoint returned {"inserted": 1}
      
      10. ✅ Invoices Excel export (GET /api/invoices/export/xlsx)
          - HTTP 200 with correct Content-Type and Content-Disposition headers
          - CRITICAL: Route NOT captured by /api/invoices/{inv_id} (no route shadowing)
          - Excel file contains all required headers: NO INVOICE, PELANGGAN, JENIS PEKERJAAN, 
            STATUS, JUMLAH WO, TOTAL JASA, TOTAL MATERIAL, GRAND TOTAL
          - Filter functionality working: status=OPEN filter returns correct number of rows
          - Row count matches API endpoint count (verified with GET /api/invoices?status=OPEN)
      
      Test Details:
      - Updated /app/backend_test.py with two new test functions
      - All tests run against production URL: https://project-bootstrap-18.preview.emergentagent.com/api
      - Used openpyxl to parse and verify Excel file structure
      - No 500 errors, no route shadowing issues
      - All HTTP status codes correct (200 as expected)
      
      RECOMMENDATION: Both new export endpoints are working correctly and ready for production use.
