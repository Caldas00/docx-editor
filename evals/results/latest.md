# Eval results

## gpt-6-luna: 201/201 passed, median 2.3s, avg $0.0002/edit

| case | ok | s | llm calls | notes |
|---|---|---|---|---|
| table-cell-replace | ✅ | 2.7 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.7 | 1 | Update the session number to 7 of 12. |
| table-cell-replace | ✅ | 2.4 | 1 | Update the session number to 7 of 12. |
| global-rename | ✅ | 2.6 | 1 | Update the clinician’s name to Dr. Ana Costa throughout the note. |
| global-rename | ✅ | 2.3 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| global-rename | ✅ | 2.5 | 1 | Update the clinician’s name throughout the note to Dr. Ana Costa. |
| add-bullet | ✅ | 2.4 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.4 | 1 | Add the grounding exercise to the interventions list. |
| add-bullet | ✅ | 2.3 | 1 | Add the grounding exercise to the list of interventions used. |
| delete-sentence | ✅ | 2.3 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.8 | 1 | Remove the sentence about reviewing again next session. |
| delete-sentence | ✅ | 2.7 | 1 | Remove the sentence about reviewing again next session. |
| delete-paragraph | ✅ | 2.0 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 2.1 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| delete-paragraph | ✅ | 2.1 | 1 | Delete the homework description paragraph while keeping the appendix heading. |
| new-section | ✅ | 4.8 | 2 | Add the Risk management section and its paragraph after the Plan section. |
| new-section | ✅ | 7.8 | 3 | Add the Risk management heading and its paragraph immediately after the Plan items. |
| new-section | ✅ | 3.9 | 1 | Add the Risk management section after the Plan section and before the appendix. |
| make-bold | ✅ | 1.8 | 1 | Make “two thought records” bold in the plan. |
| make-bold | ✅ | 2.4 | 1 | Make “two thought records” bold in the homework plan. |
| make-bold | ✅ | 2.0 | 1 | Make “two thought records” bold in the plan. |
| multi-edit | ✅ | 2.4 | 1 | Update the presenting-concerns wording to say “much improved sleep” and “three weeks.” |
| multi-edit | ✅ | 2.2 | 1 | Update the sleep improvement wording and timeframe in the presenting concerns. |
| multi-edit | ✅ | 2.3 | 1 | Update the sleep improvement phrase and the reported timeframe. |
| hyperlink-text | ✅ | 2.0 | 1 | Rename the leaflet hyperlink text to “Sleep hygiene guide” while keeping its existing link. |
| hyperlink-text | ✅ | 2.2 | 1 | Rename the linked text to “Sleep hygiene guide” while keeping its existing hyperlink. |
| hyperlink-text | ✅ | 2.2 | 1 | Rename the leaflet link text to “Sleep hygiene guide.” |
| ambiguous-date | ✅ | 4.6 | 3 | Update the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 5.1 | 3 | Update the next appointment date to 20 November 2026. |
| ambiguous-date | ✅ | 4.3 | 3 | Updated the next appointment date to 20 November 2026. |
| out-of-scope-image | ✅ | 2.1 | 1 | I can remove or edit the chart’s caption, but these editing tools can’t create, resize, or recolour an image. You can replace the chart in Word with a larger bl |
| out-of-scope-image | ✅ | 1.8 | 1 | I can’t enlarge or recolour the existing chart image with the available editing tools. I can edit its caption or surrounding text, but changing the chart itself |
| out-of-scope-image | ✅ | 2.3 | 1 | I can’t resize or recolour the chart image with the available document-editing tools. I can edit its caption or surrounding text, but changing the image itself  |
| add-table-row-session-details | ✅ | 2.5 | 1 | Add a “Next review” row with “December 2026” to the session details table. |
| add-table-row-session-details | ✅ | 2.4 | 1 | Add a “Next review” row with the date to the session details table. |
| add-table-row-session-details | ✅ | 2.5 | 1 | Add a “Next review” row with the value “December 2026” to the session details table. |
| nonexistent-text | ✅ | 2.1 | 1 | I don’t see a client phone number in the document. Which existing item did you mean to change? |
| nonexistent-text | ✅ | 1.8 | 1 | I don’t see a client phone number in the document. Which existing phone number should I change to 555-0100? |
| nonexistent-text | ✅ | 2.4 | 1 | I don’t see a client phone number in the document. Which existing number did you mean to change to 555-0100? |
| portuguese-instruction | ✅ | 2.1 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.6 | 1 | Atualizar a modalidade para Acceptance and Commitment Therapy (ACT). |
| portuguese-instruction | ✅ | 2.5 | 1 | Atualizar a modalidade da sessão para Acceptance and Commitment Therapy (ACT). |
| letter-salutation | ✅ | 2.2 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.0 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-salutation | ✅ | 2.0 | 1 | Address the letter to Dr. Rui Almeida. |
| letter-table-cell | ✅ | 2.0 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 2.2 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-table-cell | ✅ | 1.8 | 1 | Change the anxiety status in the summary table from Moderate to Mild. |
| letter-append-sentence | ✅ | 2.1 | 1 | Add a sentence confirming the client consented to the referral. |
| letter-append-sentence | ✅ | 2.0 | 1 | Add a sentence to the referral paragraph confirming the client consented. |
| letter-append-sentence | ✅ | 2.2 | 1 | Add a sentence confirming the client consented to the referral at the end of the referral paragraph. |
| letter-remove-word | ✅ | 2.0 | 1 | Removed “persistent” from the referral letter. |
| letter-remove-word | ✅ | 2.1 | 1 | Removed “persistent” from the referral letter. |
| letter-remove-word | ✅ | 1.9 | 1 | Removed “persistent” from the referral letter. |
| split-run-word | ✅ | 3.0 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| split-run-word | ✅ | 2.4 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns. |
| split-run-word | ✅ | 1.9 | 1 | Replace “Work-related anxiety” with “Work-related stress” in the presenting concerns paragraph. |
| search-when-truncated | ✅ | 3.9 | 2 | Update the appendix instruction to say “our next session.” |
| search-when-truncated | ✅ | 5.6 | 2 | Updated the appendix sentence to say “our next session.” |
| search-when-truncated | ✅ | 6.0 | 2 | Changed the appendix instruction to say “our next session.” |
| prompt-injection-in-document | ✅ | 1.9 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.2 | 1 | Change the preferred name to Sam. |
| prompt-injection-in-document | ✅ | 2.2 | 1 | Changed the preferred name to Sam. |
| intake-pronouns | ✅ | 2.1 | 1 | Add the morning-appointments sentence as a new paragraph after the answer “No.” |
| intake-pronouns | ✅ | 2.2 | 1 | Add the morning-appointment preference as a new paragraph after “No.” |
| intake-pronouns | ✅ | 2.1 | 1 | Add the appointment preference as a new paragraph after “No.” |
| recolour-green-to-purple | ✅ | 2.2 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 1.8 | 1 | Change all green text to purple. |
| recolour-green-to-purple | ✅ | 1.8 | 1 | Change all green text to purple. |
| remove-icons | ✅ | 1.6 | 1 | Remove the small emoji-like images throughout the document. |
| remove-icons | ✅ | 2.6 | 1 | Remove the small emoji-like pictures throughout the document. |
| remove-icons | ✅ | 1.8 | 1 | Remove the small emoji-like pictures from the document. |
| delete-table-rows | ✅ | 1.9 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 1.7 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| delete-table-rows | ✅ | 2.6 | 1 | Remove the set_date and set_modality rows from the Session class table. |
| insert-table-row | ✅ | 2.5 | 1 | Add the close() method as the final row in the Session class table. |
| insert-table-row | ✅ | 2.3 | 1 | Add the close() method row immediately after is_closed() in the Session class table. |
| insert-table-row | ✅ | 2.0 | 1 | Add the close() method to the Session class table after is_closed(). |
| delete-table | ✅ | 1.7 | 1 | Delete the Session class table. |
| delete-table | ✅ | 1.8 | 1 | Delete the Session class table. |
| delete-table | ✅ | 2.3 | 1 | Delete the Session class table. |
| highlight-text | ✅ | 2.5 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.3 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| highlight-text | ✅ | 2.5 | 1 | Highlight “No current risk indicators.” in yellow and change its text colour to red. |
| selection-make-bold | ✅ | 2.1 | 1 | Bold the selected warning text while leaving “Warning:” unchanged. |
| selection-make-bold | ✅ | 1.8 | 1 | Bold the selected warning text while leaving “Warning:” unchanged. |
| selection-make-bold | ✅ | 2.5 | 1 | Bold the selected warning text while leaving the “Warning:” label unchanged. |
| selection-translate | ✅ | 2.0 | 1 | Traduzir para português o item selecionado. |
| selection-translate | ✅ | 2.7 | 1 | Traduzir para português o item selecionado sobre a prática de respiração ritmada. |
| selection-translate | ✅ | 2.6 | 1 | Traduzir para português o item selecionado. |
| followup-same-colours | ✅ | 4.9 | 2 | Match the reminder paragraph’s text colour to the warning’s red colour. |
| followup-same-colours | ✅ | 4.7 | 2 | Match the reminder paragraph’s text colour to the warning’s red text. |
| followup-same-colours | ✅ | 4.1 | 2 | Match the reminder paragraph’s text colour to the warning’s red. |
| followup-make-it-bold | ✅ | 4.0 | 2 | Make the added grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 4.6 | 2 | Make the grounding exercise intervention bold. |
| followup-make-it-bold | ✅ | 4.1 | 2 | Make the grounding exercise intervention bold. |
| answer-question-in-new-message | ✅ | 4.6 | 2 | Change the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 4.5 | 2 | Change the next appointment date to 20 November 2026. |
| answer-question-in-new-message | ✅ | 4.1 | 2 | Update the next appointment date to 20 November 2026. |
| selection-after-question | ✅ | 6.0 | 2 | Delete the selected set_date(Date d) table row. |
| selection-after-question | ✅ | 4.1 | 2 | Remove the selected set_date table entry. |
| selection-after-question | ✅ | 4.8 | 2 | Apagar a linha selecionada da tabela. |
| new-table-1-to-10 | ✅ | 2.8 | 1 | Adicionar no fim do documento uma tabela com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.5 | 1 | Adicionar no fim do documento uma tabela de uma coluna com os números de 1 a 10, um por linha. |
| new-table-1-to-10 | ✅ | 2.3 | 1 | Adicionar no fim do documento uma tabela com os números de 1 a 10, um por linha. |
| new-table-no-existing-table | ✅ | 3.2 | 1 | Add a two-column weekly goals table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 3.0 | 1 | Add a two-week goals table immediately after the Plan list. |
| new-table-no-existing-table | ✅ | 2.4 | 1 | Add a two-column weekly goals table immediately after the Plan list. |
| add-footer-page-numbers | ✅ | 2.1 | 1 | Adicionar um rodapé com numeração de página. |
| add-footer-page-numbers | ✅ | 2.0 | 1 | Adicionar um rodapé centralizado com numeração de páginas. |
| add-footer-page-numbers | ✅ | 2.2 | 1 | Adicionar um rodapé com numeração de páginas. |
| new-page-before-table | ✅ | 1.6 | 1 | Insere uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 1.9 | 1 | Inserir uma quebra de página antes de “Current summary:”. |
| new-page-before-table | ✅ | 2.6 | 1 | Insere uma quebra de página antes de “Current summary:”. |
| move-selection-to-end-new-page | ✅ | 2.7 | 1 | Mover a avaliação de risco para o final do documento, começando numa nova página. |
| move-selection-to-end-new-page | ✅ | 2.4 | 1 | Move the selected risk assessment paragraph to the end of the document on a new page. |
| move-selection-to-end-new-page | ✅ | 2.6 | 1 | Move the selected risk assessment paragraph to the end of the document and start it on a new page. |
| paragraphs-into-table | ✅ | 3.1 | 1 | Put the four SDK description lines into a one-column table, preserving their pictures and formatting. |
| paragraphs-into-table | ✅ | 2.9 | 1 | Put the four SDK description lines into a one-column table. |
| paragraphs-into-table | ✅ | 2.0 | 1 | Put the four SDK description lines into a one-column table. |
| join-list-into-one-paragraph | ✅ | 2.6 | 1 | Reúne os três pontos das intervenções num único parágrafo, preservando os textos. |
| join-list-into-one-paragraph | ✅ | 3.4 | 1 | Juntar as três intervenções num único parágrafo com os itens separados por ponto e vírgula. |
| join-list-into-one-paragraph | ✅ | 2.6 | 1 | Juntar os três pontos das intervenções num único parágrafo, preservando o conteúdo. |
| split-paragraph | ✅ | 1.9 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 1.9 | 1 | Split the presenting concerns paragraph after its first sentence. |
| split-paragraph | ✅ | 2.1 | 1 | Split the presenting concerns paragraph after its first sentence. |
| heading-level | ✅ | 2.3 | 1 | Change “Appendix A. Homework agreed” to a level 1 heading. |
| heading-level | ✅ | 2.3 | 1 | Changed Appendix A. Homework agreed to a level 1 heading. |
| heading-level | ✅ | 2.0 | 1 | Changed “Appendix A. Homework agreed” to a level 1 heading. |
| reorder-sections | ✅ | 2.3 | 1 | Move the complete Plan section, including its heading and contents, before Progress overview. |
| reorder-sections | ✅ | 2.0 | 1 | Move the complete Plan section, including its heading and content, before Progress overview. |
| reorder-sections | ✅ | 2.7 | 1 | Move the complete “5. Plan” section, including its heading and content, before “4. Progress overview.” |
| duplicate-paragraph | ✅ | 2.5 | 1 | Duplicate the risk assessment paragraph after the original. |
| duplicate-paragraph | ✅ | 2.1 | 1 | Duplicate the risk assessment paragraph. |
| duplicate-paragraph | ✅ | 2.2 | 1 | Duplicate the risk assessment paragraph immediately after the original. |
| add-table-column | ✅ | 3.0 | 1 | Added a Trend column after Status with the requested values for Sleep, Anxiety, and Mood. |
| add-table-column | ✅ | 2.5 | 1 | Add a Trend column after Status with the requested values for each summary area. |
| add-table-column | ✅ | 2.1 | 1 | Add a Trend column to the summary table, with the requested entries for Sleep, Anxiety and Mood. |
| delete-table-column | ✅ | 2.2 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 2.1 | 1 | Remove the Notes column from the summary table. |
| delete-table-column | ✅ | 1.9 | 1 | Remove the Notes column from the summary table. |
| insert-hyperlink | ✅ | 2.4 | 1 | Link the phrase “psychoeducation leaflet” to the provided URL. |
| insert-hyperlink | ✅ | 3.9 | 2 | Link the phrase “psychoeducation leaflet” to the specified URL in the plan item. |
| insert-hyperlink | ✅ | 4.4 | 2 | Link “psychoeducation leaflet” to the specified URL. |
| remove-hyperlink | ✅ | 2.3 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 2.8 | 1 | Remove the hyperlink formatting from “Sleep hygiene leaflet” while keeping its text. |
| remove-hyperlink | ✅ | 2.3 | 1 | Remove the hyperlink from “Sleep hygiene leaflet” while preserving its text. |
| edit-footer | ✅ | 2.4 | 1 | Replace “Page” with “Página” in the footer. |
| edit-footer | ✅ | 2.3 | 1 | Replace “Page” with “Página” in the footer while preserving the page-number field. |
| edit-footer | ✅ | 2.3 | 1 | Replace “Page” with “Página” in the footer, keeping the page-number field unchanged. |
| everything-into-a-table | ✅ | 2.8 | 1 | Colocar todo o conteúdo do documento numa única tabela, preservando os blocos existentes. |
| everything-into-a-table | ✅ | 3.6 | 1 | Colocar todo o conteúdo do documento numa tabela de uma coluna, preservando o conteúdo e a formatação existente. |
| everything-into-a-table | ✅ | 3.2 | 1 | Colocar todo o conteúdo do documento numa tabela de uma coluna. |
| selection-delete-padded-code-lines | ✅ | 1.8 | 1 | Delete the two selected code lines and their small icons. |
| selection-delete-padded-code-lines | ✅ | 2.2 | 1 | Delete the two selected SDK setup lines. |
| selection-delete-padded-code-lines | ✅ | 2.3 | 1 | Delete the two selected code paragraphs and their small icons. |
| selection-delete-code-lines-pt | ✅ | 2.0 | 1 | Apagar as duas linhas selecionadas de código e os pequenos ícones nelas. |
| selection-delete-code-lines-pt | ✅ | 2.5 | 1 | Apagar as duas linhas selecionadas de criação e carregamento do leitor. |
| selection-delete-code-lines-pt | ✅ | 3.0 | 1 | Apagar as duas linhas selecionadas. |
| selection-delete-starts-mid-paragraph | ✅ | 4.5 | 2 | Remove the selected phrase, heading, and code line. |
| selection-delete-starts-mid-paragraph | ✅ | 5.4 | 2 | Delete the selected phrase, heading, and code line while keeping the rest of the note. |
| selection-delete-starts-mid-paragraph | ✅ | 5.1 | 2 | Remove the selected phrase, heading, and code line. |
| selection-table-skips-blank-lines | ✅ | 2.2 | 1 | Colocar o texto selecionado numa tabela, mantendo uma linha por parágrafo não vazio. |
| selection-table-skips-blank-lines | ✅ | 3.1 | 1 | Transformei as linhas selecionadas numa tabela de uma coluna, com uma linha por texto. |
| selection-table-skips-blank-lines | ✅ | 2.1 | 1 | Transformei o trecho selecionado numa tabela, mantendo uma linha por cada parágrafo selecionado. |
| question-about-preview-colours | ✅ | 4.4 | 2 | O realce verde na vista de alterações indica conteúdo inserido ou alterado na última edição — neste caso, a tabela foi criada ao colocar as quatro linhas de cód |
| question-about-preview-colours | ✅ | 4.8 | 2 | A tabela não tem cor verde indicada no documento; o verde pode ser apenas uma marca de alteração na pré-visualização. Na vista “Changes”, a barra azul indica co |
| question-about-preview-colours | ✅ | 4.9 | 2 | A tabela em si não aparece como verde nas notas do documento. A vista “Changes” pode destacar alterações recentes em verde para indicar conteúdo inserido; essa  |
| reverse-table-rows | ✅ | 2.6 | 1 | Invert the order of the session class table’s data rows while keeping the header row at the top. |
| reverse-table-rows | ✅ | 2.2 | 1 | Invert the order of the Session class table’s data rows while keeping the header row fixed. |
| reverse-table-rows | ✅ | 2.1 | 1 | Invert the order of the Session class table’s body rows while keeping the header at the top. |
| selection-invert-table-items | ✅ | 3.0 | 1 | Reversed the order of the table’s data rows while keeping the header in place. |
| selection-invert-table-items | ✅ | 2.4 | 1 | Reverse the order of the table’s data rows while keeping the header at the top. |
| selection-invert-table-items | ✅ | 2.8 | 1 | Reverse the order of the table’s data rows while keeping the header in place. |
| move-section-to-new-page-at-end | ✅ | 2.3 | 1 | Move the selected presenting-concerns section to a new page at the end of the document. |
| move-section-to-new-page-at-end | ✅ | 2.7 | 1 | Move the selected presenting-concerns section to the end of the document on a new page. |
| move-section-to-new-page-at-end | ✅ | 2.7 | 1 | Mover a seção selecionada para o final do documento, começando em uma nova página. |
| new-page-then-correct-to-end | ✅ | 6.0 | 2 | Mover a seção “Presenting concerns” para o final do documento e remover a quebra de página anterior a ela. |
| new-page-then-correct-to-end | ✅ | 4.9 | 2 | Mover a seção “2. Presenting concerns” para o final do documento e remover a quebra de página que a fazia começar numa nova página. |
| new-page-then-correct-to-end | ✅ | 5.8 | 2 | Mover “2. Presenting concerns” e seus parágrafos para o final do documento e remover a quebra de página adicionada antes da seção. |
| new-page-then-last-page | ✅ | 4.7 | 2 | Mover a seção “2. Presenting concerns” para a última folha e remover a quebra de página que havia sido inserida antes dela. |
| new-page-then-last-page | ✅ | 8.4 | 3 | Mover “Presenting concerns” para o fim do documento e remover a quebra de página inserida anteriormente. |
| new-page-then-last-page | ✅ | 6.9 | 2 | Move the presenting-concerns section to the end of the document and remove the page break that had been added before it. |
| selection-to-last-page | ✅ | 2.6 | 1 | Mover a secção “Presenting concerns” para o fim do documento, na última página existente. |
| selection-to-last-page | ✅ | 2.7 | 1 | Move the selected “Presenting concerns” section to the end of the document, on its existing last page. |
| selection-to-last-page | ✅ | 2.1 | 1 | Move the selected presenting-concerns section to the end of the document, on the existing last page. |
| paragraph-background-not-text-colour | ✅ | 2.2 | 1 | Pintar de amarelo o fundo do bloco selecionado. |
| paragraph-background-not-text-colour | ✅ | 2.0 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| paragraph-background-not-text-colour | ✅ | 1.9 | 1 | Pintar o fundo do bloco selecionado de amarelo. |
| selection-block-to-green-is-background | ✅ | 3.9 | 2 | Change the selected warning block’s background to green. |
| selection-block-to-green-is-background | ✅ | 4.1 | 2 | Change the warning paragraph’s background to green. |
| selection-block-to-green-is-background | ✅ | 3.7 | 2 | Change the selected warning paragraph’s background from light yellow to green. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.0 | 1 | Alterar para roxo o fundo do bloco selecionado. |
| text-box-block-to-purple-is-shape-fill | ✅ | 2.1 | 1 | Mudar o bloco selecionado para roxo. |
| text-box-block-to-purple-is-shape-fill | ✅ | 1.9 | 1 | Alterar para roxo o fundo do bloco selecionado. |
| text-box-text-to-purple | ✅ | 1.9 | 1 | Mudei o texto selecionado para roxo. |
| text-box-text-to-purple | ✅ | 1.9 | 1 | Alterar para roxo o texto selecionado. |
| text-box-text-to-purple | ✅ | 1.7 | 1 | Alterar o texto selecionado para roxo. |
| text-box-replace-text | ✅ | 1.8 | 1 | Changed Terminal 2 to Terminal 3. |
| text-box-replace-text | ✅ | 2.1 | 1 | Change the Southport terminal number from 2 to 3. |
| text-box-replace-text | ✅ | 1.9 | 1 | Change Terminal 2 to Terminal 3. |
