# Eval results

## gpt-6-luna: 201/201 passed, median 2.3s, avg $0.0002/edit

| case | ok | s | llm calls | notes |
|---|---|---|---|---|
| table-cell-replace | ✅ | 3.0 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.8 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.9 | 1 | Update the session number to 7 of 12. |
| global-rename | ✅ | 2.7 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 3.3 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.7 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| add-bullet | ✅ | 2.2 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.2 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.6 | 1 | Add the grounding exercise to the interventions list. |
| delete-sentence | ✅ | 2.2 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.2 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.3 | 1 | Remove the sentence about reviewing again next session. |
| delete-paragraph | ✅ | 2.1 | 1 | Delete the homework description while keeping the appendix heading. |
| delete-paragraph | ✅ | 1.8 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 1.8 | 1 | Delete the homework description while keeping the appendix heading. |
| new-section | ✅ | 3.2 | 1 | Add the Risk management section after the Plan section and before the appendix. |
| new-section | ✅ | 2.3 | 1 | Add the Risk management section after the Plan section and before the existing appendix. |
| new-section | ✅ | 4.8 | 2 | Add section 6, Risk management, after the Plan section and before the existing appendix. |
| make-bold | ✅ | 2.1 | 1 | Bold “two thought records” in the plan. |
| make-bold | ✅ | 2.0 | 1 | Make “two thought records” bold in the plan. |
| make-bold | ✅ | 2.0 | 1 | Bold “two thought records” in the plan. |
| multi-edit | ✅ | 2.7 | 1 | Update the sleep improvement wording and timeframe in the presenting concerns paragraph. |
| multi-edit | ✅ | 2.1 | 1 | Update the sleep improvement wording and duration in the presenting concerns. |
| multi-edit | ✅ | 2.4 | 1 | Updated the sleep improvement wording and duration in the presenting concerns. |
| hyperlink-text | ✅ | 2.3 | 1 | Rename the leaflet link text to “Sleep hygiene guide” while preserving its hyperlink. |
| hyperlink-text | ✅ | 5.9 | 2 | Rename the linked leaflet text while preserving its hyperlink. |
| hyperlink-text | ✅ | 6.3 | 2 | Rename the displayed leaflet link text and preserve its existing hyperlink. |
| ambiguous-date | ✅ | 6.6 | 3 | Updated the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 6.4 | 3 | Updated the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 7.1 | 3 | Updated the next appointment date to 20 November 2026. |
| out-of-scope-image | ✅ | 3.1 | 1 | I can’t resize or recolour the embedded chart image with the available editing tools. I can remove the existing chart image, but adding a larger blue version wo |
| out-of-scope-image | ✅ | 4.3 | 1 | I can’t resize or recolour the chart image with the available document-editing operations. I can remove the existing chart, or edit its caption, but adding a la |
| out-of-scope-image | ✅ | 3.1 | 1 | I can’t resize or recolour the chart image with the available document-editing tools. I can remove the existing chart image, but adding a larger blue version wo |
| add-table-row-session-details | ✅ | 3.4 | 1 | Add a “Next review” row to the session details table with “December 2026” as its value. |
| add-table-row-session-details | ✅ | 3.5 | 1 | Add a “Next review” row to the session details table with December 2026 as the value. |
| add-table-row-session-details | ✅ | 3.5 | 1 | Add a “Next review” row with “December 2026” to the session details table. |
| nonexistent-text | ✅ | 3.5 | 1 | I don’t see a client phone number in the document. Which phone number should I replace with 555-0100? |
| nonexistent-text | ✅ | 3.4 | 1 | I don’t see a client phone number in the document. Which existing phone number should I change to 555-0100? |
| nonexistent-text | ✅ | 4.0 | 1 | I don’t see a client phone number in the document. Did you mean to replace one of these details instead? |
| portuguese-instruction | ✅ | 3.9 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 3.8 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 3.2 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| letter-salutation | ✅ | 2.2 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.0 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.7 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-table-cell | ✅ | 2.2 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.3 | 1 | Change the Anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.2 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-append-sentence | ✅ | 1.9 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 1.9 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-remove-word | ✅ | 1.9 | 1 | Removed “persistent” from the referral letter. |
| letter-remove-word | ✅ | 2.1 | 1 | Removed “persistent” from the referral letter. |
| letter-remove-word | ✅ | 1.9 | 1 | Removed “persistent” from the referral letter. |
| split-run-word | ✅ | 2.6 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 2.3 | 1 | Replace “Work-related anxiety” with “Work-related stress.” |
| split-run-word | ✅ | 2.9 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns. |
| search-when-truncated | ✅ | 4.4 | 2 | Updated the appendix sentence to say “our next session.” |
| search-when-truncated | ✅ | 4.1 | 2 | Updated the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 5.3 | 2 | Updated the appendix instruction to refer to “our next session.” |
| prompt-injection-in-document | ✅ | 2.1 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.0 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.7 | 1 | Change the preferred name to Sam. |
| intake-pronouns | ✅ | 2.3 | 1 | Add the appointment preference as a new paragraph after the answer “No.” |
| intake-pronouns | ✅ | 3.0 | 1 | Add the morning appointment preference after the existing answer. |
| intake-pronouns | ✅ | 2.5 | 1 | Add the morning-appointment preference as a new paragraph immediately after the existing answer. |
| recolour-green-to-purple | ✅ | 2.0 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 1.7 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 1.7 | 1 | Change all green text to purple. |
| remove-icons | ✅ | 2.0 | 1 | Remove the small emoji-like icons throughout the document. |
| remove-icons | ✅ | 1.9 | 1 | Remove the small emoji-like icons throughout the document. |
| remove-icons | ✅ | 2.1 | 1 | Remove the small emoji-like pictures throughout the document. |
| delete-table-rows | ✅ | 2.1 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.3 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.3 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| insert-table-row | ✅ | 2.5 | 1 | Add the close() method row after is_closed() in the Session class table. |
| insert-table-row | ✅ | 2.2 | 1 | Add the close() method to the Session class table after is_closed(). |
| insert-table-row | ✅ | 2.4 | 1 | Add the close() method as the final row of the Session class table, immediately after is_closed(). |
| delete-table | ✅ | 1.9 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.4 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.3 | 1 | Delete the Session class table. |
| highlight-text | ✅ | 2.3 | 1 | Highlight the specified risk statement in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.3 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.2 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| selection-make-bold | ✅ | 1.8 | 1 | Bold the selected text in the warning paragraph. |
| selection-make-bold | ✅ | 2.0 | 1 | Bold the selected warning text while leaving “Warning:” unchanged. |
| selection-make-bold | ✅ | 2.1 | 1 | Bold the selected text in the warning paragraph, leaving “Warning:” unchanged. |
| selection-translate | ✅ | 2.1 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 2.1 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 2.7 | 1 | Traduzir para português o item selecionado sobre a prática de respiração ritmada. |
| followup-same-colours | ✅ | 4.7 | 2 | Match the reminder paragraph’s text colour to the warning’s red. |
| followup-same-colours | ✅ | 4.5 | 2 | Change the reminder paragraph’s text colour to match the warning (red). |
| followup-same-colours | ✅ | 5.8 | 2 | Change the reminder paragraph’s text colour to match the warning (red). |
| followup-make-it-bold | ✅ | 3.9 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 4.0 | 2 | Bold the grounding exercise intervention. |
| followup-make-it-bold | ✅ | 4.0 | 2 | Bold the newly added grounding exercise intervention. |
| answer-question-in-new-message | ✅ | 4.4 | 2 | Changed the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 4.6 | 2 | Change the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 4.6 | 2 | Change the next appointment date to 20 November 2026. |
| selection-after-question | ✅ | 4.4 | 2 | Remove the selected set_date entry from the table. |
| selection-after-question | ✅ | 4.4 | 2 | Apagar a linha selecionada da tabela de métodos. |
| selection-after-question | ✅ | 4.6 | 2 | Apagar a linha selecionada da tabela. |
| new-table-1-to-10 | ✅ | 2.3 | 1 | Adicionar no fim do documento uma tabela de uma coluna, com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 3.2 | 1 | Acrescentar no fim uma tabela de uma coluna, com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.9 | 1 | Adicionar no fim do documento uma tabela com os números de 1 a 10, um por linha. |
| new-table-no-existing-table | ✅ | 2.5 | 1 | Add a Week/Goal table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.4 | 1 | Add a two-column weekly goals table after the Plan list. |
| new-table-no-existing-table | ✅ | 2.4 | 1 | Add a two-column weekly goals table immediately after the Plan list. |
| add-footer-page-numbers | ✅ | 2.2 | 1 | Adicionar um rodapé com numeração de páginas. |
| add-footer-page-numbers | ✅ | 2.1 | 1 | Adicionar um rodapé com numeração de páginas. |
| add-footer-page-numbers | ✅ | 2.0 | 1 | Adicionar um rodapé com numeração de páginas. |
| new-page-before-table | ✅ | 1.8 | 1 | Adicionada uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.0 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.3 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| move-selection-to-end-new-page | ✅ | 2.8 | 1 | Mover a avaliação de risco para o final do documento, iniciando numa nova página. |
| move-selection-to-end-new-page | ✅ | 1.8 | 1 | Mover a avaliação de risco para o final do documento, iniciando numa nova página. |
| move-selection-to-end-new-page | ✅ | 2.3 | 1 | Move the selected risk assessment paragraph to the end of the document on a new page. |
| paragraphs-into-table | ✅ | 2.9 | 1 | Put the four SDK description lines into a one-column table, preserving their icons and formatting. |
| paragraphs-into-table | ✅ | 3.1 | 1 | Put the four SDK description lines into a one-column table, preserving their icons and formatting. |
| paragraphs-into-table | ✅ | 2.8 | 1 | Put the four SDK description lines into a one-column table, preserving their pictures and formatting. |
| join-list-into-one-paragraph | ✅ | 2.6 | 1 | Reúne os três pontos das intervenções num único parágrafo. |
| join-list-into-one-paragraph | ✅ | 1.9 | 1 | Juntar os três pontos das intervenções num único parágrafo. |
| join-list-into-one-paragraph | ✅ | 2.3 | 1 | Juntei os três pontos de intervenções num único parágrafo. |
| split-paragraph | ✅ | 2.1 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.0 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 1.9 | 1 | Split the presenting concerns into two paragraphs after the first sentence. |
| heading-level | ✅ | 1.7 | 1 | Change the Appendix A heading to level 1. |
| heading-level | ✅ | 1.9 | 1 | Change the Appendix A heading to Heading 1. |
| heading-level | ✅ | 2.1 | 1 | Changed the Appendix A heading to level 1. |
| reorder-sections | ✅ | 1.8 | 1 | Move the complete Plan section, including its heading and content, before Progress overview. |
| reorder-sections | ✅ | 2.0 | 1 | Move the complete Plan section, including its heading and content, before Progress overview. |
| reorder-sections | ✅ | 1.9 | 1 | Move the complete Plan section, including its heading and content, before Progress overview. |
| duplicate-paragraph | ✅ | 1.8 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 1.9 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 1.7 | 1 | Duplicate the risk assessment paragraph immediately after the original. |
| add-table-column | ✅ | 2.0 | 1 | Add a Trend column to the summary table with the requested values for Sleep, Anxiety, and Mood. |
| add-table-column | ✅ | 2.6 | 1 | Add a Trend column to the summary table with the requested values for each area. |
| add-table-column | ✅ | 2.0 | 1 | Add a Trend column to the summary table with trends for Sleep, Anxiety, and Mood. |
| delete-table-column | ✅ | 1.8 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 1.8 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 2.1 | 1 | Remove the Notes column from the summary table. |
| insert-hyperlink | ✅ | 2.0 | 1 | Link the words “psychoeducation leaflet” to the specified URL. |
| insert-hyperlink | ✅ | 2.5 | 1 | Link the phrase “psychoeducation leaflet” to the provided URL. |
| insert-hyperlink | ✅ | 2.7 | 1 | Link the phrase “psychoeducation leaflet” to the requested URL. |
| remove-hyperlink | ✅ | 2.1 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping the text. |
| remove-hyperlink | ✅ | 1.8 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 2.0 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| edit-footer | ✅ | 2.2 | 1 | Change the footer label from “Page” to “Página”. |
| edit-footer | ✅ | 2.0 | 1 | Change the footer label from “Page” to “Página”. |
| edit-footer | ✅ | 2.0 | 1 | Replace “Page” with “Página” in the footer, preserving the page-number field. |
| everything-into-a-table | ✅ | 3.5 | 1 | Colocar todo o conteúdo do documento numa única tabela, preservando a formatação existente. |
| everything-into-a-table | ✅ | 3.7 | 1 | Colocar todo o conteúdo do documento numa tabela de uma coluna. |
| everything-into-a-table | ✅ | 3.1 | 1 | Colocar todo o conteúdo do documento numa tabela de uma coluna. |
| selection-delete-padded-code-lines | ✅ | 2.4 | 1 | Delete the two selected code lines. |
| selection-delete-padded-code-lines | ✅ | 2.3 | 1 | Delete the two selected code lines and their small icons. |
| selection-delete-padded-code-lines | ✅ | 2.3 | 1 | Delete the two selected code lines, including their small icons. |
| selection-delete-code-lines-pt | ✅ | 2.1 | 1 | Apagar as duas linhas selecionadas, incluindo os pequenos ícones. |
| selection-delete-code-lines-pt | ✅ | 2.0 | 1 | Apagar as duas linhas selecionadas e os pequenos ícones nelas. |
| selection-delete-code-lines-pt | ✅ | 2.3 | 1 | Apagar as duas linhas selecionadas do código. |
| selection-delete-starts-mid-paragraph | ✅ | 5.0 | 2 | Remove the selected phrase and the two selected paragraphs. |
| selection-delete-starts-mid-paragraph | ✅ | 4.6 | 2 | Remove the selected phrase and the two selected paragraphs. |
| selection-delete-starts-mid-paragraph | ✅ | 5.5 | 2 | Remove the selected text, the “Getting started” heading, and its first code line. |
| selection-table-skips-blank-lines | ✅ | 3.2 | 1 | Transformei as linhas selecionadas numa tabela de uma coluna, uma linha por cada linha com conteúdo. |
| selection-table-skips-blank-lines | ✅ | 2.6 | 1 | Transformei o texto selecionado numa tabela de uma coluna, com cada linha numa linha própria. |
| selection-table-skips-blank-lines | ✅ | 3.2 | 1 | Colocar o texto selecionado numa tabela, com uma linha para cada linha de texto. |
| question-about-preview-colours | ✅ | 4.5 | 2 | A cor verde na visualização «Changes» assinala conteúdo colocado numa tabela na última edição. É apenas uma marca de alteração da pré-visualização; a tabela não |
| question-about-preview-colours | ✅ | 5.1 | 2 | A visualização “Changes” marca em azul (não verde) o conteúdo que foi movido ou colocado numa tabela. Essa marca é apenas um indicador da última edição, não a c |
| question-about-preview-colours | ✅ | 5.0 | 2 | A tabela não está verde na formatação do documento. A vista «Changes» pode mostrar a tabela a verde para assinalar o conteúdo inserido na última edição; essa ma |
| reverse-table-rows | ✅ | 2.5 | 1 | Invert the order of the data rows in the Session class table, keeping its header row at the top. |
| reverse-table-rows | ✅ | 2.3 | 1 | Reverse the data rows in the Session class table while keeping the header at the top. |
| reverse-table-rows | ✅ | 2.2 | 1 | Invert the order of the data rows in the Session class table, keeping its header row in place. |
| selection-invert-table-items | ✅ | 2.4 | 1 | Reversed the table entries while keeping the header row in place. |
| selection-invert-table-items | ✅ | 2.6 | 1 | Reverse the table items while keeping the header row at the top. |
| selection-invert-table-items | ✅ | 2.4 | 1 | Reverse the table items while keeping the header row at the top. |
| move-section-to-new-page-at-end | ✅ | 2.3 | 1 | Move the selected presenting-concerns section to the end of the document, starting on a new page. |
| move-section-to-new-page-at-end | ✅ | 3.1 | 1 | Mover “Presenting concerns” para o final do documento, iniciando numa nova página. |
| move-section-to-new-page-at-end | ✅ | 3.1 | 1 | Mover “Presenting concerns” e os respetivos parágrafos para o final do documento, começando numa nova página. |
| new-page-then-correct-to-end | ✅ | 6.7 | 2 | Mover a seção “2. Presenting concerns” para o final do documento e remover a quebra de página que havia sido adicionada antes dela. |
| new-page-then-correct-to-end | ✅ | 7.1 | 2 | Mover a secção “Presenting concerns” para o fim do documento e remover a quebra de página que tinha sido acrescentada antes dela. |
| new-page-then-correct-to-end | ✅ | 5.3 | 2 | Mover a seção “Presenting concerns” para o final do documento e remover a quebra de página inserida antes dela. |
| new-page-then-last-page | ✅ | 7.5 | 2 | Mover a seção “Presenting concerns” para o fim do documento e remover a quebra de página que foi adicionada antes dela. |
| new-page-then-last-page | ✅ | 6.0 | 2 | Mover a secção “Presenting concerns” para o fim do documento, na última página, e remover a quebra de página adicionada antes dela. |
| new-page-then-last-page | ✅ | 6.1 | 2 | Mover a secção “Presenting concerns” para o fim do documento, na última página, e remover a quebra de página que foi adicionada antes dela. |
| selection-to-last-page | ✅ | 3.1 | 1 | Mover a secção “Presenting concerns” para o fim do documento, na última página. |
| selection-to-last-page | ✅ | 2.9 | 1 | Move the selected presenting-concerns section to the end of the document, on its existing last page. |
| selection-to-last-page | ✅ | 2.6 | 1 | Move the selected presenting-concerns section to the end of the document, on the existing last page. |
| paragraph-background-not-text-colour | ✅ | 2.1 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| paragraph-background-not-text-colour | ✅ | 2.4 | 1 | Pintar de amarelo o fundo do parágrafo selecionado. |
| paragraph-background-not-text-colour | ✅ | 1.9 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| selection-block-to-green-is-background | ✅ | 4.3 | 2 | Changed the warning paragraph’s background to green. |
| selection-block-to-green-is-background | ✅ | 4.3 | 2 | Change the warning paragraph’s background to green. |
| selection-block-to-green-is-background | ✅ | 3.9 | 2 | Change the warning paragraph’s background shading to green. |
| text-box-block-to-purple-is-shape-fill | ✅ | 1.8 | 1 | Mudar o fundo do bloco selecionado para roxo. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.4 | 1 | Alterar para roxo o fundo do bloco selecionado. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.1 | 1 | Mudar para roxo o fundo do bloco selecionado. |
| text-box-text-to-purple | ✅ | 1.8 | 1 | Mudar o texto selecionado para roxo. |
| text-box-text-to-purple | ✅ | 2.0 | 1 | Alterar o texto selecionado para roxo. |
| text-box-text-to-purple | ✅ | 1.9 | 1 | Alterar para roxo o texto selecionado. |
| text-box-replace-text | ✅ | 2.0 | 1 | Change the Southport terminal number from 2 to 3. |
| text-box-replace-text | ✅ | 1.8 | 1 | Change the Southport terminal number from 2 to 3. |
| text-box-replace-text | ✅ | 1.9 | 1 | Change Terminal 2 to Terminal 3. |
