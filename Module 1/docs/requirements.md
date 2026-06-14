# Requirements Document

## Introduction

Module 1 — Grading, Fraud Detection & Quality System — is the core module of the Second Life Commerce platform. It receives a returned item (images, video, structured Q&A answers, catalog metadata), runs a Social Connect fraud check and an AI grader in parallel, produces a Health Card JSON (the inter-module contract consumed by Modules 2–5), and routes the item to its highest-value disposition. Option B (no-VLM, fully classical) is used: anomalib PatchCore anomaly detection, scikit-learn intent classifier, CV wear detection, weighted health score formula, and template-based justification. Target: condition assessment in under 2 seconds per item, no GPU required.

## Glossary

- **System**: The Module 1 Grading, Fraud Detection & Quality System as a whole
- **Grader**: The AI grading subsystem that produces the health score and justification via anomaly detection, intent classification, wear detection, and weighted scoring
- **Fraud_Scanner**: The Social Connect fraud check service that scans connected public social profiles for evidence of wardrobing
- **Health_Card**: The JSON output document containing condition, health_score, confidence, defects, disposition, justification, and fraud_signal — the inter-module contract
- **Disposition_Router**: The subsystem that applies Gate A (economics) and Gate B (health score thresholds) to determine the item's next destination
- **QA_Collector**: The structured Q&A UI that collects category-specific answers from the customer
- **Intent_Classifier**: The scikit-learn logistic regression or keyword-map classifier that maps structured Q&A answers to a return_reason_penalty score
- **Anomaly_Detector**: The anomalib PatchCore/FastFlow unsupervised anomaly detection model that produces a pixel-level heatmap and anomaly severity score from item images
- **Wear_Detector**: The CV layer that analyzes submitted images for use evidence (sole wear, fabric stress, stains, tag condition) and produces a wear_detection_penalty score
- **Fraud_Aggregator**: The subsystem that merges the social signal, wear detection score, and behavioural score into a single fraud_confidence value
- **P2P_Divert_UI**: The non-accusatory offer screen shown to customers when wardrobing is detected
- **Wardrobing**: The fraudulent practice of purchasing items, using them briefly (e.g., wearing to an event), then returning them as unused
- **Health_Score**: A numeric value 0–100 computed by the formula: 100 - (w1·anomaly_severity + w2·defect_penalty + w3·return_reason_penalty + w4·wear_detection_penalty)
- **Disposition**: One of: resell, refurbish, donate, recycle, return_to_seller
- **Ownership_Window**: The date range from purchase date to return initiation date, used to scope the social media scan

## Requirements

### Requirement 1: Return Window Validation

**User Story:** As a customer, I want the system to check whether my return is within the allowed window, so that only eligible returns proceed to grading.

#### Acceptance Criteria

1. WHEN a customer initiates a return, THE System SHALL calculate the elapsed days from the original order delivery date to the current date and verify that it does not exceed the configured return window (in days) for the product category (e.g., 7 days for Food & Grocery, 30 days for Electronics, 15 days for Clothing & Footwear, 30 days for Other)
2. IF the return is initiated outside the allowed return window, THEN THE System SHALL block the return, prevent navigation to any subsequent return steps (structured Q&A, image upload, grading), and display a message indicating the return window has expired along with the expiry date
3. IF the category-specific return window configuration is unavailable for the product, THEN THE System SHALL apply a default return window of 30 days from the delivery date
4. WHEN the return is within the allowed window, THE System SHALL proceed to the structured input collection step
5. IF the system cannot retrieve the delivery date or return window configuration due to a service error, THEN THE System SHALL display an error message indicating the return eligibility could not be verified and prompt the customer to retry

### Requirement 2: Structured Q&A Input Collection

**User Story:** As a customer, I want to answer category-specific questions about my return, so that the system can accurately assess the item condition without ambiguity.

#### Acceptance Criteria

1. WHEN a return passes the window check, THE QA_Collector SHALL present a category-specific question set based on the product category derived from the catalog metadata: Food & Grocery (6 questions), Electronics (8 questions), Clothing & Footwear (8 questions), or Other (8 questions)
2. THE QA_Collector SHALL present each question as a single-select multiple-choice input with predefined answer options, except where a question requires supplementary input, in which case an additional text field (maximum 200 characters) or date picker SHALL be displayed alongside the selected option
3. WHEN the product category is Food & Grocery, THE QA_Collector SHALL ask questions in this order: return reason, seal integrity, packaging condition, storage compliance, expiry date (date picker input), and quantity remaining
4. WHEN the product category is Electronics, THE QA_Collector SHALL ask questions in this order: return reason, functional status, physical condition, accessories completeness (with a text field for specifying missing items when applicable), original packaging, ownership duration, factory reset status, and liquid/impact damage history
5. WHEN the product category is Clothing & Footwear, THE QA_Collector SHALL ask questions in this order: return reason, wear history, tag status, washing history, staining or odour presence, original packaging, sole condition (displayed only when the item subcategory is footwear), and physical damage
6. WHEN the product category is Other, THE QA_Collector SHALL ask questions in this order: return reason, usage extent, physical condition, parts completeness (with a text field for specifying missing parts when applicable), original packaging, skin/body contact status, safety concerns (with a text field for describing the concern when applicable), and hygiene concerns
7. IF a customer attempts to proceed without answering all displayed questions, THEN THE QA_Collector SHALL prevent submission and indicate which unanswered questions remain
8. WHEN all displayed questions are answered, THE QA_Collector SHALL pass the structured answers as key-value pairs to the Intent_Classifier and the Grader pipeline within 1 second of submission

### Requirement 3: Image and Video Input Collection

**User Story:** As a customer, I want to upload images and a short video of my item, so that the AI can visually assess condition.

#### Acceptance Criteria

1. WHEN a return passes the window check, THE System SHALL prompt the customer to upload between 1 and 5 images of the item in JPEG or PNG format, each no larger than 10 MB
2. THE System SHALL accept an optional video (maximum 15 seconds duration, maximum 50 MB file size) of the item from the customer in MP4 or WebM format
3. WHEN a video is provided, THE System SHALL extract a minimum of 5 evenly-spaced frames from the video on the client side for use by the Anomaly_Detector and Wear_Detector
4. WHEN all images are uploaded and any video frames are extracted, THE System SHALL pass all images and extracted frames along with catalog metadata (category, original price, purchase date, warranty remaining) to the Grader pipeline
5. IF an image or video upload fails due to network error or invalid file, THEN THE System SHALL display an error message indicating the failure reason and allow the customer to retry the upload without losing previously uploaded files

### Requirement 4: Social Connect Fraud Check

**User Story:** As the platform, I want to detect wardrobing fraud by scanning customers' connected social profiles for evidence of product use, so that fraudulent returns of clothing and footwear can be identified non-invasively.

#### Acceptance Criteria

1. THE Fraud_Scanner SHALL execute only when the product category is Clothing & Footwear — for all other categories the Fraud_Scanner SHALL be skipped and social_scan_performed SHALL be set to false
2. WHEN the product category is Clothing & Footwear AND the customer has connected social accounts, THE Fraud_Scanner SHALL scan public posts on the connected profiles (Instagram, Facebook, X) within the Ownership_Window
3. THE Fraud_Scanner SHALL perform visual matching of social media images against the Amazon catalog reference images for the returned product using a matching confidence threshold of 0.70
4. WHEN the Fraud_Scanner finds a visual match with confidence above 0.70, THE Fraud_Scanner SHALL record the platform, post date, match confidence, and post type as evidence in the evidence_posts array
5. THE Fraud_Scanner SHALL output a fraud signal JSON containing: social_scan_performed (boolean), accounts_scanned (array of platform names), product_found_in_social (boolean), fraud_confidence (number 0.0–1.0), evidence_posts (array), and scan_window (object with from and to dates)
6. THE Fraud_Scanner SHALL limit scanning scope strictly to public posts within the Ownership_Window and connected accounts only — no private posts, DMs, or content outside the window
7. IF the customer has no connected social accounts, THEN THE Fraud_Scanner SHALL set social_scan_performed to false and impose no penalty on the customer (fraud_confidence derived from wear and behavioural signals only)
8. IF the social media API returns an error or is unavailable, THEN THE Fraud_Scanner SHALL set social_scan_performed to false, log the error, and allow the pipeline to proceed without social data

### Requirement 5: Parallel Execution of Fraud Check and AI Grader

**User Story:** As the platform, I want fraud detection and item grading to run in parallel, so that total assessment time remains under 2 seconds.

#### Acceptance Criteria

1. WHEN structured input collection (Q&A answers and image/video uploads) is complete AND the product category is Clothing & Footwear, THE System SHALL initiate the Fraud_Scanner and the Grader concurrently
2. WHEN structured input collection (Q&A answers and image/video uploads) is complete AND the product category is not Clothing & Footwear, THE System SHALL initiate only the Grader (Fraud_Scanner is skipped)
3. WHEN all initiated pipeline components have completed or timed out, THE System SHALL proceed to disposition routing only after all results are available
4. THE System SHALL complete the combined pipeline (fraud check where applicable + grading) in under 2 seconds per item when processing images up to 1920x1080 resolution and video up to 15 seconds duration
5. IF any initiated pipeline component (Fraud_Scanner or Grader sub-component) does not respond within 5 seconds, THEN THE System SHALL terminate that component, log the timeout, and proceed with available results from the remaining components
6. IF the Grader fails or times out entirely, THEN THE System SHALL not produce a Health_Card and SHALL return an error indicating that grading could not be completed for the item

### Requirement 6: Anomaly Detection

**User Story:** As the platform, I want to detect product anomalies using unsupervised learning on defect-free reference images, so that no labeled defect dataset is required.

#### Acceptance Criteria

1. WHEN item images and extracted video frames are available AND a trained PatchCore or FastFlow model exists for the product category, THE Anomaly_Detector SHALL process them using the anomalib library model trained only on defect-free reference images for that category
2. THE Anomaly_Detector SHALL output a pixel-level anomaly heatmap image and a numeric anomaly severity score in the range 0.0 to 1.0 inclusive for each item, where the item-level score is the maximum anomaly severity across all processed images and frames
3. THE Anomaly_Detector SHALL store the generated heatmap at an accessible URI (S3 or local storage) and include that URI in the Health_Card anomaly_heatmap_uri field
4. THE Anomaly_Detector SHALL operate on CPU without requiring GPU hardware and SHALL complete inference for a single item within 1500 milliseconds
5. IF the Anomaly_Detector fails to process one or more images due to corruption or an internal model error, THEN THE Anomaly_Detector SHALL set the anomaly severity score to 1.0 (worst case) and record the failure reason in the Health_Card defects array
6. IF no trained model exists for the product category, THEN THE Anomaly_Detector SHALL skip anomaly scoring, set the anomaly severity score to 0.0 (no penalty), and record the absence in the Health_Card defects array as "anomaly_model_unavailable"

### Requirement 7: Wear Detection

**User Story:** As the platform, I want to detect physical signs of use (sole wear, fabric stress, stains, makeup marks, tag condition) from submitted images, so that a wear penalty contributes to the health score.

#### Acceptance Criteria

1. WHEN item images are available, THE Wear_Detector SHALL analyze submitted images for category-relevant use evidence: sole wear and outsole abrasion for footwear, fabric stress points and pilling for clothing, stains, makeup marks on collars, and tag condition (attached, removed, or damaged)
2. THE Wear_Detector SHALL output a wear_detection_penalty as a numeric value in the range 0.0 to 1.0 inclusive, where 0.0 indicates no detectable wear and 1.0 indicates maximum detectable wear
3. THE Wear_Detector SHALL provide the wear_detection_penalty to the Fraud_Aggregator as an independent fraud signal
4. THE Wear_Detector SHALL operate on CPU without requiring GPU hardware and SHALL complete image analysis within 800 milliseconds per item
5. IF item images are unavailable or cannot be processed, THEN THE Wear_Detector SHALL return a wear_detection_penalty of 0.0 and SHALL include a flag indicating that wear analysis was not performed

### Requirement 8: Intent Classification from Q&A

**User Story:** As the platform, I want to classify the customer's return intent from structured Q&A answers, so that functional defect claims receive appropriate penalty weighting.

#### Acceptance Criteria

1. WHEN structured Q&A answers are received, THE Intent_Classifier SHALL classify the return intent into exactly one penalty category (high, medium, or low) using a scikit-learn logistic regression model or keyword mapping, and SHALL complete classification within 200 milliseconds
2. THE Intent_Classifier SHALL assign a return_reason_penalty score: high penalty (0.25 for partially functional claims, 0.35 for non-functional/completely broken claims), medium penalty (0.15) for "not as described" claims, and low penalty (0.05 for preference reasons such as changed mind, 0.10 for cosmetic or fit reasons such as wrong size)
3. THE Intent_Classifier SHALL output the return_reason_penalty as a numeric value that feeds into the Health_Score formula with weight w3
4. WHEN the Q&A answers indicate "never used" (including "Never used — still in original packaging", "Never worn — tags still attached", or "Never used — completely unused") AND the Wear_Detector produces a wear_detection_penalty greater than 0, THE Intent_Classifier SHALL flag the inconsistency as a fraud signal escalation to the Fraud_Aggregator
5. IF the Q&A return reason answer cannot be mapped to any defined penalty category, THEN THE Intent_Classifier SHALL assign the medium penalty value (0.15) as a default and include an "unclassified_intent" flag in the output for downstream review

### Requirement 9: Health Score Computation

**User Story:** As the platform, I want a transparent, weighted formula that computes the item health score, so that the score is fully explainable and traceable.

#### Acceptance Criteria

1. THE Grader SHALL compute the Health_Score using the formula: health_score = 100 - (w1·anomaly_severity + w2·defect_penalty + w3·return_reason_penalty + w4·wear_detection_penalty), where each component score (anomaly_severity, defect_penalty, return_reason_penalty, wear_detection_penalty) is a normalized float in the range 0.0 to 1.0 inclusive
2. IF the computed formula result is less than 0, THEN THE Grader SHALL clamp the Health_Score to 0; IF the computed formula result is greater than 100, THEN THE Grader SHALL clamp the Health_Score to 100
3. THE Grader SHALL use configurable weights (w1, w2, w3, w4) per product category, where each weight is a non-negative float in the range 0.0 to 100.0 inclusive
4. WHEN all component scores are computed, THE Grader SHALL compute the Health_Score within 100 milliseconds
5. THE Grader SHALL derive defect_penalty from the count and severity of defects detected by the Anomaly_Detector and Wear_Detector, normalized to a float in the range 0.0 to 1.0
6. WHEN the Health_Score is computed, THE Grader SHALL output a score breakdown listing each component's individual weighted contribution (w1·anomaly_severity, w2·defect_penalty, w3·return_reason_penalty, w4·wear_detection_penalty) alongside the final Health_Score

### Requirement 10: Template-Based Justification

**User Story:** As a customer, I want a human-readable justification of the grading result, so that I trust the assessment.

#### Acceptance Criteria

1. WHEN the Health_Score is computed, THE Grader SHALL generate a justification string using a template engine fed by the structured scoring outputs, producing output in the format: "{condition_label}. Detected: {defect_list}. {anomaly_phrase}. Functional check: {pass_or_fail}. Warranty: {n} months remaining."
2. THE Grader SHALL map the Health_Score to a condition label using the following ranges: "Excellent" for scores above 90, "Good" for scores above 70 up to 90, "Fair" for scores above 50 up to 70, and "Poor" for scores 50 or below
3. THE Grader SHALL include in the justification: condition label, detected defects list (comma-separated defect names with location), anomaly assessment phrase, functional check result ("pass" or "fail"), and warranty months remaining as an integer
4. IF no defects are detected, THEN THE Grader SHALL render the defects portion of the justification as "Detected: none"
5. THE Grader SHALL select the anomaly assessment phrase from a fixed set based on the anomaly severity score: "No structural anomalies" when severity is below the anomaly threshold, "Minor anomalies detected" when severity is at or above the anomaly threshold but below twice the threshold, and "Significant anomalies detected" when severity is at or above twice the threshold
6. THE Grader SHALL produce a justification where every variable value is sourced directly from the scoring pipeline outputs (anomaly_severity, defect_penalty, return_reason_penalty, wear_detection_penalty, warranty_left_months) with no values generated outside the pipeline

### Requirement 11: Fraud Confidence Aggregation

**User Story:** As the platform, I want to merge social scan results, wear detection, and behavioural signals into a single fraud confidence score, so that one threshold drives the disposition branch.

#### Acceptance Criteria

1. WHEN the Fraud_Scanner and Wear_Detector have both completed, THE Fraud_Aggregator SHALL compute a single fraud_confidence value in the range 0.0 to 1.0 using a weighted sum of: the social signal score (derived from product_found_in_social and match confidence), the wear_detection_penalty (normalized to 0.0–1.0), and the behavioural score (normalized to 0.0–1.0), with configurable weights per signal that sum to 1.0
2. THE Fraud_Aggregator SHALL define the behavioural score as a normalized value (0.0 to 1.0) derived from Q&A inconsistency flags (e.g., self-reported "never used" contradicted by wear evidence) and historical return pattern signals (return frequency, wardrobing pattern matches)
3. IF social_scan_performed is false, THEN THE Fraud_Aggregator SHALL compute fraud_confidence using only wear detection and behavioural signals, redistributing the social signal weight proportionally across the remaining signals so that the absence of social data does not inflate or deflate the score
4. IF the Wear_Detector or the behavioural signal source fails to produce a result within the pipeline timeout, THEN THE Fraud_Aggregator SHALL treat the missing component score as 0.0, log the failure, and compute fraud_confidence from the remaining available signals using proportionally redistributed weights
5. THE Fraud_Aggregator SHALL complete the fraud_confidence computation within 50 milliseconds after all input signals are available

### Requirement 12: Health Card JSON Output

**User Story:** As downstream modules (2–5), I want to receive a complete Health Card JSON in the exact inter-module contract schema, so that all modules can consume it reliably.

#### Acceptance Criteria

1. WHEN the Grader and Fraud_Aggregator have completed, THE System SHALL produce a Health_Card JSON object containing all required fields: condition (one of "Excellent", "Good", "Fair", "Poor"), health_score (integer 0–100), confidence (number 0.0–1.0), warranty_left_months (non-negative integer), defects (array of strings), anomaly_heatmap_uri (valid URI string), justification (non-empty string), disposition (one of "resell", "refurbish", "donate", "recycle", "return_to_seller"), source (one of "standard_return", "p2p_fraud_divert"), and fraud_signal block
2. THE Health_Card SHALL include a fraud_signal block containing: social_scan_performed (boolean), product_found_in_social (boolean), fraud_confidence (number 0.0–1.0), p2p_offered (boolean), and customer_chose_p2p (boolean)
3. THE System SHALL never remove or rename existing fields in the Health_Card schema — only additive changes are permitted
4. IF the item follows the P2P fraud divert path (fraud_confidence >= 0.60 AND customer chose P2P resale), THEN THE Health_Card SHALL set the source field to "p2p_fraud_divert"
5. IF the item does not follow the P2P fraud divert path, THEN THE Health_Card SHALL set the source field to "standard_return"
6. IF the Grader or Fraud_Aggregator fails to complete within 2 seconds or returns an error, THEN THE System SHALL not produce a partial Health_Card and SHALL return an error indication to the caller identifying which component failed

### Requirement 13: Disposition Routing — Gate A (Economics)

**User Story:** As the platform, I want to check whether the total processing cost exceeds the product value, so that uneconomic items are routed to their highest-value alternative destination instead of being written off.

#### Acceptance Criteria

1. WHEN fraud_confidence is below 0.60 (genuine return), THE Disposition_Router SHALL apply Gate A by comparing the item's total_processing_cost against its product_value (the original catalog price from catalog metadata)
2. IF total_processing_cost is less than product_value, THEN THE Disposition_Router SHALL set disposition to "return_to_seller"
3. IF total_processing_cost is greater than or equal to product_value, THEN THE Disposition_Router SHALL proceed to Gate B (health score thresholds) to determine disposition
4. THE Disposition_Router SHALL compute total_processing_cost by looking up the sum of reverse logistics, inspection, refurbishment labor, and storage costs from a cost lookup table (CSV) keyed by product category
5. IF the product category is not found in the cost lookup table, THEN THE Disposition_Router SHALL route the item to a manual review queue and set disposition to "pending_manual_review"

### Requirement 14: Disposition Routing — Gate B (Health Score Thresholds)

**User Story:** As the platform, I want to route items to resell, refurbish, donate, or recycle based on their health score, so that each item reaches its highest-value destination.

#### Acceptance Criteria

1. WHEN Gate A routes an item to Gate B, THE Disposition_Router SHALL assign disposition "resell" in the Health_Card disposition field for health_score greater than 90
2. WHEN Gate A routes an item to Gate B, THE Disposition_Router SHALL assign disposition "refurbish" in the Health_Card disposition field for health_score greater than 70 and less than or equal to 90
3. WHEN Gate A routes an item to Gate B, THE Disposition_Router SHALL assign disposition "donate" in the Health_Card disposition field for health_score greater than 50 and less than or equal to 70
4. WHEN Gate A routes an item to Gate B, THE Disposition_Router SHALL assign disposition "recycle" in the Health_Card disposition field for health_score less than or equal to 50
5. IF the health_score is unavailable or cannot be computed when Gate B is reached, THEN THE Disposition_Router SHALL assign disposition "recycle" as the default and record a flag in the Health_Card defects array indicating the score was unavailable
6. THE Disposition_Router SHALL complete the Gate B threshold evaluation and disposition assignment within 200 milliseconds of receiving the item from Gate A

### Requirement 15: P2P Fraud Divert Path

**User Story:** As the platform, I want to offer wardrobing customers a non-accusatory P2P resale option instead of rejecting the return, so that Amazon recovers value and avoids legal risk.

#### Acceptance Criteria

1. WHEN fraud_confidence is greater than or equal to 0.60 AND the product category is Clothing & Footwear, THE P2P_Divert_UI SHALL display an offer screen to the customer within 1 second of fraud aggregation completion, presenting the option to resell the item via P2P exchange without using language that implies fraud, theft, dishonesty, or accusation
2. WHEN the P2P_Divert_UI is displayed, THE P2P_Divert_UI SHALL present exactly two selectable choices: "Resell via ReLoop P2P" and "Proceed with standard return inspection"
3. WHEN the customer chooses P2P resale, THE System SHALL set the Health_Card source field to "p2p_fraud_divert" and set fraud_signal.p2p_offered to true and fraud_signal.customer_chose_p2p to true
4. WHEN the customer chooses standard return inspection, THE System SHALL proceed with the normal disposition flow (Gate A → Gate B), set fraud_signal.p2p_offered to true, set fraud_signal.customer_chose_p2p to false, and mark the item with an enhanced_inspection flag set to true in the Health_Card for warehouse processing
5. IF the customer does not select either choice within 30 minutes of the P2P_Divert_UI being displayed, THEN THE System SHALL treat the session as abandoned, set fraud_signal.p2p_offered to true, set fraud_signal.customer_chose_p2p to false, and proceed with the normal disposition flow (Gate A → Gate B) with the enhanced_inspection flag set to true
6. IF the product category is not Clothing & Footwear, THEN THE P2P_Divert_UI SHALL not be displayed and the item SHALL follow the normal disposition path regardless of fraud_confidence value

### Requirement 16: Graceful Degradation Without Social Accounts

**User Story:** As the platform, I want the system to function fully when a customer has no connected social accounts or the product category does not require fraud scanning, so that grading and disposition are never blocked.

#### Acceptance Criteria

1. IF the customer has no connected social accounts AND the product category is Clothing & Footwear, THEN THE System SHALL proceed with the full grading pipeline using only the Anomaly_Detector, Wear_Detector, and Intent_Classifier
2. IF the customer has no connected social accounts, THEN THE Fraud_Aggregator SHALL compute fraud_confidence from wear detection and behavioural signals only (Q&A inconsistency flags from the Intent_Classifier and wear_detection_penalty from the Wear_Detector), imposing no penalty for the absence of social data
3. IF the customer has no connected social accounts, THEN THE Health_Card fraud_signal block SHALL set social_scan_performed to false and product_found_in_social to false
4. IF the product category is not Clothing & Footwear, THEN THE System SHALL skip the Fraud_Scanner entirely and set fraud_signal.social_scan_performed to false with fraud_confidence derived from wear detection and behavioural signals only (Q&A inconsistency flags and wear_detection_penalty)
5. THE System SHALL apply identical disposition routing logic (Gate A economics check, Gate B health score thresholds, and the 0.60 fraud_confidence threshold for P2P divert) regardless of whether social accounts are connected or whether the Fraud_Scanner was executed
6. IF the customer has no connected social accounts OR the product category is not Clothing & Footwear, THEN THE System SHALL produce a Health_Card containing all required schema fields (condition, health_score, confidence, warranty_left_months, defects, anomaly_heatmap_uri, justification, disposition, source, and complete fraud_signal block) within the same 2-second processing budget as the full pipeline

### Requirement 17: Health Card Render Component

**User Story:** As a customer, I want to see my item's Health Card with a visual score breakdown, so that I trust the AI grading result.

#### Acceptance Criteria

1. WHEN a Health_Card is generated, THE System SHALL render a React Health Card component displaying: condition label, health score (integer 0–100), confidence percentage (integer 0–100 followed by "%"), defects list, anomaly heatmap image loaded from the stored URI, justification text, and disposition label
2. WHEN the Health Card component is rendered, THE System SHALL display a score-breakdown bar composed of four labeled proportional segments representing the weighted penalty contributions (w1·anomaly_severity, w2·defect_penalty, w3·return_reason_penalty, w4·wear_detection_penalty), each segment labeled with the penalty name and its numeric value rounded to one decimal place
3. WHEN the Health Card component is rendered, THE System SHALL display a "Certified by Amazon AI" badge positioned within the Health Card layout
4. IF the anomaly heatmap image fails to load from the stored URI, THEN THE System SHALL display a placeholder image with a text label indicating the heatmap is unavailable, and SHALL still render all other Health Card fields
5. IF the defects list in the Health_Card is empty, THEN THE System SHALL display a message indicating no defects were detected in place of the defects list

### Requirement 18: Integration Contract Stability

**User Story:** As the team building Modules 2–5, I want the Health Card JSON schema to remain stable, so that downstream consumers are never broken by Module 1 changes.

#### Acceptance Criteria

1. THE System SHALL output the Health_Card JSON containing all required fields (condition, health_score, confidence, warranty_left_months, defects, anomaly_heatmap_uri, justification, disposition, source, and fraud_signal block) with their documented types (string, number, number, number, array of strings, string, string, string, string, and object respectively) in every response
2. THE System SHALL never remove, rename, or change the data type of any existing field in the Health_Card schema — a field that was a string SHALL remain a string, a field that was a number SHALL remain a number, and a field that was an array SHALL remain an array
3. WHEN new fields are added to the Health_Card, THE System SHALL add them as optional fields with a default of null when absent, so that downstream consumers that do not read the new field continue to parse the Health_Card without error
4. IF a required Health_Card field cannot be populated due to a pipeline failure, THEN THE System SHALL still include the field in the output with a null value and SHALL set the confidence field to 0.0 to indicate an incomplete assessment

### Requirement 19: Category-Specific Disposition Overrides — Food & Grocery

**User Story:** As the platform, I want food items with broken seals, expired dates, or partial consumption to be automatically routed to dispose/recycle, so that safety is never compromised.

#### Acceptance Criteria

1. WHEN the product category is Food & Grocery AND the Q&A seal integrity answer is "No — seal broken or packaging opened" OR the Q&A quantity remaining answer is "Partially used" or "Mostly consumed", THE Disposition_Router SHALL set disposition to "recycle", overriding Gate A and Gate B logic regardless of health score
2. WHEN the product category is Food & Grocery AND the expiry date provided in Q&A is earlier than the date of return initiation, THE Disposition_Router SHALL set disposition to "recycle", overriding Gate A and Gate B logic regardless of health score
3. WHEN the product category is Food & Grocery AND the Q&A seal integrity answer is "Yes — completely sealed, never opened" AND the expiry date is on or after the date of return initiation AND the return reason is "Wrong item delivered", THE Disposition_Router SHALL set disposition to "return_to_seller"
4. WHEN the product category is Food & Grocery AND the item is sealed AND unexpired AND the return reason is not "Wrong item delivered", THE Disposition_Router SHALL proceed to Gate A and Gate B for standard disposition routing

### Requirement 20: Category-Specific Disposition Overrides — Safety and Hygiene

**User Story:** As the platform, I want items flagged with safety concerns or direct skin/body contact usage to be held for manual review or blocked from resale, so that consumer safety is protected.

#### Acceptance Criteria

1. WHEN the Q&A answers indicate a safety concern for any product category (Food & Grocery: return reason is "Allergic reaction / health concern"; Other: safety concern question answered "Minor concern" or "Yes — I believe this item is unsafe"; Electronics: liquid or impact damage history answered "Significant liquid damage" or "Dropped / impact damage"), THE Disposition_Router SHALL bypass all automatic disposition gates, set disposition to "manual_review", and place the item in a manual review queue
2. WHEN the product category is Other AND the Q&A skin/body contact question is answered "Yes — and it HAS been used on skin / body", THE Disposition_Router SHALL block the resell and refurbish paths and set disposition to "donate" if the physical condition answer is "Like new" or "Good", or set disposition to "recycle" if the physical condition answer is "Fair" or "Poor"
3. WHEN the product category is Electronics AND the Q&A factory reset question is answered "No — personal data still on device", THE Disposition_Router SHALL block all resale paths and set disposition to "manual_review" with a flag indicating factory reset is required before any resell or refurbish disposition is permitted
4. IF the product category is Electronics AND the Q&A factory reset question is answered "Not applicable for this product", THEN THE Disposition_Router SHALL not apply the factory reset hold and SHALL proceed with normal disposition routing

### Requirement 21: Q&A-to-Score Consistency Cross-Validation

**User Story:** As the platform, I want the system to detect inconsistencies between Q&A self-reported answers and CV-detected evidence, so that fraudulent self-reporting is caught.

#### Acceptance Criteria

1. WHEN the Q&A answers report "never used" or "tags attached" AND the Wear_Detector detects visible wear evidence (sole wear, fabric stress, stains), THE System SHALL escalate the fraud_confidence score by a configured penalty factor in the range 0.10 to 0.40 inclusive
2. WHEN the Q&A answers report "never used" AND the Anomaly_Detector produces an anomaly severity score above the configured like-new threshold (a category-specific numeric value on the anomaly severity scale), THE System SHALL add a defect entry indicating the Q&A-to-CV inconsistency to the Health_Card defects array
3. WHEN both Q&A-derived penalty values and CV-detected penalty values are available, THE System SHALL use the higher penalty value (more pessimistic signal) of the two as the authoritative input for health score calculation — where "higher" means the value that reduces the health score more
4. IF the Wear_Detector or Anomaly_Detector fails to produce a result while Q&A answers are available, THEN THE System SHALL compute the health score using only the available signals and SHALL NOT apply cross-validation escalation for the missing signal
