# Padrões da área

Coloque aqui o documento de boas práticas de Python da área (por exemplo
`boas_praticas_python.md`). O Copilot lê todo `.md` desta pasta ao gerar e ao revisar o código
(`/nova-automacao`, `/nova-pagina`, `/revisar-automacao`, `/corrigir-falha`).

Como os dois documentos convivem:
- **Estilo, nomes, organização do código, documentação**: vale o documento da área.
- **Segurança da extração** (os Princípios de `.github/copilot-instructions.md`: determinismo, dado errado é
  pior que nenhum, sem autocorreção, não inventar): vale o template.
- **Conflito entre os dois**: o Copilot não escolhe sozinho. Ele aponta o conflito no final da resposta para
  a pessoa decidir e, se for o caso, ajustar o documento ou o template.

O documento da área não fala de `requests`. As regras para robôs HTTP estão em `.github/copilot-instructions.md`
(seção "Robô HTTP").
