# Eval results

## gpt-6-luna: 198/201 passed, median 2.4s, avg $0.0002/edit

| case | ok | s | llm calls | notes |
|---|---|---|---|---|
| table-cell-replace | ✅ | 3.2 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 3.2 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 3.3 | 1 | Update the session number to 7 of 12. |
| global-rename | ✅ | 3.4 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 3.5 | 1 | Updated the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 3.8 | 1 | Update the clinician’s name to Dr. Ana Costa everywhere in the note. |
| add-bullet | ✅ | 2.1 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.2 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.1 | 1 | Add the grounding exercise to the interventions list. |
| delete-sentence | ✅ | 2.3 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.0 | 1 | Remove the highlighted sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.3 | 1 | Remove the sentence about reviewing again next session. |
| delete-paragraph | ✅ | 2.0 | 1 | Delete the homework description while keeping the appendix heading. |
| delete-paragraph | ✅ | 2.0 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 1.7 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| new-section | ✅ | 3.9 | 1 | Add the Risk management section after the plan content and before the appendix. |
| new-section | ✅ | 2.3 | 1 | Add a Risk management section after the Plan section and before the existing appendix. |
| new-section | ✅ | 5.0 | 2 | Add a Risk management section after the plan section. |
| make-bold | ✅ | 2.2 | 1 | Bold “two thought records” in the plan. |
| make-bold | ✅ | 2.2 | 1 | Make “two thought records” bold in the homework plan. |
| make-bold | ✅ | 2.3 | 1 | Bold “two thought records” in the plan. |
| multi-edit | ✅ | 2.7 | 1 | Update the sleep improvement wording and timeframe. |
| multi-edit | ✅ | 2.4 | 1 | Updated the sleep improvement description and its timeframe. |
| multi-edit | ✅ | 2.4 | 1 | Update the sleep improvement phrase and the reported time period. |
| hyperlink-text | ✅ | 2.3 | 1 | Rename the linked leaflet text to “Sleep hygiene guide” while preserving its hyperlink. |
| hyperlink-text | ✅ | 2.3 | 1 | Rename the linked leaflet text to “Sleep hygiene guide” while preserving its hyperlink. |
| hyperlink-text | ✅ | 1.9 | 1 | Rename the linked leaflet text to “Sleep hygiene guide” while keeping its hyperlink. |
| ambiguous-date | ❌ | 4.7 | 2 | status 'declined' not in ['needs_clarification'] (The date in the generated-on line is a protected field, so I can’t change it with the available editing operat |
| ambiguous-date | ✅ | 4.4 | 3 | Update the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 4.1 | 3 | Update the next appointment date to 20 November 2026. |
| out-of-scope-image | ✅ | 2.1 | 1 | I can’t replace or enlarge the chart image or change its colours with the available document-editing operations. I can edit accompanying chart text or formattin |
| out-of-scope-image | ✅ | 2.2 | 1 | I can’t replace the chart with a larger version or change its colours using the available document edits. If you provide the chart as editable text or data, I c |
| out-of-scope-image | ✅ | 1.8 | 1 | I can’t replace or enlarge the chart image or recolor its data elements with the available editing tools. I can change the Figure 1 caption or edit nearby text  |
| add-table-row-session-details | ✅ | 2.9 | 1 | Add a “Next review” row to the session details table with the value “December 2026”. |
| add-table-row-session-details | ✅ | 2.7 | 1 | Add a “Next review” row to the session details table with the value “December 2026”. |
| add-table-row-session-details | ✅ | 2.5 | 1 | Add the Next review row to the session details table. |
| nonexistent-text | ✅ | 2.0 | 1 | I don’t see a client phone number in the document. Which phone number should I replace with 555-0100? |
| nonexistent-text | ✅ | 2.1 | 1 | I don't see a client phone number in the document. Which existing contact detail should I update to 555-0100? |
| nonexistent-text | ✅ | 2.3 | 1 | I don’t see a client phone number in the document. Which existing number should I change to 555-0100? |
| portuguese-instruction | ✅ | 2.1 | 1 | Atualizei a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.4 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.1 | 1 | Atualizei a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| letter-salutation | ✅ | 2.1 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.0 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.9 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-table-cell | ✅ | 2.9 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.4 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.5 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 2.1 | 1 | Add a sentence confirming the client has consented to the referral. |
| letter-append-sentence | ✅ | 2.8 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-remove-word | ✅ | 2.8 | 1 | Remove “persistent” from the referral letter. |
| letter-remove-word | ✅ | 2.3 | 1 | Remove “persistent” from the referral letter. |
| letter-remove-word | ✅ | 2.4 | 1 | Remove “persistent” from the referral letter. |
| split-run-word | ✅ | 2.2 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns. |
| split-run-word | ✅ | 2.0 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 2.0 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns. |
| search-when-truncated | ✅ | 4.6 | 2 | Changed the appendix instruction to refer to “our next session.” |
| search-when-truncated | ✅ | 4.7 | 2 | Update the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 4.6 | 2 | Update the appendix instruction to say “our next session.” |
| prompt-injection-in-document | ✅ | 2.1 | 1 | Changed the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.1 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.0 | 1 | Change the preferred name from Alex to Sam. |
| intake-pronouns | ✅ | 2.3 | 1 | Add the appointment preference as a new paragraph immediately after “No.” |
| intake-pronouns | ✅ | 2.3 | 1 | Add the sentence as a new paragraph immediately after the answer “No.” |
| intake-pronouns | ✅ | 2.3 | 1 | Add the morning appointment preference as a new paragraph after “No.” |
| recolour-green-to-purple | ✅ | 4.1 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 4.0 | 1 | Changed the green text to purple. |
| recolour-green-to-purple | ✅ | 3.1 | 1 | Change all green text to purple. |
| remove-icons | ✅ | 2.8 | 1 | Remove the small emoji-like icons from the document. |
| remove-icons | ✅ | 2.8 | 1 | Remove the small emoji-like icons from the document. |
| remove-icons | ✅ | 2.7 | 1 | Remove the small emoji-like pictures from the document. |
| delete-table-rows | ✅ | 2.4 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.4 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.3 | 1 | Removed the set_date and set_modality entries from the Session class table. |
| insert-table-row | ✅ | 3.0 | 1 | Add the close() method to the Session class table after is_closed(). |
| insert-table-row | ✅ | 2.4 | 1 | Add the close() method row to the Session class table after is_closed(). |
| insert-table-row | ✅ | 2.0 | 1 | Add the close() method row to the Session class table after is_closed(). |
| delete-table | ✅ | 2.1 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.2 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.0 | 1 | Delete the Session class table. |
| highlight-text | ✅ | 3.0 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.1 | 1 | Highlight “No current risk indicators.” in yellow and format it in red. |
| highlight-text | ✅ | 2.1 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| selection-make-bold | ✅ | 2.5 | 1 | Bold the selected warning text while leaving “Warning:” unchanged. |
| selection-make-bold | ✅ | 2.2 | 1 | Bold the selected text in the warning paragraph. |
| selection-make-bold | ✅ | 2.3 | 1 | Bold the selected warning text while leaving “Warning:” unchanged. |
| selection-translate | ✅ | 2.9 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 3.7 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 3.3 | 1 | Traduzir para português o item selecionado. |
| followup-same-colours | ✅ | 4.6 | 2 | Set the reminder paragraph to the warning’s red text colour. |
| followup-same-colours | ✅ | 5.1 | 2 | Make the reminder paragraph the same red colour as the warning. |
| followup-same-colours | ✅ | 4.4 | 2 | Set the reminder paragraph to the warning’s red text colour. |
| followup-make-it-bold | ✅ | 4.9 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 4.0 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 3.8 | 2 | Make the grounding exercise intervention bold. |
| answer-question-in-new-message | ✅ | 5.7 | 2 | Change the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 5.1 | 2 | Updated the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 5.6 | 2 | Changed the next appointment date to 20 November 2026. |
| selection-after-question | ✅ | 5.1 | 2 | Apaguei a linha selecionada da tabela. |
| selection-after-question | ✅ | 5.5 | 2 | Apagar a linha selecionada da tabela. |
| selection-after-question | ✅ | 5.5 | 2 | Apagar a linha selecionada da tabela. |
| new-table-1-to-10 | ✅ | 2.7 | 1 | Adicionar no fim do documento uma tabela com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.9 | 1 | Adicionar no fim do documento uma tabela de uma coluna, com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.8 | 1 | Adicionar no fim do documento uma tabela de uma coluna com os números de 1 a 10, um por linha. |
| new-table-no-existing-table | ✅ | 2.1 | 1 | Add the requested Week/Goal table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.6 | 1 | Add a Week/Goal table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.1 | 1 | Add the requested Week/Goal table immediately after the Plan list. |
| add-footer-page-numbers | ✅ | 4.6 | 1 | Adicionar um rodapé com o número da página. |
| add-footer-page-numbers | ✅ | 3.9 | 1 | Adicionar um rodapé com o número da página. |
| add-footer-page-numbers | ✅ | 3.3 | 1 | Adicionar um rodapé com o número da página. |
| new-page-before-table | ✅ | 3.1 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.7 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.2 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| move-selection-to-end-new-page | ✅ | 3.0 | 1 | Move the selected risk assessment paragraph to the end of the document and start it on a new page. |
| move-selection-to-end-new-page | ✅ | 2.2 | 1 | Mover a avaliação de risco para o final do documento, começando numa nova página. |
| move-selection-to-end-new-page | ✅ | 3.0 | 1 | Move the selected risk assessment paragraph to the end of the document on a new page. |
| paragraphs-into-table | ✅ | 2.6 | 1 | Put the four SDK description lines into a one-column table, preserving their contents and formatting. |
| paragraphs-into-table | ✅ | 2.5 | 1 | Put the four SDK description lines into a one-column table. |
| paragraphs-into-table | ✅ | 2.4 | 1 | Put the four SDK description lines into a one-column table. |
| join-list-into-one-paragraph | ✅ | 3.1 | 1 | Juntar as três intervenções num único parágrafo, mantendo o formato de lista. |
| join-list-into-one-paragraph | ✅ | 2.9 | 1 | Juntar os três itens de intervenções num único parágrafo, preservando o texto. |
| join-list-into-one-paragraph | ✅ | 3.4 | 1 | Juntei os três pontos das intervenções num único parágrafo. |
| split-paragraph | ✅ | 2.2 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.4 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.0 | 1 | Split the presenting concerns into two paragraphs after the first sentence. |
| heading-level | ✅ | 3.5 | 1 | Promote “Appendix A. Homework agreed” to a level 1 heading. |
| heading-level | ✅ | 2.4 | 1 | Change “Appendix A. Homework agreed” to a level 1 heading. |
| heading-level | ✅ | 2.1 | 1 | Change “Appendix A. Homework agreed” to a level 1 heading. |
| reorder-sections | ✅ | 2.2 | 1 | Move the complete Plan section, including its heading and content, before Progress overview. |
| reorder-sections | ✅ | 1.9 | 1 | Move the complete Plan section, including its heading and all content through the clinician signature, before Progress overview. |
| reorder-sections | ✅ | 2.2 | 1 | Move the complete Plan section so it appears before the Progress overview section. |
| duplicate-paragraph | ✅ | 2.1 | 1 | Duplicate the risk assessment paragraph directly after the original. |
| duplicate-paragraph | ✅ | 2.0 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 2.0 | 1 | Duplicate the risk assessment paragraph immediately after the original. |
| add-table-column | ✅ | 2.1 | 1 | Add a Trend column to the summary table with the requested values for Sleep, Anxiety, and Mood. |
| add-table-column | ✅ | 2.4 | 1 | Add a Trend column to the summary table with the requested values for Sleep, Anxiety, and Mood. |
| add-table-column | ✅ | 2.5 | 1 | Add a Trend column to the summary table with the requested values for Sleep, Anxiety, and Mood. |
| delete-table-column | ✅ | 2.1 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 1.9 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 2.2 | 1 | Remove the Notes column from the summary table. |
| insert-hyperlink | ✅ | 2.8 | 1 | Link the phrase “psychoeducation leaflet” to the specified URL. |
| insert-hyperlink | ✅ | 2.6 | 1 | Link the phrase “psychoeducation leaflet” to the provided URL. |
| insert-hyperlink | ✅ | 2.2 | 1 | Link the phrase “psychoeducation leaflet” to the specified URL. |
| remove-hyperlink | ✅ | 2.5 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 1.8 | 1 | Remove the hyperlink while keeping the “Sleep hygiene leaflet” text. |
| remove-hyperlink | ✅ | 2.1 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| edit-footer | ✅ | 2.2 | 1 | Replace “Page” with “Página” in the footer. |
| edit-footer | ✅ | 2.0 | 1 | Replace “Page” with “Página” in the footer. |
| edit-footer | ✅ | 2.0 | 1 | Replace “Page” with “Página” in the footer. |
| everything-into-a-table | ✅ | 3.5 | 1 | Colocar todo o conteúdo do documento numa única tabela, preservando a formatação existente. |
| everything-into-a-table | ✅ | 4.2 | 1 | Colocar todo o conteúdo do documento numa única tabela. |
| everything-into-a-table | ✅ | 3.3 | 1 | Colocar todo o conteúdo do documento numa tabela de uma coluna, preservando a formatação existente. |
| selection-delete-padded-code-lines | ✅ | 2.2 | 1 | Delete the two selected code lines and their small icons. |
| selection-delete-padded-code-lines | ✅ | 2.7 | 1 | Delete the two selected code paragraphs and their small icons. |
| selection-delete-padded-code-lines | ✅ | 2.6 | 1 | Delete the two selected code paragraphs and their small icons. |
| selection-delete-code-lines-pt | ✅ | 2.6 | 1 | Apaguei as duas linhas selecionadas. |
| selection-delete-code-lines-pt | ✅ | 2.4 | 1 | Apaguei as duas linhas selecionadas. |
| selection-delete-code-lines-pt | ✅ | 2.2 | 1 | Apagar as duas linhas selecionadas. |
| selection-delete-starts-mid-paragraph | ✅ | 4.9 | 2 | Remove the selected phrase, heading, and code line, leaving the rest of the note intact. |
| selection-delete-starts-mid-paragraph | ✅ | 5.2 | 2 | Delete the selected text and paragraphs. |
| selection-delete-starts-mid-paragraph | ❌ | 4.9 | 2 | missing 'Note: this reference is' |
| selection-table-skips-blank-lines | ✅ | 2.1 | 1 | Coloquei cada linha selecionada numa linha separada de uma tabela. |
| selection-table-skips-blank-lines | ✅ | 2.0 | 1 | Transformar os parágrafos selecionados numa tabela, uma linha por parágrafo com conteúdo. |
| selection-table-skips-blank-lines | ✅ | 2.3 | 1 | Transformei o texto selecionado numa tabela, mantendo uma linha por parágrafo não vazio. |
| question-about-preview-colours | ✅ | 4.5 | 2 | As marcas verdes podem aparecer na vista “Changes” para indicar conteúdo inserido ou alterado na última edição; não significam necessariamente que a tabela este |
| question-about-preview-colours | ✅ | 4.9 | 2 | A tabela em si não está verde: as notas mostram que apenas o texto “Note:” no parágrafo de aviso está verde (#70AD47). Se a tabela aparece verde na vista “Chang |
| question-about-preview-colours | ✅ | 6.4 | 2 | As marcações verdes aparecem apenas na vista «Changes» para assinalar conteúdo inserido ou alterado na última edição. A tabela não fica verde no documento; na v |
| reverse-table-rows | ✅ | 2.6 | 1 | Invert the order of the data rows in the Session class table while keeping the header row in place. |
| reverse-table-rows | ✅ | 2.6 | 1 | Invert the order of the session class table’s data rows while keeping the header row in place. |
| reverse-table-rows | ✅ | 2.4 | 1 | Invert the order of the data rows in the Session class table, keeping its header row in place. |
| selection-invert-table-items | ✅ | 2.5 | 1 | Reverse the table entries while keeping the header row at the top. |
| selection-invert-table-items | ✅ | 2.8 | 1 | Reversed the order of the table items while keeping the header row in place. |
| selection-invert-table-items | ✅ | 3.4 | 1 | Reversed the table items while keeping the header row in place. |
| move-section-to-new-page-at-end | ✅ | 2.2 | 1 | Move the selected “Presenting concerns” section to the end of the document on a new page. |
| move-section-to-new-page-at-end | ✅ | 2.1 | 1 | Move the selected “Presenting concerns” section to the end of the document and start it on a new page. |
| move-section-to-new-page-at-end | ✅ | 2.6 | 1 | Mover a seção “Presenting concerns” para o final do documento, começando em uma nova página. |
| new-page-then-correct-to-end | ✅ | 6.2 | 2 | Mover a seção “Presenting concerns” para o final do documento e remover a quebra de página inserida antes dela. |
| new-page-then-correct-to-end | ✅ | 4.5 | 2 | Mover a seção “2. Presenting concerns” para o final do documento e remover a quebra de página que havia sido adicionada antes dela. |
| new-page-then-correct-to-end | ✅ | 13.3 | 2 | Move the presenting-concerns section to the end of the document and remove the page break added before it. |
| new-page-then-last-page | ❌ | 5.2 | 2 | step 2: unexpected page break right before '3. Interventions used'; step 2: 2 page breaks (wanted 1) |
| new-page-then-last-page | ✅ | 4.1 | 2 | Mover a secção “2. Presenting concerns” para a última folha, sem iniciar uma nova página. |
| new-page-then-last-page | ✅ | 4.7 | 2 | Mover a secção “2. Presenting concerns” para a última folha e remover a quebra de página que a iniciava numa nova página. |
| selection-to-last-page | ✅ | 2.2 | 1 | Mover a secção “2. Presenting concerns” para a última folha, após o conteúdo existente. |
| selection-to-last-page | ✅ | 2.7 | 1 | Move the selected presenting-concerns section to the end of the document, on its existing last page. |
| selection-to-last-page | ✅ | 2.5 | 1 | Move the selected presenting-concerns section to the end of the document, on the existing last page. |
| paragraph-background-not-text-colour | ✅ | 2.1 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| paragraph-background-not-text-colour | ✅ | 2.1 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| paragraph-background-not-text-colour | ✅ | 2.6 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| selection-block-to-green-is-background | ✅ | 4.2 | 2 | Change the warning block’s background shading to green. |
| selection-block-to-green-is-background | ✅ | 5.2 | 2 | Change the warning paragraph’s background to green. |
| selection-block-to-green-is-background | ✅ | 4.5 | 2 | Change the warning paragraph’s background from light yellow to green. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.3 | 1 | Mudar o bloco selecionado para roxo. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.0 | 1 | Alterar para roxo o bloco selecionado. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.1 | 1 | Mudar o fundo do bloco selecionado para roxo. |
| text-box-text-to-purple | ✅ | 1.8 | 1 | Mudar o texto selecionado para roxo. |
| text-box-text-to-purple | ✅ | 2.2 | 1 | Mudar o texto selecionado para roxo. |
| text-box-text-to-purple | ✅ | 1.8 | 1 | Mudar para roxo o texto selecionado. |
| text-box-replace-text | ✅ | 1.9 | 1 | Change Terminal 2 to Terminal 3. |
| text-box-replace-text | ✅ | 2.1 | 1 | Change Terminal 2 to Terminal 3. |
| text-box-replace-text | ✅ | 2.1 | 1 | Change Terminal 2 to Terminal 3. |
