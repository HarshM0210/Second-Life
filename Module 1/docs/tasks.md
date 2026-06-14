# Implementation Plan: Grading, Fraud Detection & Quality System

## Overview

This plan implements Module 1 of the Second Life Commerce platform — the core grading, fraud detection, and quality assessment pipeline. The implementation follows Option B (no-VLM, fully classical path): anomalib PatchCore for anomaly detection, scikit-learn for intent classification, OpenCV for wear detection, weighted formula for health scoring, and template-based justification. The backend is a single FastAPI/Python service with all AI inference in-process. The frontend is React with structured Q&A, image/video upload, Health Card rendering, and P2P divert UI. Target: condition assessment under 2 seconds per item, CPU-only.

## Tasks

- [x] 1. Project scaffolding and core data models
  - [x] 1.1 Set up Python backend project structure with FastAPI
    - Create directory structure: `backend/app/` with `models/`, `services/`, `routers/`, `config/`, `storage/`
    - Initialize FastAPI application with CORS middleware for React frontend
    - Add `pyproject.toml` or `requirements.txt` with dependencies: fastapi, uvicorn, pydantic, scikit-learn, opencv-python-headless, anomalib, numpy, aiosqlite, hypothesis (dev)
    - Set up SQLite database initialization script with all tables (returns, health_cards, cost_lookup, category_weights, return_windows)
    - Seed configuration tables with default data (return windows, category weights, cost lookup values)
    - _Requirements: 1.1, 9.3, 13.4, 14.6_

  - [x] 1.2 Define core Pydantic data models and interfaces
    - Create `models/health_card.py` with HealthCard, FraudSignal, ScoreBreakdown Pydantic models matching the JSON schema
    - Create `models/return_request.py` with ReturnRequest, CatalogMetadata models
    - Create `models/results.py` with ReturnWindowResult, AnomalyResult, WearResult, IntentResult, HealthScoreResult, FraudScanResult, DispositionResult dataclasses
    - Create `models/qa.py` with Question, SupplementaryInput, ValidationResult models
    - Ensure all models enforce type constraints (health_score 0-100 integer, fraud_confidence 0.0-1.0, etc.)
    - _Requirements: 12.1, 12.2, 12.3, 18.1, 18.2, 18.3_

  - [x] 1.3 Set up React frontend project structure
    - Initialize React project with TypeScript using Vite
    - Install dependencies: axios (HTTP), react-router-dom, tailwindcss (styling)
    - Create directory structure: `frontend/src/` with `components/`, `pages/`, `services/`, `types/`, `hooks/`
    - Define TypeScript interfaces matching backend models (HealthCard, Question, ReturnRequest)
    - Set up API service layer with base URL configuration
    - _Requirements: 17.1, 17.2, 17.3_

- [x] 2. Return Window Validator and Q&A Collector
  - [x] 2.1 Implement Return Window Validator service
    - Create `services/return_window.py` with ReturnWindowValidator class
    - Implement `validate(delivery_date, category)` that calculates elapsed days and checks against configured window
    - Load return window config from SQLite (7 days Food & Grocery, 30 Electronics, 15 Clothing & Footwear, 30 Other, 30 default fallback)
    - Return ReturnWindowResult with eligible, window_days, days_elapsed, expiry_date, and message
    - Handle error cases: missing delivery date or config → raise ServiceError with retry message
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]\* 2.2 Write property test for return window eligibility (Property 1)
    - **Property 1: Return window eligibility is correctly computed**
    - Generate random delivery dates, categories, and current dates using Hypothesis
    - Assert: eligible iff days_elapsed <= configured window for category (or 30 if unconfigured)
    - **Validates: Requirements 1.1, 1.3**

  - [x] 2.3 Implement Q&A Collector service
    - Create `services/qa_collector.py` with QACollector class
    - Implement `get_questions(category)` returning ordered question sets per category from QnA_Categories.md specification
    - Implement `validate_answers(category, answers)` checking all required questions are answered
    - Return ValidationResult with is_valid, missing_question_ids
    - Define all 4 category question sets (Food: 6 questions, Electronics: 8, Clothing: 8, Other: 8) as structured data
    - Handle conditional questions (e.g., footwear-only sole condition, supplementary text fields)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]\* 2.4 Write property test for Q&A validation (Property 2)
    - **Property 2: Incomplete Q&A submissions are rejected**
    - Generate random answer maps with deliberate omissions using Hypothesis
    - Assert: submission rejected iff any required answer is missing, and missing IDs are reported
    - **Validates: Requirements 2.7**

  - [x] 2.5 Implement media validation logic
    - Create `services/media_validator.py` with image validation (1-5 images, JPEG/PNG, max 10MB each)
    - Add video validation (optional, max 15s duration, max 50MB, MP4/WebM)
    - Return structured validation result with accepted/rejected status and reasons
    - _Requirements: 3.1, 3.2, 3.5_

  - [ ]\* 2.6 Write property test for media validation (Property 3)
    - **Property 3: Media input validation accepts only valid uploads**
    - Generate random file metadata (count, formats, sizes) using Hypothesis
    - Assert: accepts iff count in [1,5], all formats JPEG/PNG, all sizes <= 10MB; video accepts iff duration <= 15s, size <= 50MB, format MP4/WebM
    - **Validates: Requirements 3.1, 3.2**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. AI Grading Components (Anomaly Detector, Wear Detector, Intent Classifier)
  - [x] 4.1 Implement Anomaly Detector service
    - Create `services/anomaly_detector.py` with AnomalyDetector class
    - Implement `detect(images, category)` using anomalib PatchCore inference
    - Load pre-trained category-specific model (or handle missing model gracefully)
    - Compute max anomaly_severity across all images (0.0-1.0)
    - Generate and store heatmap to local filesystem (S3-compatible path)
    - Handle failures: image corruption → severity=1.0 with failure_reason; no model → severity=0.0 with "anomaly_model_unavailable"
    - Enforce 1500ms timeout
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]\* 4.2 Write property test for anomaly severity max aggregation (Property 7)
    - **Property 7: Anomaly severity is the maximum across all processed images**
    - Generate random lists of per-image severity scores using Hypothesis
    - Assert: item-level anomaly_severity equals max of individual scores
    - **Validates: Requirements 6.2**

  - [x] 4.3 Implement Wear Detector service
    - Create `services/wear_detector.py` with WearDetector class
    - Implement `detect(images, category)` using OpenCV-based analysis
    - Detect category-relevant wear indicators: sole wear (footwear), fabric stress (clothing), stains, tag condition
    - Output wear_detection_penalty (0.0-1.0) and wear_indicators list
    - Handle failures: images unavailable → penalty=0.0, analysis_performed=false
    - Enforce 800ms timeout
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 4.4 Implement Intent Classifier service
    - Create `services/intent_classifier.py` with IntentClassifier class
    - Implement `classify(qa_answers, category)` using scikit-learn logistic regression or keyword mapping
    - Map answers to penalty categories: high (0.25/0.35), medium (0.15), low (0.05/0.10)
    - Detect Q&A-to-CV inconsistencies (e.g., "never_used_but_wear_detected") and flag for fraud aggregator
    - Handle unclassifiable answers: assign medium (0.15) with "unclassified_intent" flag
    - Enforce 200ms response time
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]\* 4.5 Write property test for intent classification penalties (Property 8)
    - **Property 8: Intent classification assigns correct penalty values**
    - Generate random Q&A answer combinations using Hypothesis
    - Assert: exactly one penalty category assigned; high→0.25/0.35, medium→0.15, low→0.05/0.10; unmappable→medium(0.15) default
    - **Validates: Requirements 8.1, 8.2, 8.5**

- [x] 5. Health Score Computation and Justification Engine
  - [x] 5.1 Implement Health Score Computer service
    - Create `services/health_score.py` with HealthScoreComputer class
    - Implement `compute(anomaly_severity, defect_penalty, return_reason_penalty, wear_detection_penalty, category)`
    - Apply formula: 100 - (w1*anomaly + w2*defect + w3*reason + w4*wear) with category-specific weights from DB
    - Clamp result to [0, 100] integer
    - Output HealthScoreResult with health_score, breakdown (4 contributions), and condition label
    - Map score to condition: >90→Excellent, >70→Good, >50→Fair, <=50→Poor
    - Enforce 100ms computation time
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]\* 5.2 Write property test for health score formula (Property 9)
    - **Property 9: Health score formula is correctly applied and clamped**
    - Generate random component scores in [0.0,1.0] and weights in [0.0,100.0] using Hypothesis
    - Assert: health_score == clamp(100 - (w1*a + w2*d + w3*r + w4*w), 0, 100) rounded to int
    - **Validates: Requirements 9.1, 9.2, 9.3**

  - [ ]\* 5.3 Write property test for score breakdown sum (Property 10)
    - **Property 10: Score breakdown sums to total penalty**
    - Generate random scores and weights using Hypothesis
    - Assert: sum of 4 weighted contributions == (100 - health_score) when not clamped, or >= 100 when clamped to 0
    - **Validates: Requirements 9.6**

  - [x] 5.4 Implement Template Justification Engine
    - Create `services/justification.py` with JustificationEngine class
    - Implement `generate(condition, defects, anomaly_severity, anomaly_threshold, functional_pass, warranty_months)`
    - Produce template: "{condition}. Detected: {defects}. {anomaly_phrase}. Functional check: {pass/fail}. Warranty: {n} months remaining."
    - Map anomaly phrases: severity < T → "No structural anomalies", >= T and < 2T → "Minor anomalies detected", >= 2T → "Significant anomalies detected"
    - Handle empty defects: "Detected: none"
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]\* 5.5 Write property test for condition label and anomaly phrase mapping (Property 11)
    - **Property 11: Condition label and anomaly phrase are correctly mapped**
    - Generate random health_scores [0,100] and anomaly_severity values with threshold T using Hypothesis
    - Assert: correct condition label per range; correct anomaly phrase per severity/threshold relationship
    - **Validates: Requirements 10.2, 10.5**

  - [ ]\* 5.6 Write property test for justification template completeness (Property 12)
    - **Property 12: Justification template includes all required components**
    - Generate random scoring outputs using Hypothesis
    - Assert: justification contains condition label, defect list (or "none"), anomaly phrase, functional result, and warranty months
    - **Validates: Requirements 10.1, 10.3, 10.4**

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Fraud Detection Layer (Scanner, Aggregator, Cross-Validation)
  - [x] 7.1 Implement Fraud Scanner service (mock Social Connect)
    - Create `services/fraud_scanner.py` with FraudScanner class
    - Implement `scan(customer_id, product_images, ownership_window, connected_accounts)`
    - Mock the Social Connect API — simulate scanning connected profiles within ownership window
    - Apply match threshold of 0.70 for recording evidence posts
    - Execute ONLY for Clothing & Footwear category; skip for all others
    - Handle API errors gracefully: set social_scan_performed=false, log error, continue pipeline
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ]\* 7.2 Write property test for fraud scanner category gating (Property 5)
    - **Property 5: Fraud scanner executes only for Clothing & Footwear**
    - Generate random categories using Hypothesis
    - Assert: scan executes iff category == "Clothing & Footwear"; otherwise social_scan_performed=false
    - **Validates: Requirements 4.1, 5.1, 5.2, 15.6, 16.4**

  - [ ]\* 7.3 Write property test for social match threshold (Property 6)
    - **Property 6: Social match evidence is recorded above threshold**
    - Generate random confidence scores using Hypothesis
    - Assert: match recorded iff confidence > 0.70
    - **Validates: Requirements 4.3, 4.4**

  - [x] 7.4 Implement Fraud Confidence Aggregator
    - Create `services/fraud_aggregator.py` with FraudAggregator class
    - Implement `aggregate(social_signal, wear_penalty, behavioural_score, social_scan_performed)`
    - Compute weighted sum with configurable weights summing to 1.0
    - Proportionally redistribute weights when signals are missing (social not performed → redistribute to wear + behavioural)
    - Output fraud_confidence in [0.0, 1.0]
    - Handle missing components: treat as 0.0, redistribute weights
    - Enforce 50ms completion
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ]\* 7.5 Write property test for fraud confidence aggregation (Property 13)
    - **Property 13: Fraud confidence aggregation with proportional weight redistribution**
    - Generate random signal combinations (some missing) using Hypothesis
    - Assert: weighted sum with redistributed weights; absence of social does not inflate/deflate; result in [0.0, 1.0]
    - **Validates: Requirements 11.1, 11.3, 11.4**

  - [x] 7.6 Implement Cross-Validation service
    - Create `services/cross_validator.py` with CrossValidator class
    - Implement logic: when both Q&A penalty and CV penalty available, use the maximum (more pessimistic)
    - Implement fraud escalation: "never used" + wear_detection_penalty > 0 → escalate fraud_confidence by factor [0.10, 0.40]
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [ ]\* 7.7 Write property test for cross-validation pessimistic signal (Property 19)
    - **Property 19: Cross-validation uses the more pessimistic signal**
    - Generate random penalty pairs using Hypothesis
    - Assert: authoritative penalty == max of Q&A and CV; "never used" + wear > 0 → fraud escalation in [0.10, 0.40]
    - **Validates: Requirements 21.1, 21.3**

- [x] 8. Disposition Router (Gate A, Gate B, Overrides)
  - [x] 8.1 Implement Disposition Router — Gate A (Economics)
    - Create `services/disposition_router.py` with DispositionRouter class
    - Implement Gate A: compare total_processing_cost (from cost_lookup table) vs product_value
    - If cost < value → "return_to_seller"; if cost >= value → proceed to Gate B
    - Handle missing category in cost table → "manual_review"
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [ ]\* 8.2 Write property test for Gate A routing (Property 14)
    - **Property 14: Gate A routes correctly based on cost vs value**
    - Generate random (cost, value) pairs using Hypothesis
    - Assert: cost < value → "return_to_seller"; cost >= value → proceeds to Gate B
    - **Validates: Requirements 13.1, 13.2, 13.3**

  - [x] 8.3 Implement Disposition Router — Gate B (Health Score Thresholds)
    - Extend DispositionRouter with Gate B logic
    - Map health_score to disposition: >90→resell, >70→refurbish, >50→donate, <=50→recycle
    - Handle unavailable health_score → default "recycle" with flag
    - Enforce 200ms completion
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [ ]\* 8.4 Write property test for Gate B thresholds (Property 15)
    - **Property 15: Gate B assigns disposition by health score thresholds**
    - Generate random health_scores [0, 100] using Hypothesis
    - Assert: >90→resell, >70 and <=90→refurbish, >50 and <=70→donate, <=50→recycle
    - **Validates: Requirements 14.1, 14.2, 14.3, 14.4**

  - [x] 8.5 Implement Category-Specific Overrides — Food & Grocery
    - Add Food & Grocery safety logic to DispositionRouter
    - Seal broken OR partially/mostly consumed → "recycle" (bypasses gates)
    - Expired → "recycle" (bypasses gates)
    - Sealed + unexpired + "Wrong item delivered" → "return_to_seller"
    - Sealed + unexpired + other reason → normal Gate A/B flow
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

  - [ ]\* 8.6 Write property test for Food & Grocery overrides (Property 17)
    - **Property 17: Food & Grocery safety overrides bypass normal routing**
    - Generate random food Q&A combinations using Hypothesis
    - Assert: broken seal/consumed/expired → recycle regardless of score; sealed+unexpired+"Wrong item" → return_to_seller
    - **Validates: Requirements 19.1, 19.2, 19.3, 19.4**

  - [x] 8.7 Implement Safety and Hygiene Overrides
    - Add safety overrides: any safety concern → "manual_review" (bypasses all gates)
    - Add hygiene overrides: Other category + used on skin → donate (good condition) or recycle (poor condition)
    - Add Electronics override: unreset device → "manual_review" with factory_reset_required flag
    - _Requirements: 20.1, 20.2, 20.3, 20.4_

  - [ ]\* 8.8 Write property test for safety/hygiene overrides (Property 18)
    - **Property 18: Safety and hygiene overrides bypass automatic disposition**
    - Generate random safety/hygiene scenarios using Hypothesis
    - Assert: safety concern → manual_review; skin contact → donate/recycle; unreset → manual_review + flag
    - **Validates: Requirements 20.1, 20.2, 20.3**

- [x] 9. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Health Card Assembly and Pipeline Orchestrator
  - [x] 10.1 Implement Health Card Assembler
    - Create `services/health_card_assembler.py` with HealthCardAssembler class
    - Implement `assemble(...)` composing all pipeline outputs into Health Card JSON
    - Set source field: "p2p_fraud_divert" when fraud_confidence >= 0.60 AND category Clothing & Footwear AND customer chose P2P; otherwise "standard_return"
    - Ensure all required schema fields are present; null fields when unavailable with confidence=0.0
    - Validate fraud_signal block completeness
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 18.1, 18.4_

  - [ ]\* 10.2 Write property test for Health Card source field (Property 16)
    - **Property 16: Health Card source field reflects P2P choice**
    - Generate random fraud_confidence, category, and P2P choice combinations using Hypothesis
    - Assert: fraud >= 0.60 AND Clothing & Footwear AND chose P2P → source="p2p_fraud_divert"; else → source="standard_return"
    - **Validates: Requirements 12.4, 12.5, 15.3**

  - [x] 10.3 Implement Pipeline Orchestrator with async parallel execution
    - Create `services/pipeline_orchestrator.py` with PipelineOrchestrator class
    - Implement `async execute(return_request)` coordinating full end-to-end flow
    - Use asyncio.gather for parallel execution: Grader pipeline (Anomaly + Wear + Intent) + Fraud Scanner (Clothing & Footwear only)
    - Apply cross-validation after grader completes
    - Run fraud aggregation, then disposition routing, then Health Card assembly
    - Enforce 2000ms total budget; 5000ms individual component hard timeout
    - Handle partial failures per error handling strategy in design
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [x] 10.4 Implement video frame extraction utility
    - Create `services/frame_extractor.py` with extract_frames function
    - Extract minimum 5 evenly-spaced frames from video (client-side in production, server fallback for demo)
    - Calculate frame timestamps distributed across video duration
    - _Requirements: 3.3_

  - [ ]\* 10.5 Write property test for frame extraction spacing (Property 4)
    - **Property 4: Video frame extraction produces evenly-spaced frames**
    - Generate random video durations [1, 15] seconds using Hypothesis
    - Assert: >= 5 frames produced with timestamps evenly distributed across duration
    - **Validates: Requirements 3.3**

- [x] 11. FastAPI Routes and API Endpoints
  - [x] 11.1 Implement POST /api/returns/initiate endpoint
    - Create `routers/returns.py` with return initiation endpoint
    - Accept order_id, product_id, customer_id; look up delivery date and category from DB/mock
    - Call ReturnWindowValidator; return eligibility + category-specific questions if eligible
    - Return 403 with expiry message if window expired
    - Persist return session in SQLite with status "initiated"
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1_

  - [x] 11.2 Implement POST /api/returns/{return_id}/submit endpoint
    - Accept qa_answers, image_uris, video_frame_uris, catalog_metadata
    - Validate Q&A answers via QACollector
    - Validate media via media validator
    - Trigger PipelineOrchestrator.execute() with all inputs
    - Return Health Card JSON response (or P2P divert offer if applicable)
    - Persist health card in SQLite
    - _Requirements: 2.7, 2.8, 3.4, 5.1, 5.2, 12.1_

  - [x] 11.3 Implement POST /api/returns/{return_id}/p2p-choice endpoint
    - Accept chose_p2p boolean
    - Update Health Card source field accordingly
    - If chose P2P: source="p2p_fraud_divert", customer_chose_p2p=true
    - If chose standard: proceed with Gate A/B, set enhanced_inspection flag
    - Return updated Health Card
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 12. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. React Frontend — Structured Q&A and Media Upload
  - [x] 13.1 Implement Return Initiation page
    - Create `pages/ReturnInitiate.tsx` with order_id/product_id input form
    - Call POST /api/returns/initiate and handle eligible/ineligible responses
    - Display expiry message with date when window is expired (block further navigation)
    - Navigate to Q&A page on success
    - _Requirements: 1.2, 1.4, 1.5_

  - [x] 13.2 Implement Structured Q&A form component
    - Create `components/QAForm.tsx` rendering category-specific questions dynamically
    - Render each question as single-select radio buttons with predefined options
    - Handle supplementary inputs: text field (max 200 chars) and date picker where applicable
    - Handle conditional display (e.g., footwear-only questions)
    - Validate all required questions answered before allowing submission
    - Show unanswered question indicators on attempted submit
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 13.3 Implement Image/Video upload component with client-side frame extraction
    - Create `components/MediaUpload.tsx` with drag-and-drop or file picker
    - Enforce 1-5 images, JPEG/PNG only, max 10MB per image (client-side validation)
    - Optional video: max 15s, max 50MB, MP4/WebM
    - Implement client-side video frame extraction using canvas: extract >= 5 evenly-spaced frames
    - Show upload progress, handle errors with retry capability (preserve previously uploaded files)
    - _Requirements: 3.1, 3.2, 3.3, 3.5_

  - [x] 13.4 Wire Q&A + media submission flow
    - Create `pages/ReturnSubmit.tsx` combining QAForm and MediaUpload
    - On submit: call POST /api/returns/{id}/submit with qa_answers + media URIs + catalog metadata
    - Show loading state during pipeline processing (up to 2s)
    - Route to Health Card display or P2P divert UI based on response
    - _Requirements: 2.8, 3.4, 5.4_

- [x] 14. React Frontend — Health Card and P2P Divert UI
  - [x] 14.1 Implement Health Card render component
    - Create `components/HealthCard.tsx` displaying: condition label, health score, confidence %, defects list, heatmap image, justification, disposition
    - Implement score-breakdown bar with 4 labeled proportional segments (anomaly, defect, reason, wear contributions)
    - Each segment labeled with penalty name and numeric value rounded to 1 decimal place
    - Display "Certified by Amazon AI" badge
    - Handle heatmap load failure: show placeholder with "heatmap unavailable" text
    - Handle empty defects: show "No defects detected" message
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x] 14.2 Implement P2P Divert UI component
    - Create `components/P2PDivert.tsx` with non-accusatory offer screen
    - Display messaging: "We noticed this item may have been used..." (no fraud/theft/dishonesty language)
    - Present exactly two choices: "Resell via ReLoop P2P" and "Proceed with standard return inspection"
    - Call POST /api/returns/{id}/p2p-choice on selection
    - Handle 30-minute timeout: auto-proceed with standard return + enhanced_inspection flag
    - Navigate to Health Card display after choice
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 15. Integration, Storage, and Final Wiring
  - [x] 15.1 Implement S3/local filesystem storage for media and heatmaps
    - Create `storage/media_store.py` with save/retrieve for images, video frames, and heatmaps
    - Use local filesystem for demo (configurable path); interface compatible with S3
    - Generate accessible URIs for stored heatmaps (used in Health Card anomaly_heatmap_uri)
    - _Requirements: 6.3, 17.4_

  - [x] 15.2 Wire full end-to-end pipeline with SQLite persistence
    - Connect all services in PipelineOrchestrator with real DB reads (category weights, cost lookup, return windows)
    - Persist return sessions (status transitions: initiated → qa_complete → grading → complete/error)
    - Persist completed Health Cards in health_cards table
    - Ensure graceful degradation hierarchy: full → no social → no anomaly model → partial failure → complete failure
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 18.4_

  - [ ]\* 15.3 Write integration tests for pipeline timing and parallel execution
    - Test end-to-end pipeline completes within 2 seconds for standard inputs
    - Test parallel execution of Fraud Scanner + Grader for Clothing & Footwear
    - Test graceful degradation when components fail/timeout
    - _Requirements: 5.4, 5.5, 5.6_

- [x] 16. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 19 universal correctness properties defined in the design using Hypothesis
- Unit tests validate specific examples and edge cases
- The backend uses Python/FastAPI with all AI inference in-process (no external API calls)
- The frontend uses React with TypeScript
- SQLite is used for demo persistence; the storage interface is designed for easy S3 migration
- All AI components (anomalib PatchCore, scikit-learn, OpenCV) run CPU-only
- The fraud scanner is mocked for the hackathon demo (simulates Social Connect API)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1", "2.3", "2.5", "4.4"] },
    { "id": 3, "tasks": ["2.2", "2.4", "2.6", "4.1", "4.3", "4.5"] },
    { "id": 4, "tasks": ["4.2", "5.1", "5.4", "7.1"] },
    { "id": 5, "tasks": ["5.2", "5.3", "5.5", "5.6", "7.4", "7.6"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.5", "7.7", "8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3", "8.5", "8.7"] },
    { "id": 8, "tasks": ["8.4", "8.6", "8.8", "10.1", "10.4"] },
    { "id": 9, "tasks": ["10.2", "10.3", "10.5"] },
    { "id": 10, "tasks": ["11.1", "11.2", "11.3", "15.1"] },
    { "id": 11, "tasks": ["13.1", "13.2", "13.3", "15.2"] },
    { "id": 12, "tasks": ["13.4", "14.1", "14.2", "15.3"] }
  ]
}
```
