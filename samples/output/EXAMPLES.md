# Example runs

Generated with `scripts/make_examples.py` (model `gpt-6-luna`).

## session_note.docx

**Instruction:** The clinician is now Dr. Ana Costa - update her name everywhere. Also change the session number to 7 of 12 and add 'Grounding exercise (5-4-3-2-1)' as another intervention used.

**Result:** Update the clinician name throughout, set the session number to 7 of 12, and add the grounding exercise intervention.  
1 LLM call(s), 4631 input tokens, about $0.0001  
Input: `samples/input/session_note.docx` → output: `samples/output/session_note.edited.docx` · plan: `samples/output/session_note.plan.json`

| change | block | before | after |
|---|---|---|---|
| replace_text | `p21` | Clinician signature:	Dr. Maya Ferreira Registration no. PSY-00000 (synthetic) | Clinician signature:	Dr. Ana Costa Registration no. PSY-00000 (synthetic) |
| replace_text | `p1` | Prepared by Dr. Maya Ferreira, Clinical Psychologist · Generated on 17 November 2026 | Prepared by Dr. Ana Costa, Clinical Psychologist · Generated on 17 November 2026 |
| replace_text | `t0.r2.c1.p0` | 6 of 12 | 7 of 12 |
| insert_paragraph | `new1` |  | Grounding exercise (5-4-3-2-1) |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, media, metadata and other parts untouched — 22 parts copied byte-for-byte
- ✅ Block structure matches the plan — 54 blocks
- ✅ Untouched blocks are XML-identical — 50 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 127 original characters checked
- ✅ New paragraphs and rows copy their template's formatting — 1 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 images, 1 tables, 1 hyperlinks, 1 fields, 3 comment anchors, 1 section breaks
- ✅ OOXML structure rules hold

## referral_letter.docx

**Instruction:** Address the letter to Dr. Rui Almeida, change the anxiety status in the summary table from Moderate to Mild, and remove the word 'persistent'.

**Result:** Address the letter to Dr. Rui Almeida, change the anxiety status to Mild, and remove “persistent.”  
1 LLM call(s), 4303 input tokens, about $0.0001  
Input: `samples/input/referral_letter.docx` → output: `samples/output/referral_letter.edited.docx` · plan: `samples/output/referral_letter.plan.json`

| change | block | before | after |
|---|---|---|---|
| replace_text | `p7` | Dear Dr. Almeida, | Dear Dr. Rui Almeida, |
| replace_text | `t0.r2.c1.p0` | Moderate | Mild |
| delete_text | `p9` | Although the client has made good progress with sleep, persistent physical symptoms of anxiety are affecting daily functioning. I would be grateful for your opinion on whether a medication review would be appropriate. | Although the client has made good progress with sleep, physical symptoms of anxiety are affecting daily functioning. I would be grateful for your opinion on whether a medication review would be appropriate. |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, media, metadata and other parts untouched — 19 parts copied byte-for-byte
- ✅ Block structure matches the plan — 46 blocks
- ✅ Untouched blocks are XML-identical — 43 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 206 original characters checked
- ✅ New paragraphs and rows copy their template's formatting — 0 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 tables, 1 section breaks
- ✅ OOXML structure rules hold

## intake_form.docx

**Instruction:** Change the preferred name to Sam.

**Result:** Change the preferred name from Alex to Sam.  
1 LLM call(s), 4155 input tokens, about $0.0001  
Input: `samples/input/intake_form.docx` → output: `samples/output/intake_form.edited.docx` · plan: `samples/output/intake_form.plan.json`

| change | block | before | after |
|---|---|---|---|
| replace_text | `t0.r1.c1.p0` | Alex | Sam |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, media, metadata and other parts untouched — 16 parts copied byte-for-byte
- ✅ Block structure matches the plan — 33 blocks
- ✅ Untouched blocks are XML-identical — 32 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 0 original characters checked
- ✅ New paragraphs and rows copy their template's formatting — 0 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 tables, 1 section breaks
- ✅ OOXML structure rules hold

## api_reference.docx

**Instruction:** Make all the green text purple, remove the emojis, and remove the set_date and set_modality rows from the Session class table.

**Result:** Turn green text purple, remove the small emoji images, and delete the two setter rows from the Session class table.  
1 LLM call(s), 4801 input tokens, about $0.0001  
Input: `samples/input/api_reference.docx` → output: `samples/output/api_reference.edited.docx` · plan: `samples/output/api_reference.plan.json`

| change | block | before | after |
|---|---|---|---|
| restyle_text | `p1` | Note: this reference is generated from synthetic data. | Note: this reference is generated from synthetic data. (color=#7030A0) |
| restyle_text | `p14` | Tip: prefer get_date() over parsing the raw JSON. | Tip: prefer get_date() over parsing the raw JSON. (color=#7030A0) |
| delete_images | `p3` | #include <notes/sdk.hpp>                ⟦IMAGE#1⟧ | #include <notes/sdk.hpp>                 |
| delete_images | `p4` | using namespace notes;                  ⟦IMAGE#2⟧ | using namespace notes;                   |
| delete_images | `p5` | session_reader reader;                  ⟦IMAGE#3⟧ | session_reader reader;                   |
| delete_images | `p6` | reader.load("session.json");            ⟦IMAGE#4⟧ | reader.load("session.json");             |
| delete_images | `p7` | ⟦IMAGE#5⟧ - Include the SDK header |  - Include the SDK header |
| delete_images | `p8` | ⟦IMAGE#6⟧ - Use the SDK namespace |  - Use the SDK namespace |
| delete_images | `p9` | ⟦IMAGE#7⟧ - Create a reader |  - Create a reader |
| delete_images | `p10` | ⟦IMAGE#8⟧ - Load a session file |  - Load a session file |
| delete_table_row | `t0.r4` | void / set_date(Date d) / Sets the session date. |  |
| delete_table_row | `t0.r6` | void / set_modality(Modality m) / Sets the therapy modality. |  |

Verification:

- ✅ Output is a valid .docx — re-opened with lxml and python-docx
- ✅ Styles, media, metadata and other parts untouched — 20 parts copied byte-for-byte
- ✅ Block structure matches the plan — 60 blocks
- ✅ Untouched blocks are XML-identical — 50 blocks compared
- ✅ Edited text matches the plan exactly
- ✅ Formatting preserved in edited paragraphs — 352 original characters checked
- ✅ New paragraphs and rows copy their template's formatting — 0 new paragraph(s)
- ✅ Images, tables, links, fields, bookmarks, sections preserved — 1 tables, 1 section breaks
- ✅ OOXML structure rules hold
