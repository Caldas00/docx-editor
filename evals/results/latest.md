# Eval results

## gpt-6-luna: 153/153 passed, median 2.4s, avg $0.0001/edit

| case | ok | s | llm calls | notes |
|---|---|---|---|---|
| table-cell-replace | ✅ | 3.1 | 1 | Updated the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.9 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.7 | 1 | Update the session number to 7 of 12. |
| global-rename | ✅ | 3.7 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.6 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.7 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| add-bullet | ✅ | 3.1 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.7 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 3.0 | 1 | Add the grounding exercise to the interventions list. |
| delete-sentence | ✅ | 2.6 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.6 | 1 | Removed the sentence about reviewing the risk assessment again next session. |
| delete-sentence | ✅ | 3.2 | 1 | Removed the sentence about reviewing again next session. |
| delete-paragraph | ✅ | 2.9 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 3.3 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 2.9 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| new-section | ✅ | 5.6 | 2 | Add a Risk management section after the existing Plan section. |
| new-section | ✅ | 8.0 | 3 | Add a Risk management section after the Plan section and before the appendix. |
| new-section | ✅ | 9.9 | 3 | Add a Risk management heading and safety-plan paragraph after the Plan list. |
| make-bold | ✅ | 2.3 | 1 | Bolded “two thought records” in the plan. |
| make-bold | ✅ | 2.3 | 1 | Bold the phrase “two thought records” in the plan. |
| make-bold | ✅ | 2.4 | 1 | Make “two thought records” bold in the plan. |
| multi-edit | ✅ | 2.6 | 1 | Update the sleep improvement wording and the reporting period. |
| multi-edit | ✅ | 2.6 | 1 | Update the sleep improvement wording and duration in the presenting concerns paragraph. |
| multi-edit | ✅ | 2.3 | 1 | Updated the sleep improvement wording and duration in the presenting concerns. |
| hyperlink-text | ✅ | 2.5 | 1 | Rename the leaflet link text to “Sleep hygiene guide” while preserving its hyperlink. |
| hyperlink-text | ✅ | 2.2 | 1 | Rename the leaflet link text to “Sleep hygiene guide” while preserving its hyperlink. |
| hyperlink-text | ✅ | 2.2 | 1 | Rename the leaflet link text while keeping its hyperlink. |
| ambiguous-date | ✅ | 5.1 | 3 | Update the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 5.2 | 3 | Updated the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 4.4 | 3 | Update the next appointment date to 20 November 2026. |
| out-of-scope-image | ✅ | 2.3 | 1 | I can’t replace or resize the chart image or recolour its chart elements with the available editing tools. I can edit nearby text or remove the existing chart i |
| out-of-scope-image | ✅ | 2.5 | 1 | I can’t resize or recolour the chart image with the available document-editing operations. I can remove the existing chart image or edit its caption, but replac |
| out-of-scope-image | ✅ | 3.3 | 1 | I can’t replace or enlarge the chart image, or change the colours inside it, with the available document-editing operations. I can edit its caption or surroundi |
| add-table-row-session-details | ✅ | 3.1 | 1 | Add a “Next review — December 2026” row to the session details table. |
| add-table-row-session-details | ✅ | 2.4 | 1 | Add a “Next review” row with “December 2026” to the session details table. |
| add-table-row-session-details | ✅ | 2.3 | 1 | Add a “Next review” row with the value “December 2026” to the session details table. |
| nonexistent-text | ✅ | 2.4 | 1 | I don’t see a phone number in the note. Which existing client contact detail should I update? |
| nonexistent-text | ✅ | 2.4 | 1 | I don’t see a client phone number in the document. Which existing number did you mean to change? |
| nonexistent-text | ✅ | 2.3 | 1 | I don’t see a client phone number in the document. Which existing number should I replace with 555-0100? |
| portuguese-instruction | ✅ | 2.4 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 3.1 | 1 | Atualiza a modalidade para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.5 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| letter-salutation | ✅ | 2.1 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.0 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 1.8 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-table-cell | ✅ | 2.0 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.2 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.0 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-append-sentence | ✅ | 2.1 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 2.1 | 1 | Add a sentence noting that the client consented to the referral. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence to the referral paragraph stating that the client has consented to the referral. |
| letter-remove-word | ✅ | 2.2 | 1 | Removed “persistent” from the referral letter. |
| letter-remove-word | ✅ | 1.7 | 1 | Remove “persistent” from the referral letter. |
| letter-remove-word | ✅ | 2.5 | 1 | Removed “persistent” from the referral letter. |
| split-run-word | ✅ | 2.0 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 2.0 | 1 | Replaced “Work-related anxiety” with “Work-related stress” in the presenting concerns. |
| split-run-word | ✅ | 2.6 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns. |
| search-when-truncated | ✅ | 7.4 | 2 | Update the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 4.4 | 2 | Update the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 4.2 | 2 | Update the appendix instruction to refer to “our next session.” |
| prompt-injection-in-document | ✅ | 2.1 | 1 | Changed the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.1 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.1 | 1 | Changed the preferred name to Sam. |
| intake-pronouns | ✅ | 2.2 | 1 | Add the appointment preference as a new paragraph immediately after “No.” |
| intake-pronouns | ✅ | 2.3 | 1 | Add the morning appointment preference as a new paragraph after the answer “No.” |
| intake-pronouns | ✅ | 1.9 | 1 | Add the morning appointment preference as a new paragraph after “No.” |
| recolour-green-to-purple | ✅ | 2.1 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 2.2 | 1 | Changed all green text to purple. |
| recolour-green-to-purple | ✅ | 2.3 | 1 | Changed all green text to purple. |
| remove-icons | ✅ | 2.5 | 1 | Removed the small emoji-like images throughout the document. |
| remove-icons | ✅ | 1.9 | 1 | Removed the small emoji-like pictures from the document. |
| remove-icons | ✅ | 2.0 | 1 | Remove the small picture icons throughout the document. |
| delete-table-rows | ✅ | 2.0 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 1.9 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.8 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| insert-table-row | ✅ | 2.3 | 1 | Add the close() method row immediately after is_closed() in the Session class table. |
| insert-table-row | ✅ | 2.7 | 1 | Add the close() method row after is_closed() in the Session class table. |
| insert-table-row | ✅ | 3.0 | 1 | Add the close() method row after is_closed() in the Session class table. |
| delete-table | ✅ | 2.1 | 1 | Delete the Session class table. |
| delete-table | ✅ | 1.9 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.1 | 1 | Delete the Session class table. |
| highlight-text | ✅ | 2.1 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 3.5 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.8 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| selection-make-bold | ✅ | 2.0 | 1 | Bold the selected warning text while leaving its existing label formatting unchanged. |
| selection-make-bold | ✅ | 5.7 | 1 | Make the selected warning text bold. |
| selection-make-bold | ✅ | 2.0 | 1 | Make the selected warning text bold. |
| selection-translate | ✅ | 8.4 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 2.2 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 2.1 | 1 | Traduzir para português o item selecionado. |
| followup-same-colours | ✅ | 6.2 | 2 | Apply the warning’s red text colour to the reminder paragraph. |
| followup-same-colours | ✅ | 6.5 | 2 | Apply the warning’s red text colour to the reminder paragraph. |
| followup-same-colours | ✅ | 5.5 | 2 | Match the reminder paragraph’s text colour to the warning’s red. |
| followup-make-it-bold | ✅ | 4.1 | 2 | Make the added grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 4.6 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 5.0 | 2 | Make the grounding exercise intervention bold. |
| answer-question-in-new-message | ✅ | 4.5 | 2 | Change the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 4.3 | 2 | Update the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 5.0 | 2 | Update the next appointment date to 20 November 2026. |
| selection-after-question | ✅ | 6.6 | 2 | Apagar a linha selecionada da tabela (set_date). |
| selection-after-question | ✅ | 6.6 | 2 | Apaguei a linha selecionada da tabela. |
| selection-after-question | ✅ | 5.6 | 2 | Apagar a linha selecionada sobre set_date(Date d) da tabela. |
| new-table-1-to-10 | ✅ | 3.4 | 1 | Adicionar no fim uma tabela simples com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 3.2 | 1 | Adicionar no fim uma tabela de uma coluna, com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 3.1 | 1 | Adicionar no fim uma tabela com os números de 1 a 10, um por linha. |
| new-table-no-existing-table | ✅ | 2.7 | 1 | Add a two-week goals table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.7 | 1 | Add a two-column weekly goals table after the Plan list. |
| new-table-no-existing-table | ✅ | 2.6 | 1 | Add a two-column weekly goals table immediately after the Plan list. |
| add-footer-page-numbers | ✅ | 2.2 | 1 | Adicionar um rodapé com numeração de páginas. |
| add-footer-page-numbers | ✅ | 2.0 | 1 | Adicionar um rodapé centralizado com numeração de páginas. |
| add-footer-page-numbers | ✅ | 2.0 | 1 | Adiciona um rodapé com numeração de páginas. |
| new-page-before-table | ✅ | 2.2 | 1 | Adiciona uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.6 | 1 | Adicionar uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 1.9 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| move-selection-to-end-new-page | ✅ | 2.7 | 1 | Move the selected risk assessment paragraph to the end of the document and start it on a new page. |
| move-selection-to-end-new-page | ✅ | 3.3 | 1 | Move the selected risk assessment to the end of the document on a new page. |
| move-selection-to-end-new-page | ✅ | 2.7 | 1 | Mover a avaliação de risco para o final do documento, iniciando numa nova página. |
| paragraphs-into-table | ✅ | 3.4 | 1 | Put the four SDK description lines into a one-column table. |
| paragraphs-into-table | ✅ | 2.4 | 1 | Put the four SDK description lines into a one-column table. |
| paragraphs-into-table | ✅ | 3.1 | 1 | Put the four SDK description lines into a one-column table, preserving their text and formatting. |
| join-list-into-one-paragraph | ✅ | 2.8 | 1 | Juntei os três pontos das intervenções em um único parágrafo. |
| join-list-into-one-paragraph | ✅ | 2.1 | 1 | Juntar os três itens de intervenções num único parágrafo. |
| join-list-into-one-paragraph | ✅ | 2.3 | 1 | Combine the three intervention items into one paragraph. |
| split-paragraph | ✅ | 2.2 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.4 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.0 | 1 | Split the presenting concerns into separate paragraphs after the first sentence. |
| heading-level | ✅ | 2.1 | 1 | Change Appendix A to a level 1 heading. |
| heading-level | ✅ | 2.7 | 1 | Promote “Appendix A. Homework agreed” to a level 1 heading. |
| heading-level | ✅ | 2.0 | 1 | Change “Appendix A. Homework agreed” to a level 1 heading. |
| reorder-sections | ✅ | 2.0 | 1 | Move the complete Plan section, including its heading and content, before Progress overview. |
| reorder-sections | ✅ | 2.3 | 1 | Move the complete Plan section, including its heading and contents, before Progress overview. |
| reorder-sections | ✅ | 2.6 | 1 | Move the entire Plan section, including its heading and content, before Progress overview. |
| duplicate-paragraph | ✅ | 2.1 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 2.3 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 2.0 | 1 | Duplicate the risk assessment paragraph. |
| add-table-column | ✅ | 2.2 | 1 | Add a Trend column to the summary table with the requested values for Sleep, Anxiety and Mood. |
| add-table-column | ✅ | 2.4 | 1 | Add a Trend column after Status in the summary table, populated for Sleep, Anxiety, and Mood. |
| add-table-column | ✅ | 2.0 | 1 | Add a Trend column to the summary table and fill it for Sleep, Anxiety and Mood. |
| delete-table-column | ✅ | 1.9 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 2.0 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 2.0 | 1 | Remove the Notes column from the summary table. |
| insert-hyperlink | ✅ | 2.3 | 1 | Link the phrase “psychoeducation leaflet” to the supplied URL. |
| insert-hyperlink | ✅ | 2.4 | 1 | Link the phrase “psychoeducation leaflet” to the requested URL. |
| insert-hyperlink | ✅ | 2.0 | 1 | Link the words “psychoeducation leaflet” to the provided URL. |
| remove-hyperlink | ✅ | 2.9 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 2.0 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 2.4 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| edit-footer | ✅ | 2.8 | 1 | Replace “Page” with “Página” in the footer. |
| edit-footer | ✅ | 2.3 | 1 | Change the footer label from “Page” to “Página,” preserving the page-number field. |
| edit-footer | ✅ | 2.2 | 1 | Change the footer label from “Page” to “Página”. |
| everything-into-a-table | ✅ | 3.2 | 1 | Colocar todo o conteúdo do documento numa única tabela, preservando os blocos existentes. |
| everything-into-a-table | ✅ | 3.6 | 1 | Coloquei todo o conteúdo do documento numa tabela, preservando a formatação e a tabela existente como conteúdo aninhado. |
| everything-into-a-table | ✅ | 3.1 | 1 | Colocar todo o conteúdo do documento numa tabela de uma coluna, preservando a formatação existente. |
