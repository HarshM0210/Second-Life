// Classifieds (seller) question sets — sourced from Questions.md.
//
// These are DISTINCT from the return-flow Q&A (which lives server-side in
// Module 1's QACollector and is shown by ReturnWizard). Sellers listing an item
// answer condition questions phrased for resale, not return reasons.
//
// Module 1's grading pipeline, however, still validates/scores against the
// RETURN question schema (return_reason, functional_status, …). To keep grading
// faithful without touching the return questions, `toGradingAnswers()` translates
// a seller's answers into a grade-compatible payload, and `deriveListingMeta()`
// pulls out the age / completeness / brand the Module 5 quote needs.

export type CQuestionKind = "radio" | "text";

export interface CQuestion {
  id: string;
  text: string;
  kind: CQuestionKind;
  options?: string[]; // for radio
  note?: string; // optional free-text placeholder shown under a radio question
  footwearOnly?: boolean; // clothing: sole/upper question
  optional?: boolean; // text questions that don't block submit
}

// Module 1 grading category -> seller question set.
export const CLASSIFIEDS_QUESTIONS: Record<string, CQuestion[]> = {
  Electronics: [
    {
      id: "ownership",
      text: "How long have you owned this product?",
      kind: "radio",
      options: ["Less than 1 month", "1–6 months", "6–12 months", "More than 1 year"],
    },
    {
      id: "functional",
      text: "How would you describe the functional condition?",
      kind: "radio",
      options: [
        "Works perfectly — all features functioning as new",
        "Works well — minor glitches that don't affect core use",
        "Works partially — some features not functioning",
        "Does not power on / non-functional",
      ],
    },
    {
      id: "physical",
      text: "What is the physical condition?",
      kind: "radio",
      options: [
        "Like new — no scratches, dents or marks",
        "Good — minor cosmetic marks only, no structural damage",
        "Fair — visible scratches or dents, fully functional",
        "Poor — significant damage visible",
      ],
    },
    {
      id: "accessories",
      text: "Are all original accessories included? (charger, cables, earphones, remote, manual, etc.)",
      kind: "radio",
      options: [
        "Yes — complete set, all original accessories present",
        "Mostly complete — minor accessories missing",
        "Partially complete — major accessories missing",
        "Item only — no accessories included",
      ],
      note: "List any missing accessories (optional)",
    },
    {
      id: "packaging",
      text: "Is the original box and packaging available?",
      kind: "radio",
      options: [
        "Yes — original box with all inserts and manuals",
        "Box only — inserts/manuals missing",
        "Third-party box only",
        "No packaging",
      ],
    },
    {
      id: "reset",
      text: "Has the device been factory reset and personal data removed?",
      kind: "radio",
      options: [
        "Yes — fully reset, ready for new owner",
        "Not yet — I will reset before handover",
        "Not applicable for this product",
      ],
    },
    {
      id: "repairs",
      text: "Is there any history of repairs or servicing?",
      kind: "radio",
      options: [
        "No repairs — never serviced",
        "Officially serviced at authorized centre",
        "Repaired at third-party shop",
        "Self-repaired",
      ],
    },
    {
      id: "warranty",
      text: "Is there any remaining warranty?",
      kind: "radio",
      options: [
        "Yes — manufacturer warranty still active",
        "Extended warranty / AMC active",
        "Warranty expired",
        "No warranty was included",
      ],
      note: "Approximate months remaining (optional)",
    },
    {
      id: "liquid",
      text: "Any history of liquid damage or major drops?",
      kind: "radio",
      options: [
        "No — never dropped or exposed to liquid",
        "Minor incident — no lasting damage",
        "Yes — there was an incident (reflected in condition above)",
      ],
    },
  ],

  "Clothing & Footwear": [
    {
      id: "worn",
      text: "How many times has this item been worn?",
      kind: "radio",
      options: ["Never worn — tags still attached", "Worn once", "Worn 2–5 times", "Worn regularly"],
    },
    {
      id: "tags",
      text: "Are all original tags still attached?",
      kind: "radio",
      options: [
        "Yes — all tags attached and intact",
        "Brand tag attached, size/care tags removed",
        "All tags removed",
      ],
    },
    {
      id: "washed",
      text: "Has the item been washed or dry cleaned?",
      kind: "radio",
      options: [
        "Never washed",
        "Washed once — as per care instructions",
        "Washed multiple times — as per care instructions",
        "Dry cleaned",
      ],
    },
    {
      id: "fabric",
      text: "What is the overall condition of the fabric / material?",
      kind: "radio",
      options: [
        "Excellent — no pilling, fading, or wear marks",
        "Good — very minor wear, not visible when worn",
        "Fair — some pilling, fading, or minor marks visible",
        "Poor — significant wear, stains, or damage",
      ],
    },
    {
      id: "staining",
      text: "Is there any visible staining, discolouration, or odour?",
      kind: "radio",
      options: [
        "None — completely clean and fresh",
        "Minor mark that is barely visible",
        "Visible stain or noticeable odour (reflected in price)",
      ],
    },
    {
      id: "footwear",
      text: "For footwear — what is the condition of the soles and upper?",
      kind: "radio",
      footwearOnly: true,
      options: [
        "Not applicable — this is not footwear",
        "Soles completely clean, upper pristine",
        "Minor sole wear, upper in good condition",
        "Moderate sole wear, some creasing on upper",
        "Significant sole wear or upper damage",
      ],
    },
    {
      id: "packaging",
      text: "Is the original packaging or dust bag available?",
      kind: "radio",
      options: ["Yes — original box / dust bag present", "Partial packaging only", "No original packaging"],
    },
    {
      id: "defects",
      text: "Are there any defects, damage, or alterations the buyer should know about?",
      kind: "radio",
      options: [
        "No defects — item is as originally purchased",
        "Minor defect (describe below)",
        "Item has been altered or tailored",
      ],
      note: "Describe any defects or alterations honestly (optional)",
    },
    {
      id: "size",
      text: "What size is this item?",
      kind: "text",
      optional: true,
      note: "e.g. M / 38 / EU 42 / UK 8 — include brand sizing if different from standard",
    },
    {
      id: "brand",
      text: "Which brand is this item?",
      kind: "text",
      optional: true,
      note: "Brand name",
    },
  ],

  Other: [
    {
      id: "ownership",
      text: "How long have you owned this item?",
      kind: "radio",
      options: ["Less than 1 month", "1–6 months", "6–12 months", "More than 1 year"],
    },
    {
      id: "usage",
      text: "How frequently was this item used?",
      kind: "radio",
      options: [
        "Never used — still in original packaging",
        "Used occasionally (a few times total)",
        "Used regularly for a short period",
        "Used heavily over a long period",
      ],
    },
    {
      id: "functional",
      text: "What is the current functional condition?",
      kind: "radio",
      options: [
        "Fully functional — works as new",
        "Mostly functional — minor issues that don't affect core use",
        "Partially functional — some features not working",
        "Non-functional",
      ],
    },
    {
      id: "physical",
      text: "What is the physical / cosmetic condition?",
      kind: "radio",
      options: [
        "Like new — no visible wear or marks",
        "Good — minor signs of use, nothing distracting",
        "Fair — visible wear, scratches, or marks",
        "Poor — significant cosmetic or structural damage",
      ],
    },
    {
      id: "parts",
      text: "Are all parts, components, and accessories included?",
      kind: "radio",
      options: [
        "Yes — complete as originally sold",
        "Mostly complete — minor items missing",
        "Significantly incomplete — major parts missing",
      ],
      note: "What is missing? (optional)",
    },
    {
      id: "packaging",
      text: "Is the original packaging available?",
      kind: "radio",
      options: ["Yes — original box / packaging intact", "Partial packaging", "No original packaging"],
    },
    {
      id: "skin",
      text: "Has this item ever come into direct contact with skin or body? (beauty tools, sports gear, baby products, personal care)",
      kind: "radio",
      options: [
        "No — never used on skin or body",
        "Yes — thoroughly cleaned and sanitised before listing",
        "Not applicable for this product",
      ],
    },
    {
      id: "safety",
      text: "Are there any safety concerns a buyer should be aware of?",
      kind: "radio",
      options: [
        "No safety concerns whatsoever",
        "Minor cosmetic issue only (described in defects)",
        "There is a safety concern",
      ],
      note: "Describe the safety concern (optional)",
    },
    {
      id: "repaired",
      text: "Has this item been repaired or modified in any way?",
      kind: "radio",
      options: [
        "No — as originally purchased",
        "Yes — officially repaired / serviced",
        "Yes — self-repaired or modified",
      ],
      note: "Describe the repair or modification (optional)",
    },
    {
      id: "itemDefects",
      text: "Are there any defects or damage the buyer should know about?",
      kind: "radio",
      options: [
        "No defects — item is in the condition described above",
        "Yes — minor defect (describe below)",
        "Yes — significant defect (describe below)",
      ],
      note: "Be specific — honest listings get better buyer reviews (optional)",
    },
  ],
};

// ---------------------------------------------------------------------------
// Translation: seller answers -> Module 1 return-schema qa_answers.
//
// Module 1 keeps its own (return) question schema; we map onto it so grading
// stays faithful. Values below are exact return-option phrases the intent
// classifier / disposition router recognise.
// ---------------------------------------------------------------------------

function pick<T>(arr: T[], idx: number, fallback: T): T {
  return idx >= 0 && idx < arr.length ? arr[idx] : fallback;
}

export function toGradingAnswers(
  m1Category: string,
  a: Record<string, string>,
  options: Record<string, string[]>,
): Record<string, string> {
  const idxOf = (id: string) => (options[id] ?? []).indexOf(a[id] ?? "");

  if (m1Category === "Electronics") {
    const fi = idxOf("functional"); // 0 perfect,1 minor,2 partial,3 dead
    const pi = idxOf("physical"); // 0 like-new..3 poor
    const ai = idxOf("accessories");
    const pki = idxOf("packaging");
    const ri = idxOf("reset"); // 0 yes,1 not yet,2 n/a
    const li = idxOf("liquid"); // 0 none,1 minor,2 incident
    const oi = idxOf("ownership");

    return {
      // Listing has no "return reason"; neutral baseline — condition fields carry severity.
      return_reason: "Changed my mind / no longer needed",
      functional_status: pick(
        [
          "Fully functional — works perfectly",
          "Fully functional — works perfectly",
          "Partially functional — some features not working",
          "Not functional — does not power on / completely broken",
        ],
        fi,
        "Fully functional — works perfectly",
      ),
      physical_condition: pick(
        [
          "No visible damage — mint condition",
          "Minor cosmetic damage (light scratches, small dents)",
          "Moderate damage (cracked casing, significant scratches)",
          "Severe damage (broken screen, crushed, burnt)",
        ],
        pi,
        "No visible damage — mint condition",
      ),
      accessories: pick(
        [
          "Yes — all accessories present",
          "Some accessories missing (specify below)",
          "Some accessories missing (specify below)",
          "No accessories included",
        ],
        ai,
        "Yes — all accessories present",
      ),
      original_packaging: pick(
        [
          "Yes — original box with all inserts",
          "Box only, inserts missing",
          "No original packaging",
          "No original packaging",
        ],
        pki,
        "Yes — original box with all inserts",
      ),
      // Map ownership -> usage duration; avoid "Never used" so we don't trip the
      // never-used-but-wear fraud inconsistency on a used listing.
      ownership_duration: pick(
        [
          "Used for 1–4 weeks",
          "Used for more than a month",
          "Used for more than a month",
          "Used for more than a month",
        ],
        oi,
        "Used for more than a month",
      ),
      // "Not yet, will reset" -> N/A to avoid the return-only data-privacy
      // manual_review hold; a listing isn't a privacy handover yet.
      factory_reset: pick(
        [
          "Yes — fully reset, personal data removed",
          "Not applicable for this product",
          "Not applicable for this product",
        ],
        ri,
        "Not applicable for this product",
      ),
      liquid_damage: pick(
        [
          "No — never exposed to liquid or impact",
          "Minor liquid exposure (spill, splash)",
          "Significant liquid damage (submerged, heavy exposure)",
        ],
        li,
        "No — never exposed to liquid or impact",
      ),
    };
  }

  if (m1Category === "Clothing & Footwear") {
    const wi = idxOf("worn"); // 0 never,1 once,2 2-5,3 regularly
    const ti = idxOf("tags"); // 0 all,1 size/care removed,2 all removed
    const wsi = idxOf("washed"); // 0 never,1 once,2 multiple,3 dry
    const fbi = idxOf("fabric"); // 0 excellent..3 poor
    const si = idxOf("staining"); // 0 none,1 minor,2 visible
    const fwi = idxOf("footwear"); // 0 n/a,1 clean..4 significant
    const pki = idxOf("packaging"); // 0 yes,1 partial,2 no
    const di = idxOf("defects"); // 0 none,1 minor,2 altered

    const out: Record<string, string> = {
      return_reason: "Changed my mind",
      wear_history: pick(
        [
          "Never worn — tags still attached",
          "Worn once outside",
          "Worn multiple times",
          "Worn multiple times",
        ],
        wi,
        "Tried on indoors only — not worn outside",
      ),
      tag_status: pick(
        ["Yes — all tags attached and intact", "Some tags removed", "All tags removed"],
        ti,
        "Yes — all tags attached and intact",
      ),
      washing_history: pick(
        ["No — not washed", "Yes — washed once", "Yes — washed multiple times", "Yes — washed once"],
        wsi,
        "No — not washed",
      ),
      staining_odour: pick(
        [
          "No — completely clean",
          "Minor — very faint mark or slight odour",
          "Yes — visible stain or noticeable odour",
        ],
        si,
        "No — completely clean",
      ),
      original_packaging: pick(
        ["Yes — original packaging intact", "Packaging damaged but present", "No original packaging"],
        pki,
        "Yes — original packaging intact",
      ),
      // physical_damage from fabric condition + declared defects (most severe wins).
      physical_damage:
        fbi === 3
          ? "Significant damage (torn, broken fastening)"
          : di >= 1
            ? "Minor damage (loose thread, small snag)"
            : "No damage",
    };

    // Sole condition only when footwear was actually answered (index 1+).
    if (fwi >= 1) {
      out.sole_condition = pick(
        [
          "Completely clean — no sole wear",
          "Minor dirt but no structural wear",
          "Visible sole wear or scuffing",
          "Significant wear — clearly used outdoors",
        ],
        fwi - 1,
        "Completely clean — no sole wear",
      );
    }
    return out;
  }

  // Other
  const ui = idxOf("usage"); // 0 never,1 occasionally,2 regularly,3 heavily
  const fi = idxOf("functional"); // 0 full..3 non
  const pi = idxOf("physical"); // 0 like-new..3 poor
  const pai = idxOf("parts"); // 0 complete,1 mostly,2 significantly
  const pki = idxOf("packaging"); // 0 yes,1 partial,2 no
  const ski = idxOf("skin"); // 0 no,1 cleaned,2 n/a
  const sfi = idxOf("safety"); // 0 none,1 minor,2 concern

  const physical = pick(
    [
      "Like new — no marks or damage",
      "Good — minor signs of use, fully functional",
      "Fair — visible wear but functional",
      "Poor — significant damage or non-functional",
    ],
    pi,
    "Like new — no marks or damage",
  );

  return {
    return_reason: sfi === 2 ? "Safety concern" : "Changed my mind / no longer needed",
    usage_extent: pick(
      [
        "Never used — completely unused",
        "Used once or twice",
        "Used regularly for a short period",
        "Used extensively",
      ],
      ui,
      "Used once or twice",
    ),
    // Non-functional overrides cosmetic condition.
    physical_condition: fi === 3 ? "Poor — significant damage or non-functional" : physical,
    parts_completeness: pick(
      ["Yes — complete as originally received", "Some parts missing (specify below)", "Significantly incomplete"],
      pai,
      "Yes — complete as originally received",
    ),
    original_packaging: pick(
      ["Yes — original box/packaging intact", "Partial packaging only", "No original packaging"],
      pki,
      "Yes — original box/packaging intact",
    ),
    // "Cleaned & sanitised" -> treat as not-on-skin so a sanitised item isn't
    // force-routed to donate by the skin-contact category override.
    skin_contact: pick(
      ["No", "Yes — and it has NOT been used on skin", "No"],
      ski,
      "No",
    ),
    safety_concern: pick(
      ["No safety concerns", "Minor concern (describe in notes)", "Yes — I believe this item is unsafe"],
      sfi,
      "No safety concerns",
    ),
    hygiene_concerns: ski === 1 ? "Item has been cleaned and sanitised" : "No hygiene concerns",
  };
}

// Derive the listing/quote metadata the seller's answers imply.
export function deriveListingMeta(
  m1Category: string,
  a: Record<string, string>,
  options: Record<string, string[]>,
): { ageMonths: number; hasBox: boolean; accessoriesComplete: boolean; brand?: string } {
  const idxOf = (id: string) => (options[id] ?? []).indexOf(a[id] ?? "");

  // Age from the ownership/usage tenure question (ranges -> representative months).
  const ownIdx = idxOf("ownership");
  const ageByOwnership = [0, 3, 9, 18]; // <1mo, 1–6, 6–12, >1yr
  const ageMonths = ownIdx >= 0 ? ageByOwnership[ownIdx] : 6;

  // Packaging present unless the seller picked the explicit "No packaging" option.
  const pkgOpts = options["packaging"] ?? [];
  const pkgAns = a["packaging"] ?? "";
  const hasBox = pkgAns ? !/^no\b/i.test(pkgAns.trim()) && pkgIdxHasBox(pkgOpts, pkgAns) : true;

  // Accessories/parts completeness.
  let accessoriesComplete = true;
  if (m1Category === "Electronics") accessoriesComplete = idxOf("accessories") <= 0;
  else if (m1Category === "Other") accessoriesComplete = idxOf("parts") <= 0;

  const brand = m1Category === "Clothing & Footwear" ? (a["brand"]?.trim() || undefined) : undefined;

  return { ageMonths, hasBox, accessoriesComplete, brand };
}

function pkgIdxHasBox(opts: string[], ans: string): boolean {
  // Last option in each packaging set is the "No packaging" choice.
  const i = opts.indexOf(ans);
  if (i < 0) return true;
  return i < opts.length - 1;
}
