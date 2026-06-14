# Structured Q&A — Per Category Design

The questions serve two masters simultaneously:
- **The AI grader** — feeding `return_reason_penalty` and `wear_detection_penalty` inputs
- **The fraud detector** — surfacing wardrobing signals per category

---

## Category 1 — Food & Grocery

**Unique challenge:** Condition can't be assessed visually the same way. Safety and expiry are the primary signals. Wardrobing doesn't apply. Most food returns are either damaged in transit or wrong item.

### Features the model needs

| Feature | Signal it provides |
|---|---|
| Expiry date at time of return | Safety disposition — expired = recycle/dispose only |
| Packaging integrity | Damaged in transit vs tampered |
| Seal status | Opened = cannot resell under any circumstances |
| Storage compliance | Was it refrigerated if required? Affects safety |
| Reason category | Wrong item / damaged / quality issue / allergic reaction |
| Quantity remaining | Partially consumed = automatic dispose |

### Questions

```
1. What is the reason for your return?
   ○ Wrong item delivered
   ○ Item damaged during delivery
   ○ Item expired or near expiry
   ○ Quality not as expected
   ○ Allergic reaction / health concern
   ○ Other

2. Is the original packaging seal intact?
   ○ Yes — completely sealed, never opened
   ○ No — seal broken or packaging opened

3. What is the current state of the packaging?
   ○ Fully intact, no damage
   ○ Minor damage (dents, small tears) but contents unaffected
   ○ Significant damage — contents may be compromised
   ○ Leaking or crushed

4. Has the item been stored as per instructions?
   (e.g. refrigerated, kept dry, away from sunlight)
   ○ Yes, stored correctly throughout
   ○ No — storage conditions not met
   ○ Unsure

5. What is the expiry date on the product?
   [Date picker]

6. How much of the product remains?
   ○ 100% — completely unused
   ○ Partially used
   ○ Mostly consumed
```

### Disposition logic food unlocks

```
Seal broken OR partially consumed  → Recycle/Dispose (non-negotiable)
Expired                            → Recycle/Dispose
Wrong item + sealed + unexpired    → Return to Seller
Damaged packaging + sealed + unexpired → Donate (food banks) if safe
```

### Images/video guidance for food
- Photo of seal/packaging integrity
- Photo of expiry date label
- Photo of any damage to outer packaging
- Video: rotate product showing all sides

---

## Category 2 — Electronics

**Unique challenge:** Functional condition matters as much as physical. A visually perfect device may be functionally dead. Accessories completeness affects resale value significantly.

### Features the model needs

| Feature | Signal it provides |
|---|---|
| Functional status | Working = resell/refurbish, dead = recycle |
| Physical damage type | Cosmetic vs structural vs screen damage |
| Accessories completeness | Missing charger/cable = lower health score |
| Original packaging present | Affects resale grade significantly |
| Purchase date / warranty left | Determines refurb vs return to seller viability |
| Usage duration | Wardrobing signal — "never used" + wear detected = fraud |
| Reset status | Data privacy — unreset device cannot be resold |
| Reason category | Defective / not as described / changed mind / compatibility |

### Questions

```
1. What is the reason for your return?
   ○ Item is defective / not working
   ○ Item not as described in listing
   ○ Compatibility issue (wrong model/version)
   ○ Changed my mind / no longer needed
   ○ Received wrong item
   ○ Physical damage on arrival

2. Is the item currently functional?
   ○ Fully functional — works perfectly
   ○ Partially functional — some features not working
   ○ Not functional — does not power on / completely broken

3. Describe the physical condition:
   ○ No visible damage — mint condition
   ○ Minor cosmetic damage (light scratches, small dents)
   ○ Moderate damage (cracked casing, significant scratches)
   ○ Severe damage (broken screen, crushed, burnt)

4. Are all original accessories included?
   (charger, cables, earphones, remote, manual, etc.)
   ○ Yes — all accessories present
   ○ Some accessories missing (specify below)
   ○ No accessories included
   [Text field: Which accessories are missing?]

5. Is the original packaging available?
   ○ Yes — original box with all inserts
   ○ Box only, inserts missing
   ○ No original packaging

6. How long have you owned and used this item?
   ○ Never used — still in original packaging
   ○ Used briefly (less than a week)
   ○ Used for 1–4 weeks
   ○ Used for more than a month

7. Has the device been factory reset?
   (for phones, tablets, laptops, smart devices)
   ○ Yes — fully reset, personal data removed
   ○ No — personal data still on device
   ○ Not applicable for this product

8. Is there any liquid or physical damage history?
   ○ No — never exposed to liquid or impact
   ○ Minor liquid exposure (spill, splash)
   ○ Significant liquid damage (submerged, heavy exposure)
   ○ Dropped / impact damage
```

### Disposition logic electronics unlocks

```
Not functional + severe damage              → Recycle
Not functional + minor damage               → Refurbish (if cost < value)
Fully functional + complete + original box  → Resell as Renewed
Fully functional + missing accessories      → Refurbish tier (repackage)
Unreset device                              → Flag: must reset before any resale path
```

### Images/video guidance for electronics
- Photo of all four sides of device
- Photo of screen (on and off)
- Photo of all ports and connectors
- Photo of accessories laid out
- Video: power on/off demonstration + key function demo (screen, buttons, camera)
- Photo of serial number / IMEI label

---

## Category 3 — Clothing & Footwear

**Unique challenge:** This is your highest wardrobing risk category. The fraud detection layer is most critical here. Physical wear evidence is the primary signal. Size/fit issues are legitimate but easily faked.

### Features the model needs

| Feature | Signal it provides |
|---|---|
| Wear evidence | Primary wardrobing signal |
| Tag status | Removed tags = strong fraud indicator |
| Washing history | Washed = definitely worn |
| Occasion of use (if admitted) | Feeds P2P divert offer |
| Fit issue specificity | Genuine size problem vs excuse |
| Stain / odour presence | Wear evidence for grader |
| Purchase-to-return timeline | Fast fashion fraud signal |
| Original packaging | Authenticity and resale grade |

### Questions

```
1. What is the reason for your return?
   ○ Wrong size — too small
   ○ Wrong size — too large
   ○ Style / colour not as shown in images
   ○ Quality not as expected (fabric, stitching)
   ○ Item damaged on arrival
   ○ Received wrong item
   ○ Changed my mind

2. Have you worn or tried on this item?
   ○ Never worn — tags still attached
   ○ Tried on indoors only — not worn outside
   ○ Worn once outside
   ○ Worn multiple times

3. Are all original tags still attached?
   ○ Yes — all tags attached and intact
   ○ Some tags removed
   ○ All tags removed

4. Has the item been washed or dry cleaned?
   ○ No — not washed
   ○ Yes — washed once
   ○ Yes — washed multiple times

5. Is there any visible staining, marking, or odour?
   ○ No — completely clean
   ○ Minor — very faint mark or slight odour
   ○ Yes — visible stain or noticeable odour

6. Is the original packaging / polybag present?
   ○ Yes — original packaging intact
   ○ Packaging damaged but present
   ○ No original packaging

7. For footwear only — what is the condition of the soles?
   ○ Completely clean — no sole wear
   ○ Minor dirt but no structural wear
   ○ Visible sole wear or scuffing
   ○ Significant wear — clearly used outdoors

8. Does the item have any physical damage?
   (torn seams, broken zip, missing buttons, etc.)
   ○ No damage
   ○ Minor damage (loose thread, small snag)
   ○ Significant damage (torn, broken fastening)
```

### Disposition logic clothing unlocks

```
Tags removed + worn outside + washed        → High fraud confidence → P2P divert offer
Never worn + tags attached + original pkg   → Resell as New
Tried on indoors + tags attached            → Resell as Renewed (light grade)
Worn once + no damage + tags removed        → Refurbish (repackage) or P2P
Stained / damaged                           → Donate if wearable, Recycle if not
```

### Images/video guidance for clothing
- Front and back flat lay photo
- Close-up of all tags (attached or detached)
- Close-up of any stains, damage, or wear marks
- Photo of original packaging
- For footwear: photo of both soles clearly
- Video: slow pan of full item showing overall condition

---

## Category 4 — Other

**The catch-all category** — furniture, books, toys, sports equipment, beauty, home appliances, stationery etc. Questions need to be generic enough to work across all but still extract the key signals.

### Features the model needs

| Feature | Signal it provides |
|---|---|
| Usage extent | Primary condition signal |
| Physical damage | Grader input |
| Completeness (parts/pieces) | Critical for toys, furniture, appliances |
| Original packaging | Resale grade |
| Safety concern flag | Especially for toys, baby products |
| Hygiene status | For beauty, personal care, baby items |
| Reason category | Determines penalty weight |
| Age of product | Combined with usage for wear estimation |

### Questions

```
1. What is the reason for your return?
   ○ Item defective or not working
   ○ Item not as described
   ○ Wrong item received
   ○ Missing parts or accessories
   ○ Changed my mind / no longer needed
   ○ Safety concern
   ○ Item damaged on arrival

2. How would you describe your usage of this item?
   ○ Never used — completely unused
   ○ Used once or twice
   ○ Used regularly for a short period
   ○ Used extensively

3. What is the physical condition of the item?
   ○ Like new — no marks or damage
   ○ Good — minor signs of use, fully functional
   ○ Fair — visible wear but functional
   ○ Poor — significant damage or non-functional

4. Are all parts, components, and accessories included?
   ○ Yes — complete as originally received
   ○ Some parts missing (specify below)
   ○ Significantly incomplete
   [Text field: Which parts are missing?]

5. Is the original packaging available?
   ○ Yes — original box/packaging intact
   ○ Partial packaging only
   ○ No original packaging

6. Does this item involve direct skin or body contact?
   (beauty, personal care, baby products, sports gear)
   ○ No
   ○ Yes — and it has NOT been used on skin
   ○ Yes — and it HAS been used on skin / body

7. Is there any safety concern with this item?
   ○ No safety concerns
   ○ Minor concern (describe in notes)
   ○ Yes — I believe this item is unsafe
   [Text field: Please describe the safety concern]

8. Are there any hygiene concerns?
   (relevant for baby products, personal care, sports equipment)
   ○ No hygiene concerns
   ○ Item has been cleaned and sanitised
   ○ Item may have hygiene issues
```

### Disposition logic Other unlocks

```
Used on skin/body                           → Cannot resell → Donate or Recycle
Safety concern flagged                      → Hold for manual review (never auto-resell)
Missing parts                               → Refurbish path or Donate
Never used + complete + original packaging  → Resell
Significant damage                          → Recycle if uneconomic to repair
```

### Images/video guidance for Other
- Overall product photo from multiple angles
- Close-up of any damage or wear
- All parts/accessories laid out together
- Serial number or batch code if present
- Video: demonstrate functionality if applicable (appliances, toys, sports equipment)

---

## How These Feed the Grader Model

Every question maps to a penalty or bonus in the health score formula:

```
return_reason_penalty:
  "defective/broken" answers          → high penalty   (0.25 - 0.35)
  "wrong size / changed mind"         → low penalty    (0.05 - 0.10)
  "not as described"                  → medium penalty (0.15)

wear_detection_penalty:
  "worn multiple times" +
  "tags removed" +
  "washed"                            → high wear signal (cross-validates CV output)

  "never used" + CV detects wear      → fraud flag escalation

safety_hold_flag:
  Any safety concern answer           → bypass all disposition gates
                                      → mandatory manual review queue

hygiene_flag:
  Used on skin/body                   → block resell path entirely

completeness_penalty:
  Missing parts                       → reduce health score by 10–20 pts
                                      → route to refurbish not resell
```

---

## Q&A to Health Score Mapping Summary

| Category | Key fraud signal | Key grader signal | Auto-block trigger |
|---|---|---|---|
| Food | N/A | Seal broken / expiry date | Opened seal / consumed |
| Electronics | "Never used" + CV wear mismatch | Functional status + accessories | Unreset device / safety issue |
| Clothing | Tags removed + worn outside + washed | Wear evidence + damage | Washed + stained |
| Other | Heavy use + skin contact | Completeness + condition | Safety concern / hygiene issue |
