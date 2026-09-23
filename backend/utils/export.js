const { Document, Packer, Paragraph, TextRun, HeadingLevel } = require("docx");

/**
 * Builds a .docx buffer from a note.
 */
async function buildDocx(note) {
  const paragraphs = [
    new Paragraph({
      text: note.title,
      heading: HeadingLevel.HEADING_1,
    }),
    new Paragraph({
      children: [
        new TextRun({
          text: `Created: ${new Date(note.createdAt).toLocaleString()}`,
          italics: true,
          size: 18,
        }),
      ],
    }),
    new Paragraph({ text: "" }),
    ...note.content
      .split("\n")
      .map((line) => new Paragraph({ text: line || " " })),
  ];

  if (note.tags && note.tags.length) {
    paragraphs.push(new Paragraph({ text: "" }));
    paragraphs.push(
      new Paragraph({
        children: [
          new TextRun({ text: `Tags: ${note.tags.join(", ")}`, italics: true, size: 18 }),
        ],
      })
    );
  }

  const doc = new Document({
    sections: [{ children: paragraphs }],
  });

  return Packer.toBuffer(doc);
}

function escapeXml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Builds a simple, well-formed XML representation of a note.
 */
function buildXml(note) {
  const tagsXml = (note.tags || [])
    .map((t) => `    <tag>${escapeXml(t)}</tag>`)
    .join("\n");

  const contentXml = note.content
    .split("\n")
    .map((line) => `    <line>${escapeXml(line)}</line>`)
    .join("\n");

  return `<?xml version="1.0" encoding="UTF-8"?>
<note id="${note._id}">
  <title>${escapeXml(note.title)}</title>
  <createdAt>${new Date(note.createdAt).toISOString()}</createdAt>
  <tags>
${tagsXml}
  </tags>
  <content>
${contentXml}
  </content>
</note>
`;
}

/**
 * Builds a plain text version of a note.
 */
function buildTxt(note) {
  const lines = [
    note.title,
    `Created: ${new Date(note.createdAt).toLocaleString()}`,
    "",
    note.content,
  ];
  if (note.tags && note.tags.length) {
    lines.push("", `Tags: ${note.tags.join(", ")}`);
  }
  return lines.join("\n");
}

module.exports = { buildDocx, buildXml, buildTxt };
