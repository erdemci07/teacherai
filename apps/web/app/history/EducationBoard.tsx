import type { EducationalDraft, LessonView, Table } from '../lib/education.generated.ts';
import { MathExpression } from '../solve/MathExpression.tsx';

type Answer = NonNullable<EducationalDraft['answer']>;
type Block = EducationalDraft['blocks'][number];

function DataTable({ table }: { table: Table }) {
  return <table><thead><tr>{table.headers.map((column, i) => <th key={i} scope="col">{column}</th>)}</tr></thead>
    <tbody>{table.rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>)}</tbody></table>;
}

function AnswerContent({ answer }: { answer: Answer }) {
  switch (answer.kind) {
    case 'text': return <p>{answer.text}</p>;
    case 'math': return <><p>{answer.description}</p>{answer.expressions.map((latex, i) => <MathExpression key={i} latex={latex} />)}</>;
    case 'number': return <p>{answer.value}</p>;
    case 'choice': return <p>{answer.choices[answer.selected]}</p>;
    case 'quantity': return <p>{answer.quantity.label && <>{answer.quantity.label} · </>}{answer.quantity.value} {answer.quantity.unit}</p>;
    case 'table': return <DataTable table={answer.table} />;
  }
}

const labels = {warning: 'Dikkat', hint: 'İpucu', checkpoint: 'Kendini sına', definition: 'Kavram',
  explanation: '', result: 'Sonuç', summary: 'Özet'};

function BlockContent({ block }: { block: Block }) {
  switch (block.kind) {
    case 'expression': return <MathExpression latex={block.latex} />;
    case 'calculation': return <><MathExpression latex={block.expression} /><AnswerContent answer={block.result} /></>;
    case 'worked_example': return <><strong>{block.prompt}</strong><p>{block.explanation}</p><AnswerContent answer={block.answer} /></>;
    case 'table': return <DataTable table={block.table} />;
    case 'visual': return <figure><figcaption>{block.description}</figcaption>
      {block.visual_type === 'number_line' ? <p>Sayı doğrusunda soldan sağa: {block.positions?.join(' · ')}</p>
        : <small>{block.visual_type === 'unsupported' ? 'Bu görsel türü henüz gösterilemiyor.' : 'Kaynak sorudaki şekle bak.'}</small>}</figure>;
    default: return <>{(block.title || labels[block.kind]) && <strong>{block.title || labels[block.kind]}</strong>}<p>{block.text}</p></>;
  }
}

export function EducationBoard({ view }: { view: LessonView }) {
  const { content, verification } = view.lesson;
  const blocks = new Map(content.blocks.map(block => [block.id, block]));
  const calculation = {passed: 'Matematik motorunun desteklediği hesaplar kontrol edildi.',
    partially_checked: 'Hesapların bir bölümü kontrol edildi.', failed: 'Hesap kontrolü başarısız.',
    unsupported: 'Bu hesap için otomatik doğrulama yok.', not_applicable: 'Hesap kontrolü uygulanmıyor.',
    not_checked: 'Hesaplar kontrol edilmedi.'}[verification.calculation];
  const scientific = {passed: 'Bilimsel içerik kontrol edildi.', partially_checked: 'Bilimsel içeriğin yalnızca bir bölümü kontrol edildi.',
    failed: 'Bilimsel kontrol başarısız.', unsupported: 'Bu alanda bilimsel içerik henüz otomatik doğrulanmıyor.',
    not_applicable: '', not_checked: 'Bilimsel içerik kontrol edilmedi.'}[verification.scientific];
  return <article aria-label="Ders anlatımı">
    {view.panels.map(panel => <section key={panel.blocks[0]}>{panel.blocks.map(id => {
      const block = blocks.get(id);
      return block && <BlockContent key={id} block={block} />;
    })}</section>)}
    {content.answer && <section><strong>Cevap</strong><AnswerContent answer={content.answer} /></section>}
    <p>{content.takeaway}</p><small>{calculation} {scientific} Müfredat ve öğretim yöntemi değerlendirilmedi.</small>
  </article>;
}
