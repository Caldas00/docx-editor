# Example runs

Generated with `scripts/make_examples.py` (model `gpt-5.5`).

## session_note.docx

**Instruction:** The clinician is now Dr. Ana Costa - update her name everywhere. Also change the session number to 7 of 12 and add 'Grounding exercise (5-4-3-2-1)' as another intervention used.

**Result:** Updated the clinician name throughout, changed the session number, and added the new grounding exercise to the interventions list.  
Input: `samples/input/session_note.docx` → output: `samples/output/session_note.edited.docx` · plan: `samples/output/session_note.plan.json`

| change | block | before | after |
|---|---|---|---|
| replace_text | `p21` | Clinician signature:	Dr. Maya Ferreira Registration no. PSY-00000 (synthetic) | Clinician signature:	Dr. Ana Costa Registration no. PSY-00000 (synthetic) |
| replace_text | `p1` | Prepared by Dr. Maya Ferreira, Clinical Psychologist · Generated on 17 November 2026 | Prepared by Dr. Ana Costa, Clinical Psychologist · Generated on 17 November 2026 |
| replace_text | `t0.r2.c1.p0` | 6 of 12 | 7 of 12 |
| insert_paragraph | `new1` |  | Grounding exercise (5-4-3-2-1) |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, headers/footers, media and all other parts untouched — 22 parts copied byte-for-byte
- ✅ Block structure matches the plan — 39 blocks
- ✅ Untouched blocks are XML-identical — 35 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 127 original characters checked
- ✅ New paragraphs copy their template's formatting — 1 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 images, 1 tables, 1 hyperlinks, 1 fields, 3 comment anchors, 1 section breaks
- ✅ OOXML structure rules hold

## referral_letter.docx

**Instruction:** Address the letter to Dr. Rui Almeida, change the anxiety status in the summary table from Moderate to Mild, and remove the word 'persistent'.

**Result:** Updated the addressee, anxiety status, and removed “persistent” from the body text.  
Input: `samples/input/referral_letter.docx` → output: `samples/output/referral_letter.edited.docx` · plan: `samples/output/referral_letter.plan.json`

| change | block | before | after |
|---|---|---|---|
| replace_text | `p7` | Dear Dr. Almeida, | Dear Dr. Rui Almeida, |
| replace_text | `t0.r2.c1.p0` | Moderate | Mild |
| delete_text | `p9` | Although the client has made good progress with sleep, persistent physical symptoms of anxiety are affecting daily functioning. I would be grateful for your opinion on whether a medication review would be appropriate. | Although the client has made good progress with sleep, physical symptoms of anxiety are affecting daily functioning. I would be grateful for your opinion on whether a medication review would be appropriate. |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, headers/footers, media and all other parts untouched — 19 parts copied byte-for-byte
- ✅ Block structure matches the plan — 30 blocks
- ✅ Untouched blocks are XML-identical — 27 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 206 original characters checked
- ✅ New paragraphs copy their template's formatting — 0 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 tables, 1 section breaks
- ✅ OOXML structure rules hold

## intake_form.docx

**Instruction:** Change the preferred name to Sam.

**Result:** Updated the preferred name to Sam.  
Input: `samples/input/intake_form.docx` → output: `samples/output/intake_form.edited.docx` · plan: `samples/output/intake_form.plan.json`

| change | block | before | after |
|---|---|---|---|
| replace_text | `t0.r1.c1.p0` | Alex | Sam |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, headers/footers, media and all other parts untouched — 16 parts copied byte-for-byte
- ✅ Block structure matches the plan — 21 blocks
- ✅ Untouched blocks are XML-identical — 20 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 0 original characters checked
- ✅ New paragraphs copy their template's formatting — 0 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 tables, 1 section breaks
- ✅ OOXML structure rules hold
