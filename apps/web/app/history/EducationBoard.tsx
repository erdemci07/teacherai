import type { BlockCheck, EducationalDraft, EducationalProvenance, LessonView, Table, VerificationReport } from '../lib/education.generated.ts';
import { MathExpression } from '../solve/MathExpression.tsx';

type Answer = NonNullable<EducationalDraft['answer']>;
type Block = EducationalDraft['blocks'][number];
type Outcome = BlockCheck['outcome'];

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

// TA-004: Adım durumu yalnızca sunucu kontrollerinden türetilir. Desteklenmeyen veya kontrol edilmeyen adım
// "geçti" olarak gösterilmez; çelişki her zaman öne çıkar.
const stepLabels: Record<Outcome, string> = {
  passed: 'Bu adım matematik motoruyla kontrol edildi.',
  partially_checked: 'Bu adım kısmen kontrol edildi.',
  failed: 'Bu adımda bir çelişki bulundu.',
  unsupported: 'Bu adım için otomatik kontrol yok.',
  not_checked: 'Bu adım otomatik kontrol edilmedi.',
  not_applicable: '',
};

export function stepOutcome(checks: BlockCheck[], ids: string[]): Outcome {
  // TA-005: yöntem/müfredat kayıt kontrolleri adımın hesap durumunu belirlemez; ayrı rozetle gösterilir.
  const outcomes = checks.filter(check => check.scope === 'block' && check.verifier !== 'registry' && check.target && ids.includes(check.target))
    .map(check => check.outcome);
  if (outcomes.includes('failed')) return 'failed';
  if (outcomes.length && outcomes.every(value => value === 'passed')) return 'passed';
  if (outcomes.some(value => value === 'passed' || value === 'partially_checked')) return 'partially_checked';
  if (outcomes.includes('unsupported')) return 'unsupported';
  return 'not_checked';
}

const methodLabels: Record<VerificationReport['method'], string> = {
  passed: 'Yöntem: bu sınıf düzeyinin onaylı politikasına uygun.',
  failed: 'Yöntem: bu sınıf düzeyine uygun yöntem doğrulanamadı.',
  partially_checked: 'Yöntem: yasak işlem bulunmadı; adımların hepsi kontrol edilemedi.',
  not_checked: 'Yöntem: değerlendirilmedi.',
};
const curriculumLabels: Record<VerificationReport['curriculum'], string> = {
  passed: 'Müfredat: konu, sınıfının resmî programındaki bir kazanıma eşlendi.',
  partially_checked: 'Müfredat: eşleme kısmi (konu sözcükten veya incelenmemiş eşlemeyle belirlendi).',
  not_checked: 'Müfredat: değerlendirilmedi.',
};

const targetLabels: Partial<Record<Outcome, string>> = {
  passed: 'Sorunun istediği sonuç bağımsız olarak hesaplandı.',
  partially_checked: 'Sorunun istediği sonuç kısmen kontrol edildi.',
  unsupported: 'Sorunun istediği sonuç otomatik doğrulanamadı.',
  not_checked: 'Sorunun istediği sonuç kontrol edilmedi.',
};

function BlockContent({ block, verification }: { block: Block; verification: VerificationReport }) {
  switch (block.kind) {
    case 'expression': return <MathExpression latex={block.latex} />;
    case 'calculation': return <><MathExpression latex={block.expression} /><AnswerContent answer={block.result} /></>;
    case 'worked_example': return <><strong>{block.prompt}</strong><p>{block.explanation}</p><AnswerContent answer={block.answer} /></>;
    case 'table': return <DataTable table={block.table} />;
    case 'visual': return <figure><figcaption>{block.description}</figcaption>
      {block.visual_type === 'number_line' ? <p>Sayı doğrusunda soldan sağa: {block.positions?.join(' · ')}</p>
        : <small>{block.visual_type === 'unsupported' ? 'Bu görsel türü henüz gösterilemiyor.' : 'Kaynak sorudaki şekle bak.'}</small>}</figure>;
    case 'derivation_step': {
      const ids = [block.id, ...(block.outputs ?? []).filter(ref => ref.kind === 'block').map(ref => ref.id)];
      const outcome = stepOutcome(verification.block_checks ?? [], ids);
      return <>{block.title && <strong>{block.title}</strong>}<p>{block.explanation}</p>
        {stepLabels[outcome] && <small data-step-check={outcome}>{stepLabels[outcome]}</small>}</>;
    }
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
  const target = verification.target ? targetLabels[verification.target.outcome] : undefined;
  const policyChecked = verification.method !== 'not_checked' || verification.curriculum !== 'not_checked';
  return <article aria-label="Ders anlatımı">
    {view.panels.map(panel => <section key={panel.blocks[0]}>{panel.blocks.map(id => {
      const block = blocks.get(id);
      return block && <BlockContent key={id} block={block} verification={verification} />;
    })}</section>)}
    {content.answer && <section><strong>Cevap</strong><AnswerContent answer={content.answer} />
      {target && <small data-target-check={verification.target?.outcome}>{target}</small>}</section>}
    <p>{content.takeaway}</p><small>{calculation} {scientific}{policyChecked ? '' : ' Müfredat ve öğretim yöntemi değerlendirilmedi.'}</small>
    {policyChecked && <p>
      <small data-policy-check="method" data-state={verification.method}>{methodLabels[verification.method]}</small>{' '}
      <small data-policy-check="curriculum" data-state={verification.curriculum}>{curriculumLabels[verification.curriculum]}</small>
    </p>}
    {view.provenance && <ProvenanceDetails provenance={view.provenance} />}
  </article>;
}

const mappingLabels: Record<string, string> = {
  structural: 'Konu, sorudaki ifadelerin yapısından belirlendi.',
  single: 'Konu, soru metnindeki sözcüklerden tahmin edildi (kesin değil).',
  ambiguous: 'Soru birden çok konuya benziyor; tek konu seçilmedi.',
  none: 'Konu belirlenemedi.',
};
const transmissionLabels: Record<string, string> = {
  normal: 'Seçilen bağlam ders üretimine gönderildi.',
  emergency: 'Bağlam sığmadığı için müfredat ve bilgi bağlamı gönderilmedi.',
  mixed: 'Çağrılardan en az birinde müfredat ve bilgi bağlamı gönderilmedi.',
};

// TA-007: dersin hangi program, konu eşlemesi, onaylı bilgi ve yöntem politikasıyla üretildiği. Aşamalı gösterim:
// kapalı başlar; teknik kimlikler yalnız açınca görünür. Kayıt ders oluşturulduktan sonra değişmez.
export function ProvenanceDetails({ provenance }: { provenance: EducationalProvenance }) {
  const resolution = provenance.resolution;
  const program = resolution.status === 'resolved' ? resolution.program_ids?.[0] : null;
  const knowledge = provenance.transmitted_knowledge_ids ?? [];
  const policies = provenance.method_policy_ids ?? [];
  return <details className="taProvenance" data-provenance="lesson">
    <summary>Bu dersin bağlamı</summary>
    <ul>
      <li>{program ? `Program: ${program} (${resolution.academic_year})` : 'Program belirlenemedi; müfredat bağlamı kullanılmadı.'}</li>
      {provenance.topic_mapping && <li>{mappingLabels[provenance.topic_mapping]}</li>}
      <li>{knowledge.length > 0 ? `Öğretmen onaylı ${knowledge.length} bilimsel bilgi girdisi kullanıldı.`
        : 'Öğretmen onaylı bilimsel bilgi girdisi kullanılmadı.'}</li>
      <li>{policies.length > 0 ? `Öğretmen onaylı ${policies.length} yöntem politikası uygulandı.`
        : 'Onaylı yöntem politikası yok; yöntem kısıtı uygulanmadı.'}</li>
      {provenance.transmission && <li>{transmissionLabels[provenance.transmission]}</li>}
    </ul>
    {(knowledge.length > 0 || policies.length > 0) && <p><small>Kayıtlar: {[...knowledge, ...policies].join(', ')}</small></p>}
  </details>;
}
