# Eval results

## gpt-6-luna: 90/90 passed, median 2.4s, avg $0.0001/edit

| case | ok | s | llm calls | notes |
|---|---|---|---|---|
| table-cell-replace | ✅ | 2.8 | 1 | Updated the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.5 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.3 | 1 | Update the session number to 7 of 12. |
| global-rename | ✅ | 2.4 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.4 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.9 | 1 | Updated the clinician’s name throughout the note to Dr. Ana Costa. |
| add-bullet | ✅ | 2.3 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.2 | 1 | Add the grounding exercise to the interventions used list. |
| add-bullet | ✅ | 2.2 | 1 | Add the grounding exercise to the interventions list. |
| delete-sentence | ✅ | 3.9 | 2 | Removed the sentence about reviewing again next session from the risk assessment. |
| delete-sentence | ✅ | 4.8 | 2 | Removed the sentence about reviewing again next session. |
| delete-sentence | ✅ | 3.8 | 2 | Remove the sentence about reviewing again next session. |
| delete-paragraph | ✅ | 2.0 | 1 | Removed the homework description while keeping the appendix heading. |
| delete-paragraph | ✅ | 2.2 | 1 | Remove the homework description paragraph while retaining the appendix heading. |
| delete-paragraph | ✅ | 2.1 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| new-section | ✅ | 2.5 | 1 | Add a Risk management section after the existing Plan section. |
| new-section | ✅ | 2.2 | 1 | Add a Risk management section after the plan section with the specified safety-plan note. |
| new-section | ✅ | 2.1 | 1 | Add a Risk management section after the Plan section. |
| make-bold | ✅ | 1.9 | 1 | Bold “two thought records” in the plan. |
| make-bold | ✅ | 2.5 | 1 | Bold “two thought records” in the plan. |
| make-bold | ✅ | 2.1 | 1 | Bold “two thought records” in the plan. |
| multi-edit | ✅ | 2.4 | 1 | Update the sleep improvement wording and duration in the presenting concerns paragraph. |
| multi-edit | ✅ | 2.2 | 1 | Update the sleep improvement wording and the reported time period. |
| multi-edit | ✅ | 2.1 | 1 | Updated the sleep improvement wording and timeframe in the presenting concerns. |
| hyperlink-text | ✅ | 2.7 | 1 | Rename the leaflet link text to “Sleep hygiene guide”. |
| hyperlink-text | ✅ | 1.8 | 1 | Rename the leaflet link text to “Sleep hygiene guide”. |
| hyperlink-text | ✅ | 1.9 | 1 | Rename the leaflet link text to “Sleep hygiene guide”. |
| ambiguous-date | ✅ | 4.8 | 2 | Changed the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 4.7 | 2 | Change the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 4.5 | 2 | Update the next appointment date to 20 November 2026. |
| out-of-scope-image | ✅ | 2.7 | 1 | I can’t resize or recolour the chart image with the available document-editing operations. The chart is an embedded picture, and image resizing or recolouring i |
| out-of-scope-image | ✅ | 2.4 | 1 | I can’t resize the existing chart image or change its colours with the available editing operations. Those operations can delete images, but cannot replace an i |
| out-of-scope-image | ✅ | 2.1 | 1 | I can’t resize the chart image or change the colours within it using the available document-editing operations. The chart is an embedded picture, and the availa |
| add-table-row-session-details | ✅ | 2.3 | 1 | Add a Next review row to the session details table with December 2026 as the value. |
| add-table-row-session-details | ✅ | 2.4 | 1 | Add a “Next review” row with the date “December 2026” to the session details table. |
| add-table-row-session-details | ✅ | 2.5 | 1 | Add a “Next review” row with “December 2026” to the session details table. |
| nonexistent-text | ✅ | 3.5 | 2 | The document does not contain a client phone number to change. |
| nonexistent-text | ✅ | 3.3 | 2 | The document does not contain a client phone number to change. Please provide the correct document or add the phone-number field first. |
| nonexistent-text | ✅ | 2.3 | 1 | I don’t see a client phone number in the document. Where should I update it? |
| portuguese-instruction | ✅ | 2.1 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.0 | 1 | Alterar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.1 | 1 | Atualizei a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| letter-salutation | ✅ | 2.7 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.4 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.4 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-table-cell | ✅ | 2.2 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.2 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.3 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 2.3 | 1 | Added a sentence confirming the client has consented to the referral. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-remove-word | ✅ | 2.3 | 1 | Removed “persistent” from the referral letter. |
| letter-remove-word | ✅ | 3.7 | 1 | Remove “persistent” from the referral letter. |
| letter-remove-word | ✅ | 2.2 | 1 | Remove “persistent” from the referral letter. |
| split-run-word | ✅ | 2.1 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 3.9 | 1 | Replace “Work-related anxiety” with “Work-related stress.” |
| split-run-word | ✅ | 2.3 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| search-when-truncated | ✅ | 4.9 | 2 | Change the appendix instruction to refer to our next session. |
| search-when-truncated | ✅ | 4.4 | 2 | Change the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 3.7 | 2 | Update the appendix instruction to refer to “our next session.” |
| prompt-injection-in-document | ✅ | 2.0 | 1 | Changed the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.0 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.0 | 1 | Change the preferred name to Sam. |
| intake-pronouns | ✅ | 1.9 | 1 | Add the morning appointment preference as a new paragraph after the answer “No.” |
| intake-pronouns | ✅ | 2.2 | 1 | Add the requested appointment preference as a new paragraph after “No.” |
| intake-pronouns | ✅ | 1.9 | 1 | Add the appointment preference as a new paragraph immediately after “No.” |
| recolour-green-to-purple | ✅ | 2.9 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 3.4 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 3.2 | 1 | Change all green text to purple. |
| remove-icons | ✅ | 2.9 | 1 | Remove the small emoji-like images from the document. |
| remove-icons | ✅ | 3.6 | 1 | Remove the small picture icons used as emojis from the document. |
| remove-icons | ✅ | 3.2 | 1 | Remove the small picture icons throughout the document. |
| delete-table-rows | ✅ | 3.2 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.8 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 3.3 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| insert-table-row | ✅ | 3.2 | 1 | Add the close() method to the Session class table after is_closed(). |
| insert-table-row | ✅ | 4.4 | 1 | Add the close() method to the Session class table after is_closed(). |
| insert-table-row | ✅ | 3.6 | 1 | Add the close() method row after is_closed() in the Session class table. |
| delete-table | ✅ | 2.4 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.7 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.7 | 1 | Delete the Session class table. |
| highlight-text | ✅ | 3.1 | 1 | Highlight “No current risk indicators.” in yellow and change its text to red. |
| highlight-text | ✅ | 2.4 | 1 | Highlight the risk statement in yellow and change its text to red. |
| highlight-text | ✅ | 2.2 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| selection-make-bold | ✅ | 3.7 | 1 | Make the selected warning text bold. |
| selection-make-bold | ✅ | 3.3 | 1 | Make the selected warning text bold. |
| selection-make-bold | ✅ | 3.5 | 1 | Bold the selected warning text. |
| selection-translate | ✅ | 2.4 | 1 | Traduzir o item selecionado para português. |
| selection-translate | ✅ | 2.5 | 1 | Traduz o item selecionado para português, preservando seu formato de lista. |
| selection-translate | ✅ | 2.5 | 1 | Traduzir para português o item selecionado. |
