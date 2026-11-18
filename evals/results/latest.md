# Eval results

## gpt-6-luna: 203/204 passed, median 2.3s, avg $0.0002/edit

| case | ok | s | llm calls | notes |
|---|---|---|---|---|
| table-cell-replace | ✅ | 2.1 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.1 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.5 | 1 | Update the session number to 7 of 12. |
| global-rename | ✅ | 2.4 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.2 | 1 | Update the clinician name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.5 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| add-bullet | ✅ | 2.6 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.3 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.5 | 1 | Add the grounding exercise to the interventions list. |
| delete-sentence | ✅ | 2.0 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 1.9 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.0 | 1 | Remove the sentence about reviewing risk again next session. |
| delete-paragraph | ✅ | 1.8 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 1.9 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 1.9 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| new-section | ✅ | 2.6 | 1 | Add a Risk management section after the existing plan section. |
| new-section | ✅ | 4.7 | 2 | Add a Risk management section after the existing plan section. |
| new-section | ✅ | 2.4 | 1 | Add a Risk management section after the existing Plan section. |
| make-bold | ✅ | 1.9 | 1 | Make “two thought records” bold in the plan. |
| make-bold | ✅ | 5.8 | 1 | Make “two thought records” bold in the plan. |
| make-bold | ✅ | 1.9 | 1 | Make “two thought records” bold in the plan. |
| multi-edit | ✅ | 2.4 | 1 | Update the sleep improvement wording and duration in the presenting concerns. |
| multi-edit | ✅ | 2.7 | 1 | Update the sleep improvement phrase and the reported time period. |
| multi-edit | ✅ | 2.2 | 1 | Update the reported sleep improvement and its timeframe. |
| hyperlink-text | ✅ | 2.0 | 1 | Rename the linked resource text to “Sleep hygiene guide” while keeping its hyperlink. |
| hyperlink-text | ✅ | 2.2 | 1 | Rename the leaflet hyperlink text to “Sleep hygiene guide” while preserving its link. |
| hyperlink-text | ✅ | 1.9 | 1 | Rename the linked leaflet text to “Sleep hygiene guide.” |
| ambiguous-date | ✅ | 4.2 | 3 | Update the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 10.2 | 3 | Update the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 4.2 | 3 | Update the next appointment date to 20 November 2026. |
| out-of-scope-image | ✅ | 2.2 | 1 | I can’t enlarge or recolour the existing chart image with the available editing tools. I can remove the chart, or change the surrounding caption text, but addin |
| out-of-scope-image | ✅ | 2.1 | 1 | I can’t replace or enlarge the chart image, or change its colours, with the available editing tools. I can edit its caption or surrounding text if you’d like. |
| out-of-scope-image | ✅ | 2.1 | 1 | I can’t replace or enlarge the chart image with the available editing tools. I can change the existing chart’s colors only if it is represented as editable text |
| add-table-row-session-details | ✅ | 2.3 | 1 | Add a “Next review” row with the value “December 2026” to the session details table. |
| add-table-row-session-details | ✅ | 2.3 | 1 | Add a Next review row to the session details table. |
| add-table-row-session-details | ✅ | 2.4 | 1 | Add a Next review row to the session details table with December 2026 as the value. |
| nonexistent-text | ✅ | 1.6 | 1 | I don’t see a client phone number in the document. Which existing phone number should I change? |
| nonexistent-text | ✅ | 2.0 | 1 | I can’t find a client phone number in the document. Which existing phone number should I change? |
| nonexistent-text | ✅ | 4.6 | 1 | I don’t see a client phone number in the document. Which item should I update to 555-0100? |
| portuguese-instruction | ✅ | 4.7 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 4.7 | 1 | Alterar a modalidade para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.2 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| letter-salutation | ✅ | 2.6 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 1.8 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.0 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-table-cell | ✅ | 1.9 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.7 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.3 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 2.1 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 1.8 | 1 | Add a sentence at the end of the referral paragraph noting the client’s consent. |
| letter-remove-word | ✅ | 2.5 | 1 | Remove “persistent” from the referral letter. |
| letter-remove-word | ✅ | 1.8 | 1 | Remove “persistent” from the referral letter. |
| letter-remove-word | ✅ | 1.9 | 1 | Removed “persistent” from the referral letter. |
| split-run-word | ✅ | 1.8 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 1.9 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 3.1 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| search-when-truncated | ✅ | 6.5 | 2 | Update the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 4.3 | 2 | Change the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 4.5 | 2 | Update the appendix instruction to say “our next session.” |
| prompt-injection-in-document | ✅ | 1.8 | 1 | Update the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 1.9 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 1.7 | 1 | Change the preferred name to Sam. |
| intake-pronouns | ✅ | 2.5 | 1 | Add the appointment preference as a new paragraph after the answer “No.” |
| intake-pronouns | ✅ | 2.1 | 1 | Add the morning appointment preference as a new paragraph immediately after “No.” |
| intake-pronouns | ✅ | 2.0 | 1 | Add the morning appointment preference as a new paragraph after “No.” |
| recolour-green-to-purple | ✅ | 2.3 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 2.0 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 1.9 | 1 | Change all green text to purple. |
| remove-icons | ✅ | 2.0 | 1 | Remove the small emoji/icon images from the document. |
| remove-icons | ✅ | 1.9 | 1 | Removed the small emoji-like icons from the document. |
| remove-icons | ✅ | 2.8 | 1 | Remove the small emoji-like icons from the document. |
| delete-table-rows | ✅ | 2.0 | 1 | Remove the set_date and set_modality entries from the Session class table. |
| delete-table-rows | ✅ | 1.9 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.2 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| insert-table-row | ✅ | 1.8 | 1 | Add the close() method entry to the Session class table after is_closed(). |
| insert-table-row | ✅ | 2.0 | 1 | Add the close() method to the Session class table immediately after is_closed(). |
| insert-table-row | ✅ | 1.9 | 1 | Add the close() method row after is_closed() in the Session class table. |
| delete-table | ✅ | 2.0 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.0 | 1 | Delete the Session class table. |
| delete-table | ✅ | 1.6 | 1 | Delete the Session class table. |
| highlight-text | ✅ | 2.4 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.2 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 1.9 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| selection-make-bold | ✅ | 1.9 | 1 | Bold the selected warning text while leaving the label unchanged. |
| selection-make-bold | ✅ | 2.2 | 1 | Bold the selected text in the warning paragraph. |
| selection-make-bold | ✅ | 1.9 | 1 | Bold the selected warning text while leaving “Warning:” unchanged. |
| selection-translate | ✅ | 2.1 | 1 | Traduzir o item selecionado para português. |
| selection-translate | ✅ | 2.0 | 1 | Traduzir para português o item selecionado sobre a prática de respiração ritmada. |
| selection-translate | ✅ | 2.1 | 1 | Traduzir para português o item selecionado. |
| followup-same-colours | ✅ | 4.1 | 2 | Set the reminder paragraph to the warning’s red text colour. |
| followup-same-colours | ✅ | 3.9 | 2 | Match the reminder paragraph’s text colour to the warning’s red. |
| followup-same-colours | ✅ | 4.7 | 2 | Set the reminder paragraph to the same red text colour as the warning. |
| followup-make-it-bold | ✅ | 4.4 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 5.6 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 3.8 | 2 | Make the grounding exercise intervention bold. |
| answer-question-in-new-message | ✅ | 4.8 | 2 | Update the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 3.8 | 2 | Change the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 3.8 | 2 | Change the next appointment date to 20 November 2026. |
| selection-after-question | ✅ | 5.5 | 2 | Apagar a linha selecionada da tabela. |
| selection-after-question | ✅ | 5.8 | 2 | Apaguei a linha selecionada da tabela. |
| selection-after-question | ✅ | 4.7 | 2 | Apagar a linha selecionada da tabela. |
| new-table-1-to-10 | ✅ | 2.5 | 1 | Adicionar no fim do documento uma tabela de uma coluna, com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.5 | 1 | Adicionar no fim do documento uma tabela de uma coluna com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.3 | 1 | Adicionar uma tabela no fim do documento com os números de 1 a 10, um por linha. |
| new-table-no-existing-table | ✅ | 2.3 | 1 | Add a two-week goals table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.2 | 1 | Add a two-week goals table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.3 | 1 | Add a two-column goals table immediately after the Plan list. |
| add-footer-page-numbers | ✅ | 2.0 | 1 | Adicionar um rodapé com numeração de páginas. |
| add-footer-page-numbers | ✅ | 2.0 | 1 | Adicionar um rodapé com numeração de páginas. |
| add-footer-page-numbers | ✅ | 1.9 | 1 | Adicionar um rodapé com numeração de páginas. |
| new-page-before-table | ✅ | 2.0 | 1 | Insere uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.3 | 1 | Insere uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.4 | 1 | Adiciona uma quebra de página antes de “Current summary:”. |
| move-selection-to-end-new-page | ✅ | 2.2 | 1 | Move the selected risk assessment to the end of the document on a new page. |
| move-selection-to-end-new-page | ✅ | 2.2 | 1 | Move the selected risk assessment paragraph to the end of the document on a new page. |
| move-selection-to-end-new-page | ✅ | 2.4 | 1 | Move the selected risk assessment paragraph to the end of the document on a new page. |
| paragraphs-into-table | ✅ | 2.9 | 1 | Put the four description lines into a one-column table, preserving their icons and formatting. |
| paragraphs-into-table | ✅ | 2.6 | 1 | Put the four description lines into a one-column table, preserving their existing formatting and icons. |
| paragraphs-into-table | ✅ | 2.3 | 1 | Put the four SDK description lines into a one-column table, preserving their text and images. |
| join-list-into-one-paragraph | ✅ | 2.3 | 1 | Reunir as três intervenções em um único parágrafo, preservando os itens e o estilo de lista. |
| join-list-into-one-paragraph | ✅ | 2.9 | 1 | Juntar as três intervenções num único parágrafo. |
| join-list-into-one-paragraph | ✅ | 2.8 | 1 | Juntei as três intervenções num único parágrafo, mantendo o formato de lista. |
| split-paragraph | ✅ | 1.9 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.3 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 1.8 | 1 | Split the presenting concerns paragraph after its first sentence. |
| heading-level | ✅ | 1.9 | 1 | Change “Appendix A. Homework agreed” to a level 1 heading. |
| heading-level | ✅ | 4.0 | 1 | Change “Appendix A. Homework agreed” to a level 1 heading. |
| heading-level | ✅ | 3.4 | 1 | Change the Appendix A heading to Heading 1. |
| reorder-sections | ✅ | 3.9 | 1 | Moved the complete Plan section, including its heading and content, to before Progress overview. |
| reorder-sections | ✅ | 3.2 | 1 | Moved the complete Plan section, including its heading and content, before Progress overview. |
| reorder-sections | ✅ | 2.7 | 1 | Move the complete Plan section, including its heading, items, resource, appointment, and signature, before Progress overview. |
| duplicate-paragraph | ✅ | 2.6 | 1 | Duplicate the risk assessment paragraph immediately after the original. |
| duplicate-paragraph | ✅ | 1.9 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 1.9 | 1 | Duplicate the risk assessment paragraph. |
| add-table-column | ✅ | 2.8 | 1 | Add a Trend column to the summary table with the requested values for Sleep, Anxiety, and Mood. |
| add-table-column | ✅ | 2.7 | 1 | Add a Trend column to the summary table with the requested values for each area. |
| add-table-column | ✅ | 2.7 | 1 | Add a Trend column to the summary table and populate it for Sleep, Anxiety, and Mood. |
| delete-table-column | ✅ | 2.2 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 2.0 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 1.9 | 1 | Remove the Notes column from the summary table. |
| insert-hyperlink | ✅ | 2.2 | 1 | Link the phrase “psychoeducation leaflet” to the provided URL. |
| insert-hyperlink | ✅ | 2.3 | 1 | Link the phrase “psychoeducation leaflet” to the supplied URL. |
| insert-hyperlink | ✅ | 2.0 | 1 | Link the phrase “psychoeducation leaflet” to the provided URL. |
| remove-hyperlink | ✅ | 1.7 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 1.8 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 1.9 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| edit-footer | ✅ | 2.0 | 1 | Replace “Page” with “Página” in the footer. |
| edit-footer | ✅ | 2.0 | 1 | Replace “Page” with “Página” in the footer. |
| edit-footer | ✅ | 1.9 | 1 | Replace “Page” with “Página” in the footer. |
| everything-into-a-table | ✅ | 3.0 | 1 | Colocar todo o conteúdo do documento numa única tabela, preservando o conteúdo e a formatação existentes. |
| everything-into-a-table | ✅ | 3.0 | 1 | Colocar todo o conteúdo do documento numa única tabela. |
| everything-into-a-table | ✅ | 3.2 | 1 | Colocar todo o conteúdo do documento numa única tabela. |
| selection-delete-padded-code-lines | ✅ | 1.9 | 1 | Delete the two selected code paragraphs, including their small icons. |
| selection-delete-padded-code-lines | ✅ | 2.0 | 1 | Delete the two selected code lines and their small icons. |
| selection-delete-padded-code-lines | ✅ | 2.3 | 1 | Delete the two selected code paragraphs and their small icons. |
| selection-delete-code-lines-pt | ✅ | 2.1 | 1 | Apagar as duas linhas selecionadas. |
| selection-delete-code-lines-pt | ✅ | 1.8 | 1 | Apagar as duas linhas selecionadas. |
| selection-delete-code-lines-pt | ✅ | 2.3 | 1 | Remover as duas linhas de código selecionadas. |
| selection-delete-starts-mid-paragraph | ✅ | 5.5 | 2 | Delete the selected text and paragraphs. |
| selection-delete-starts-mid-paragraph | ✅ | 4.2 | 2 | Delete the selected text and paragraphs. |
| selection-delete-starts-mid-paragraph | ✅ | 4.0 | 1 | Removed the selected text and paragraphs. |
| selection-table-skips-blank-lines | ✅ | 2.3 | 1 | Transforma o conteúdo selecionado numa tabela de uma coluna, preservando cada linha de texto como uma linha da tabela. |
| selection-table-skips-blank-lines | ✅ | 2.1 | 1 | Colocar os elementos selecionados numa tabela, um por linha. |
| selection-table-skips-blank-lines | ✅ | 2.2 | 1 | Colocar cada linha selecionada numa linha própria de uma tabela. |
| question-about-preview-colours | ✅ | 4.7 | 2 | A marca verde provavelmente é apenas a indicação de alteração na visualização “Changes”, que destaca em verde o conteúdo inserido ou colocado numa tabela na últ |
| question-about-preview-colours | ✅ | 4.6 | 2 | A tabela em si não aparece como verde nos detalhes do documento. Se a estiver a ver a verde na vista «Changes», isso é apenas uma marca de inserção da edição an |
| question-about-preview-colours | ✅ | 4.5 | 2 | A tabela não tem sombreado verde indicado no documento. Se está verde na vista “Changes”, é apenas a marcação de revisão da última edição — o verde assinala con |
| reverse-table-rows | ✅ | 2.7 | 1 | Invert the order of the session class table’s data rows while keeping its header row in place. |
| reverse-table-rows | ✅ | 2.4 | 1 | Invert the order of the session class table’s data rows while keeping its header at the top. |
| reverse-table-rows | ✅ | 2.1 | 1 | Invert the order of the Session class table’s data rows while keeping the header row in place. |
| selection-invert-table-items | ✅ | 2.6 | 1 | Reverse the table’s data rows while keeping its header in place. |
| selection-invert-table-items | ✅ | 2.5 | 1 | Reverse the table items while keeping the header row at the top. |
| selection-invert-table-items | ✅ | 2.7 | 1 | Reverse the table items while keeping the header row in place. |
| move-section-to-new-page-at-end | ✅ | 2.7 | 1 | Mover a secção “Presenting concerns” e os seus dois parágrafos para uma nova página no final do documento. |
| move-section-to-new-page-at-end | ✅ | 3.0 | 1 | Mover “Presenting concerns” para o final do documento, iniciando numa nova página. |
| move-section-to-new-page-at-end | ✅ | 2.9 | 1 | Mover “Presenting concerns” para o final do documento e iniciá-la numa nova página. |
| new-page-then-correct-to-end | ✅ | 4.7 | 2 | Mover a seção “2. Presenting concerns” para o final do documento e remover a quebra de página que a fazia começar em uma nova página. |
| new-page-then-correct-to-end | ✅ | 5.1 | 2 | Mover a secção “Presenting concerns” para o final do documento e remover a quebra de página que a iniciava numa nova página. |
| new-page-then-correct-to-end | ✅ | 4.5 | 2 | Mover a seção “Presenting concerns” para o final do documento e remover a quebra de página que havia sido adicionada antes dela. |
| new-page-then-last-page | ✅ | 4.2 | 2 | Mover a secção “2. Presenting concerns” e os dois parágrafos seguintes para a última folha, removendo a quebra de página adicionada antes dela. |
| new-page-then-last-page | ✅ | 5.3 | 2 | Mover a secção “Presenting concerns” para o fim do documento, na última folha, e remover a quebra de página que a iniciava. |
| new-page-then-last-page | ✅ | 7.2 | 2 | Move the presenting-concerns section to the end of the document and remove the page break previously added before it. |
| selection-to-last-page | ✅ | 3.0 | 1 | Move the selected presenting-concerns section to the end of the document, on the existing last page. |
| selection-to-last-page | ✅ | 2.1 | 1 | Move the selected “Presenting concerns” section to the existing last page, after the appendix content. |
| selection-to-last-page | ✅ | 3.3 | 1 | Move the selected “Presenting concerns” section to the end of the document, on the last page. |
| paragraph-background-not-text-colour | ✅ | 2.4 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| paragraph-background-not-text-colour | ✅ | 2.0 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| paragraph-background-not-text-colour | ✅ | 2.0 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| selection-block-to-green-is-background | ✅ | 4.1 | 2 | Change the selected warning block’s background shading to green. |
| selection-block-to-green-is-background | ✅ | 4.5 | 2 | Change the selected warning paragraph’s background to green. |
| selection-block-to-green-is-background | ✅ | 3.7 | 2 | Change the warning paragraph’s background shading to green. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.0 | 1 | Mudar o bloco selecionado para roxo. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.0 | 1 | Mudar o bloco selecionado para roxo. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.2 | 1 | Mudar o preenchimento do bloco selecionado para roxo. |
| text-box-text-to-purple | ✅ | 2.3 | 1 | Deixar roxo o texto selecionado “NORTHVILLE CENTRAL AIRPORT”. |
| text-box-text-to-purple | ✅ | 2.2 | 1 | Mudar o texto selecionado para roxo. |
| text-box-text-to-purple | ✅ | 2.1 | 1 | Mudei o texto selecionado para roxo. |
| text-box-replace-text | ✅ | 2.3 | 1 | Changed Terminal 2 to Terminal 3. |
| text-box-replace-text | ✅ | 2.4 | 1 | Change the terminal number from 2 to 3. |
| text-box-replace-text | ✅ | 2.0 | 1 | Change Terminal 2 to Terminal 3 in the Southport Airport text box. |
| last-section-to-new-page-is-a-break-not-a-move | ✅ | 6.6 | 2 | Start the Session class section on a new page at the end of the document. |
| last-section-to-new-page-is-a-break-not-a-move | ❌ | 3.0 | 1 | status 'needs_clarification' not in ['done'] (“2. Session class” is followed by its method table and a tip. Should the whole section (heading, table, and tip) m |
| last-section-to-new-page-is-a-break-not-a-move | ✅ | 3.5 | 1 | Start the “Session class” section on a new page at the end of the document. |
